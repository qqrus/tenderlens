import pytest

from tenderlens.domain.documents import ExtractedPage
from tenderlens.ingestion.chunking import PageAwareChunker


def test_chunks_keep_page_and_exact_character_offsets() -> None:
    pages = [
        ExtractedPage(
            page_number=1,
            text=("First requirement. Second requirement. Third requirement. " * 4).strip(),
        ),
        ExtractedPage(page_number=2, text="Budget: 1 000 000 RUB. Deadline: 20 August."),
    ]
    chunker = PageAwareChunker(chunk_size_chars=80, overlap_chars=12)

    chunks = chunker.chunk_pages(pages)

    assert {chunk.page_number for chunk in chunks} == {1, 2}
    for chunk in chunks:
        source = pages[chunk.page_number - 1].text
        assert chunk.text == source[chunk.start_char : chunk.end_char]
        assert chunk.end_char - chunk.start_char <= 80
    assert [chunk.chunk_index for chunk in chunks if chunk.page_number == 2] == [0]


def test_blank_page_produces_no_chunks() -> None:
    chunker = PageAwareChunker(chunk_size_chars=200, overlap_chars=20)

    assert chunker.chunk_page(ExtractedPage(page_number=1, text=" \n ")) == []


@pytest.mark.parametrize(
    ("size", "overlap"),
    [(0, 0), (100, -1), (100, 100), (100, 101)],
)
def test_invalid_chunk_configuration_is_rejected(size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        PageAwareChunker(size, overlap)
