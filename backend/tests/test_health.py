from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.main import _cors_origins, app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "rescue-agent-api",
    }


def test_cors_defaults_to_local_frontend(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("FRONTEND_ORIGIN", raising=False)

    assert _cors_origins() == ["http://localhost:3000"]


def test_cors_includes_render_frontend_origin_and_localhost(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv(
        "FRONTEND_ORIGIN", "https://rescue-snag-bookings.vercel.app/"
    )

    assert _cors_origins() == [
        "http://localhost:3000",
        "https://rescue-snag-bookings.vercel.app",
    ]


def test_cors_preserves_optional_legacy_origin_list(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://preview.example.com, http://localhost:3000/",
    )
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://production.example.com")

    assert _cors_origins() == [
        "http://localhost:3000",
        "https://preview.example.com",
        "https://production.example.com",
    ]


def test_cors_preflight_allows_local_and_deployed_frontends(monkeypatch) -> None:
    production_origin = "https://rescue-snag-bookings.vercel.app"
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv("FRONTEND_ORIGIN", production_origin)
    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    with TestClient(test_app) as cors_client:
        for origin in ("http://localhost:3000", production_origin):
            response = cors_client.options(
                "/dashboard",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                },
            )

            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin
