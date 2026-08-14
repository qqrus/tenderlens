from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from tenderlens import __version__
from tenderlens.core.errors import error_payload
from tenderlens.db.session import Database

router = APIRouter(prefix="/health")


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = __version__


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse()


@router.get("/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse | JSONResponse:
    database: Database = request.app.state.database
    try:
        await database.ping()
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_payload(
                code="database_unavailable",
                message="Database is not ready.",
            ),
        )
    return HealthResponse()
