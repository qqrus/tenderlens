from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from tenderlens.api.routes.health import router


class HealthyDatabase:
    async def ping(self) -> None:
        return None


class UnhealthyDatabase:
    async def ping(self) -> None:
        raise SQLAlchemyError("database unavailable")


def create_test_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database = HealthyDatabase()
        yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(router, prefix="/api/v1")
    return app


def test_liveness() -> None:
    with TestClient(create_test_app()) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_readiness() -> None:
    with TestClient(create_test_app()) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_reports_database_failure() -> None:
    app = create_test_app()
    with TestClient(app) as client:
        app.state.database = UnhealthyDatabase()
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
