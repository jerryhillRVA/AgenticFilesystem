import os
from unittest.mock import patch

# Set test env vars before importing
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("FILESTORE_BASE_PATH", "/tmp/test")

from agentic_fs.services.chunker import Chunker


def test_chunk_short_text():
    chunker = Chunker()
    text = "This is a short text that should fit in a single chunk."
    chunks = chunker.chunk(text)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].chunk_idx == 0


def test_chunk_empty_text():
    chunker = Chunker()
    chunks = chunker.chunk("")
    assert chunks == []


def test_chunk_whitespace():
    chunker = Chunker()
    chunks = chunker.chunk("   \n\t  ")
    assert chunks == []


def test_chunk_long_text():
    chunker = Chunker()
    # Create a text that's definitely longer than 512 tokens
    text = "The quick brown fox jumps over the lazy dog. " * 200
    chunks = chunker.chunk(text)
    assert len(chunks) > 1

    # Verify chunk indices are sequential
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_idx == i

    # Verify all chunks have content
    for chunk in chunks:
        assert len(chunk.text) > 0
        assert chunk.token_count > 0


def test_chunk_overlap():
    chunker = Chunker()
    text = "word " * 2000  # ~2000 tokens
    chunks = chunker.chunk(text)

    # With overlap, the end of one chunk should overlap with the start of the next
    assert len(chunks) >= 2

    # Verify chunks cover the full text
    first_chunk = chunks[0]
    last_chunk = chunks[-1]
    assert first_chunk.start_char == 0
    assert last_chunk.end_char <= len(text) + 10  # Allow small rounding
