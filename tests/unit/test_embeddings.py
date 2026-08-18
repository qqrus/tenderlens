from pathlib import Path
from typing import Any, cast

import pytest

from tenderlens.retrieval.embeddings import EmbeddingError, FastEmbedEmbeddingProvider


class FakeModel:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors

    def embed(self, _texts: list[str]) -> list[list[float]]:
        return self.vectors[: len(_texts)]


@pytest.mark.asyncio
async def test_fastembed_provider_returns_plain_float_vectors(tmp_path: Path) -> None:
    provider = FastEmbedEmbeddingProvider("fake", dimensions=3, cache_dir=tmp_path)
    provider._model = cast(Any, FakeModel([[1, 2, 3], [4, 5, 6]]))

    vectors = await provider.embed_documents(["first", "second"])
    query_vector = await provider.embed_query("query")

    assert vectors == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    assert query_vector == [1.0, 2.0, 3.0]


@pytest.mark.asyncio
async def test_fastembed_provider_rejects_wrong_dimensions(tmp_path: Path) -> None:
    provider = FastEmbedEmbeddingProvider("fake", dimensions=3, cache_dir=tmp_path)
    provider._model = cast(Any, FakeModel([[1, 2]]))

    with pytest.raises(EmbeddingError, match="dimension"):
        await provider.embed_query("query")


@pytest.mark.asyncio
async def test_fastembed_provider_handles_empty_batch(tmp_path: Path) -> None:
    provider = FastEmbedEmbeddingProvider("fake", dimensions=3, cache_dir=tmp_path)

    assert await provider.embed_documents([]) == []
