from types import SimpleNamespace

import pytest

from app.services.claude_client import ClaudeClient


class StubMessages:
    def __init__(self, content: list[object]) -> None:
        self.content = content
        self.request: dict[str, object] | None = None

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(content=self.content)


class FailingMessages:
    def create(self, **kwargs):
        class AuthenticationFailure(Exception):
            status_code = 401
            body = {
                "error": {
                    "message": "credit balance is too low",
                    "api_key": "sk-ant-body-secret",
                }
            }

        raise AuthenticationFailure(
            "request rejected for x-api-key: sk-ant-must-not-appear"
        )


def test_claude_client_calls_messages_api_and_returns_text() -> None:
    messages = StubMessages(
        [SimpleNamespace(type="text", text='{"message":"Please reply."}')]
    )
    sdk = SimpleNamespace(messages=messages)
    client = ClaudeClient(
        api_key="unused-test-key",
        model="claude-test-model",
        client=sdk,
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
    assert messages.request == {
        "model": "claude-test-model",
        "max_tokens": 120,
        "system": "System rules",
        "messages": [
            {"role": "user", "content": '{"booking_id":"booking_test"}'}
        ],
        "output_config": {
            "format": {"type": "json_schema", "schema": schema}
        },
    }


def test_claude_client_rejects_response_without_text() -> None:
    messages = StubMessages([SimpleNamespace(type="tool_use")])
    client = ClaudeClient(
        api_key="unused-test-key",
        model="claude-test-model",
        client=SimpleNamespace(messages=messages),
    )

    with pytest.raises(ValueError, match="no text content"):
        client.generate_text(
            system="System rules",
            prompt="{}",
            output_schema={"type": "object"},
            max_tokens=120,
        )


def test_claude_client_logs_safe_request_failure_details(caplog) -> None:
    client = ClaudeClient(
        api_key="sk-ant-must-not-appear",
        model="claude-test-model",
        client=SimpleNamespace(messages=FailingMessages()),
    )

    with caplog.at_level("WARNING", logger="uvicorn.error"):
        with pytest.raises(Exception, match="request rejected"):
            client.generate_text(
                system="do-not-log-system",
                prompt="do-not-log-prompt",
                output_schema={"type": "object"},
                max_tokens=120,
            )

    log_output = caplog.text
    assert "error_type=AuthenticationFailure" in log_output
    assert "status_code=401" in log_output
    assert "message=request rejected" in log_output
    assert "credit balance is too low" in log_output
    assert "[REDACTED]" in log_output
    assert "sk-ant-must-not-appear" not in log_output
    assert "sk-ant-body-secret" not in log_output
    assert "do-not-log-system" not in log_output
    assert "do-not-log-prompt" not in log_output
