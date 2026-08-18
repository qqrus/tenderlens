from fastapi import Query
from fastapi.testclient import TestClient
from pydantic import SecretStr

from tenderlens.core.config import Settings
from tenderlens.core.errors import AppError
from tenderlens.main import create_app


def make_settings() -> Settings:
    return Settings(
        app_env="test",
        database_url=SecretStr(
            "postgresql+asyncpg://tenderlens:tenderlens@localhost:5432/tenderlens_test"
        ),
        cors_origins=["http://localhost:8501"],
    )


def test_application_factory_exposes_health_and_request_id() -> None:
    app = create_app(make_settings())

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/health/live",
            headers={"X-Request-ID": "test-request-id"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"
    assert response.json()["version"] == "0.1.0"


def test_application_error_has_stable_response() -> None:
    app = create_app(make_settings())

    @app.get("/expected-error")
    async def expected_error() -> dict[str, str]:
        raise AppError(
            code="document_too_large",
            message="Document is too large.",
            status_code=413,
            details={"max_mb": 20},
        )

    with TestClient(app) as client:
        response = client.get("/expected-error")

    assert response.status_code == 413
    assert response.json() == {
        "error": {
            "code": "document_too_large",
            "message": "Document is too large.",
            "details": {"max_mb": 20},
        }
    }


def test_validation_error_has_stable_response() -> None:
    app = create_app(make_settings())

    @app.get("/validated")
    async def validated(limit: int = Query(ge=1)) -> dict[str, int]:
        return {"limit": limit}

    with TestClient(app) as client:
        response = client.get("/validated", params={"limit": 0})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"]["issues"]


def test_unexpected_error_is_hidden_from_client() -> None:
    app = create_app(make_settings())

    @app.get("/unexpected-error")
    async def unexpected_error() -> dict[str, str]:
        raise RuntimeError("sensitive internal detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/unexpected-error")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "details": {},
        }
    }
    assert "sensitive" not in response.text
