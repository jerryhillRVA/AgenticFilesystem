"""Unit tests for text extraction."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("FILESTORE_BASE_PATH", "/tmp/test")

from agentic_fs.services.extractor import Extractor


def test_extract_text_file(tmp_path):
    """Test direct text file reading."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, this is plain text content.")

    extractor = Extractor()
    result = extractor.extract(str(test_file), "text/plain")

    assert result.method == "direct_read"
    assert "Hello" in result.text
    assert result.char_count > 0


def test_extract_json_file(tmp_path):
    """Test JSON file reading as text."""
    test_file = tmp_path / "config.json"
    test_file.write_text('{"key": "value", "number": 42}')

    extractor = Extractor()
    result = extractor.extract(str(test_file), "application/json")

    assert result.method == "direct_read"
    assert '"key"' in result.text


def test_extract_markdown_file(tmp_path):
    """Test markdown file reading."""
    test_file = tmp_path / "readme.md"
    test_file.write_text("# Title\n\nSome markdown content with **bold** text.")

    extractor = Extractor()
    result = extractor.extract(str(test_file), "text/markdown")

    assert result.method == "direct_read"
    assert "# Title" in result.text
