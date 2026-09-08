import logging

from app.config import load_backend_environment


def test_loads_backend_env_and_logs_only_safe_configuration(tmp_path, monkeypatch, caplog) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "ANTHROPIC_API_KEY=sk-ant-startup-secret\n"
        "ANTHROPIC_MODEL=claude-test-model\n"
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        load_backend_environment(env_path)

    assert "api_key_configured=true" in caplog.text
    assert "model=claude-test-model" in caplog.text
    assert "sk-ant-startup-secret" not in caplog.text


def test_deployment_environment_takes_precedence_over_local_env(
    tmp_path,
    monkeypatch,
    caplog,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "ANTHROPIC_API_KEY=sk-ant-local-secret\n"
        "ANTHROPIC_MODEL=claude-local-model\n"
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "render-secret")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-render-model")

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        load_backend_environment(env_path)

    assert "api_key_configured=true" in caplog.text
    assert "model=claude-render-model" in caplog.text
    assert "render-secret" not in caplog.text
    assert "sk-ant-local-secret" not in caplog.text
