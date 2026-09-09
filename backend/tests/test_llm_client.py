import httpx
import pytest

from app.services.llm_client import OpenAIResponsesClient


class StubHTTPClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.request: dict[str, object] | None = None

    def post(self, url: str, **kwargs) -> httpx.Response:
        self.request = {"url": url, **kwargs}
        return self.response


def _response(status_code: int, payload: object) -> httpx.Response:
    request = httpx.Request("POST", "https://api.openai.test/v1/responses")
    return httpx.Response(status_code, request=request, json=payload)


def test_openai_client_calls_responses_api_and_returns_structured_text() -> None:
    transport = StubHTTPClient(
        _response(200, {"output_text": '{"message":"Please reply."}'})
    )
    client = OpenAIResponsesClient(
        api_key="unused-test-key",
        model="gpt-test-model",
        base_url="https://api.openai.test/v1/",
        client=transport,
    )
    schema = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
        "additionalProperties": False,
    }

    result = client.generate_text(
        system="System rules",
        prompt='{"booking_id":"booking_test"}',
        output_schema=schema,
        max_tokens=120,
    )

    assert result == '{"message":"Please reply."}'
    assert transport.request == {
        "url": "https://api.openai.test/v1/responses",
        "headers": {
            "Authorization": "Bearer unused-test-key",
            "Content-Type": "application/json",
        },
        "json": {
            "model": "gpt-test-model",
            "instructions": "System rules",
            "input": '{"booking_id":"booking_test"}',
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "rescue_sms",
                    "strict": True,
                    "schema": schema,
                }
            },
            "max_output_tokens": 120,
            "store": False,
        },
    }


def test_openai_client_reads_text_from_response_output_blocks() -> None:
    transport = StubHTTPClient(
        _response(
            200,
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": '{"message":"Reply."}'}
                        ]
                    }
                ]
            },
        )
    )
    client = OpenAIResponsesClient(
        api_key="unused-test-key",
        model="gpt-test-model",
        client=transport,
    )

    assert client.generate_text(
        system="System rules",
        prompt="{}",
        output_schema={"type": "object"},
        max_tokens=120,
    ) == '{"message":"Reply."}'


def test_openai_client_rejects_response_without_text() -> None:
    client = OpenAIResponsesClient(
        api_key="unused-test-key",
        model="gpt-test-model",
        client=StubHTTPClient(_response(200, {"output": []})),
    )

    with pytest.raises(ValueError, match="no text content"):
        client.generate_text(
            system="System rules",
            prompt="{}",
            output_schema={"type": "object"},
            max_tokens=120,
        )


def test_openai_client_logs_safe_request_failure_details(caplog) -> None:
    api_key = "sk-must-not-appear"
    response = _response(
        401,
        {
            "error": {
                "message": "credit balance is too low",
                "api_key": "sk-body-secret",
            }
        },
    )
    client = OpenAIResponsesClient(
        api_key=api_key,
        model="gpt-test-model",
        client=StubHTTPClient(response),
    )

    with caplog.at_level("WARNING", logger="uvicorn.error"):
        with pytest.raises(httpx.HTTPStatusError):
            client.generate_text(
                system="do-not-log-system",
                prompt="do-not-log-prompt",
                output_schema={"type": "object"},
                max_tokens=120,
            )

    log_output = caplog.text
    assert "provider=openai" in log_output
    assert "error_type=HTTPStatusError" in log_output
    assert "status_code=401" in log_output
    assert "credit balance is too low" in log_output
    assert "[REDACTED]" in log_output
    assert api_key not in log_output
    assert "sk-body-secret" not in log_output
    assert "do-not-log-system" not in log_output
    assert "do-not-log-prompt" not in log_output
