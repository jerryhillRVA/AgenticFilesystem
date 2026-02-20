"""Unit tests for the indexing pipeline."""

import os
from unittest.mock import patch, MagicMock

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("FILESTORE_BASE_PATH", "/tmp/test")


def test_pipeline_happy_path(tmp_path):
    """Test that the pipeline runs all 7 steps for a text file."""
    from agentic_fs.models.file import FileMetadata

    mock_metadata = FileMetadata(
        file_id="test-file-id",
        tenant_id="test-tenant",
        filename="test.txt",
        mime_type="text/plain",
        size_bytes=100,
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-01T00:00:00Z",
        namespace="default",
    )

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is test content for the indexing pipeline.")

    with patch("agentic_fs.worker.pipeline.FileStore") as MockFS, \
         patch("agentic_fs.worker.pipeline.Extractor") as MockExtractor, \
         patch("agentic_fs.worker.pipeline.Chunker") as MockChunker, \
         patch("agentic_fs.worker.pipeline.EmbeddingService") as MockEmbed, \
         patch("agentic_fs.worker.pipeline.VectorStore") as MockVS, \
         patch("agentic_fs.worker.pipeline.PairingService"):

        # Setup mocks
        fs = MockFS.return_value
        fs.get_metadata.return_value = mock_metadata
        fs.get_file_path.return_value = str(test_file)
        fs.update_metadata.return_value = mock_metadata

        from agentic_fs.services.extractor import ExtractedText
        extractor = MockExtractor.return_value
        extractor.extract.return_value = ExtractedText(
            text="Test content for indexing", method="direct_read", char_count=24
        )

        from agentic_fs.services.chunker import Chunk
        chunker = MockChunker.return_value
        chunker.chunk.return_value = [
            Chunk(text="Test content for indexing", chunk_idx=0, start_char=0, end_char=24, token_count=5)
        ]

        embed = MockEmbed.return_value
        embed.embed_texts.return_value = [[0.1] * 1536]

        vs = MockVS.return_value

        # Run pipeline
        from agentic_fs.worker.pipeline import run_indexing_pipeline
        run_indexing_pipeline("test-tenant", "test-file-id")

        # Verify all steps were called
        fs.get_metadata.assert_called_once()
        fs.get_file_path.assert_called_once()
        extractor.extract.assert_called_once()
        chunker.chunk.assert_called_once()
        embed.embed_texts.assert_called_once()
        vs.upsert_chunks.assert_called_once()

        # Verify status was updated to "indexed"
        update_calls = fs.update_metadata.call_args_list
        statuses = [c.kwargs.get("indexing_status") for c in update_calls if "indexing_status" in c.kwargs]
        assert "processing" in statuses
        assert "indexed" in statuses
