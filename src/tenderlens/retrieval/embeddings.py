from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from anyio import Lock, to_thread
from fastembed import TextEmbedding


class EmbeddingError(Exception):
    """Raised when local embedding generation is unavailable or invalid."""


class EmbeddingProvider(Protocol):
    dimensions: int

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class FastEmbedEmbeddingProvider:
    def __init__(self, model_name: str, dimensions: int, cache_dir: Path) -> None:
        self.model_name = model_name
        self.dimensions = dimensions
        self.cache_dir = cache_dir.resolve()
        self._model: TextEmbedding | None = None
        self._load_lock = Lock()

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._embed(list(texts))

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self._embed([text])
        return vectors[0]

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        model = await self._get_model()
        try:
            vectors = await to_thread.run_sync(lambda: list(model.embed(texts)))
        except Exception as exc:
            raise EmbeddingError("Local embedding generation failed.") from exc

        result = [[float(value) for value in vector] for vector in vectors]
        if len(result) != len(texts):
            raise EmbeddingError("Embedding provider returned an unexpected vector count.")
        if any(len(vector) != self.dimensions for vector in result):
            raise EmbeddingError(
                f"Embedding dimension does not match configured value {self.dimensions}."
            )
        return result

    async def _get_model(self) -> TextEmbedding:
        if self._model is not None:
            return self._model
        async with self._load_lock:
            if self._model is None:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                try:
                    self._model = await to_thread.run_sync(
                        lambda: TextEmbedding(
                            model_name=self.model_name,
                            cache_dir=str(self.cache_dir),
                        )
                    )
                except Exception as exc:
                    raise EmbeddingError("Embedding model could not be loaded.") from exc
        return self._model
