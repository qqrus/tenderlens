from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tenderlens.api.router import api_router
from tenderlens.core.config import Settings, get_settings
from tenderlens.core.errors import register_error_handlers
from tenderlens.core.logging import configure_logging
from tenderlens.core.middleware import RequestContextMiddleware
from tenderlens.db.session import Database
from tenderlens.ingestion.chunking import PageAwareChunker
from tenderlens.ingestion.extractor import PdfTextExtractor
from tenderlens.ingestion.service import DocumentIngestionService
from tenderlens.ingestion.storage import FileSystemDocumentStorage
from tenderlens.qa.providers import (
    AnswerProvider,
    ExtractiveAnswerProvider,
    OllamaAnswerProvider,
    OpenAIAnswerProvider,
)
from tenderlens.qa.service import GroundedQuestionAnsweringService
from tenderlens.retrieval.embeddings import FastEmbedEmbeddingProvider
from tenderlens.retrieval.indexing import ChunkIndexingService
from tenderlens.retrieval.service import HybridRetrievalService

logger = structlog.get_logger(__name__)


def build_answer_provider(settings: Settings) -> AnswerProvider:
    if settings.llm_provider == "extractive":
        return ExtractiveAnswerProvider()
    if settings.llm_provider == "ollama":
        return OllamaAnswerProvider(
            str(settings.ollama_base_url),
            settings.llm_model,
            settings.llm_timeout_seconds,
        )
    if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value():
        raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
    return OpenAIAnswerProvider(
        settings.openai_api_key,
        settings.llm_model,
        settings.llm_timeout_seconds,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(
        log_level=resolved_settings.log_level,
        json_logs=resolved_settings.app_env != "development",
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = Database(resolved_settings.database_dsn)
        storage = FileSystemDocumentStorage(
            resolved_settings.upload_dir,
            resolved_settings.max_upload_size_bytes,
        )
        await storage.ensure_ready()
        ingestion_service = DocumentIngestionService(
            database.session_factory,
            storage,
            PdfTextExtractor(resolved_settings.max_pdf_pages),
            PageAwareChunker(
                resolved_settings.chunk_size_chars,
                resolved_settings.chunk_overlap_chars,
            ),
        )
        embedding_provider = FastEmbedEmbeddingProvider(
            resolved_settings.embedding_model,
            resolved_settings.embedding_dimensions,
            resolved_settings.embedding_cache_dir,
        )
        indexing_service = ChunkIndexingService(
            database.session_factory,
            embedding_provider,
        )
        retrieval_service = HybridRetrievalService(
            database.session_factory,
            embedding_provider,
            indexing_service,
            dense_k=resolved_settings.retrieval_dense_k,
            lexical_k=resolved_settings.retrieval_lexical_k,
            default_limit=resolved_settings.retrieval_final_k,
            rrf_k=resolved_settings.rrf_k,
        )
        qa_service = GroundedQuestionAnsweringService(
            retrieval_service,
            build_answer_provider(resolved_settings),
            evidence_limit=resolved_settings.qa_evidence_limit,
            max_claims=resolved_settings.qa_max_claims,
        )
        application.state.database = database
        application.state.ingestion_service = ingestion_service
        application.state.retrieval_service = retrieval_service
        application.state.qa_service = qa_service
        logger.info("application_started", environment=resolved_settings.app_env)
        try:
            yield
        finally:
            await database.close()
            logger.info("application_stopped")

    application = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        description=(
            "AI-assisted tender analysis with verifiable citations. "
            "The service does not provide legal advice."
        ),
        lifespan=lifespan,
    )
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in resolved_settings.cors_origins],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=resolved_settings.api_prefix)
    register_error_handlers(application)
    return application


app = create_app()
