from fastapi import APIRouter

from tenderlens.api.routes.documents import router as documents_router
from tenderlens.api.routes.health import router as health_router
from tenderlens.api.routes.search import router as search_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(search_router, tags=["retrieval"])
