import logging

from app.config import load_backend_environment


def test_loads_backend_env_and_logs_only_safe_configuration(tmp_path, monkeypatch, caplog) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_API_KEY=sk-startup-secret\n"
        "OPENAI_MODEL=gpt-test-model\n"
        "OPENAI_TIMEOUT_SECONDS=25\n"
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        load_backend_environment(env_path)

    assert "api_key_configured=true" in caplog.text
    assert "provider=openai" in caplog.text
    assert "model=gpt-test-model" in caplog.text
    assert "timeout_seconds=25" in caplog.text
    assert "sk-startup-secret" not in caplog.text


def test_deployment_environment_takes_precedence_over_local_env(
    tmp_path,
    monkeypatch,
    caplog,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_API_KEY=sk-local-secret\n"
        "OPENAI_MODEL=gpt-local-model\n"
    )
    monkeypatch.setenv("OPENAI_API_KEY", "render-secret")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-render-model")

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        load_backend_environment(env_path)

    assert "api_key_configured=true" in caplog.text
    assert "model=gpt-render-model" in caplog.text
    assert "render-secret" not in caplog.text
    assert "sk-local-secret" not in caplog.text
