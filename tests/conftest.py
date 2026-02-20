import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def temp_file_store(tmp_path):
    """Provide a temporary file store directory."""
    return str(tmp_path)


@pytest.fixture
def mock_celery():
    """Mock Celery tasks so they don't actually enqueue."""
    with patch("agentic_fs.api.files.index_file") as mock_index, \
         patch("agentic_fs.api.files.delete_vectors") as mock_delete:
        mock_index.delay = MagicMock()
        mock_delete.delay = MagicMock()
        yield {"index_file": mock_index, "delete_vectors": mock_delete}


@pytest.fixture
def test_client(temp_file_store, mock_celery):
    """Create a test client with mocked services."""
    # Set env vars before any imports that read settings
    os.environ["FILESTORE_BASE_PATH"] = temp_file_store
    os.environ["QDRANT_URL"] = "http://localhost:6333"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["LOG_LEVEL"] = "warning"

    from agentic_fs import dependencies

    # Reset cached dependencies so they pick up new env vars
    dependencies.get_file_store.cache_clear()
    dependencies.get_metadata_store.cache_clear()
    dependencies.get_vector_store.cache_clear()
    dependencies.get_embedding_service.cache_clear()
    dependencies.get_chunker.cache_clear()
    dependencies.get_extractor.cache_clear()

    # Reload config to pick up new env vars
    import importlib
    import agentic_fs.config
    importlib.reload(agentic_fs.config)

    with patch("agentic_fs.main.VectorStore") as mock_vs_class:
        mock_vs_class.return_value.ensure_collection = MagicMock()

        # Need to reload main to pick up fresh settings
        import agentic_fs.main
        importlib.reload(agentic_fs.main)

        from agentic_fs.main import app
        client = TestClient(app)
        yield client

    # Clean up caches after test
    dependencies.get_file_store.cache_clear()
    dependencies.get_metadata_store.cache_clear()
    dependencies.get_vector_store.cache_clear()
    dependencies.get_embedding_service.cache_clear()
    dependencies.get_chunker.cache_clear()
    dependencies.get_extractor.cache_clear()
