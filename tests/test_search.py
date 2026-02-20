"""Search endpoint tests with mocked vector store and embedding service."""

import io
from unittest.mock import patch, MagicMock


def test_indexing_status(test_client):
    # Upload a file first
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("status.txt", io.BytesIO(b"test content"), "text/plain")},
        data={"namespace": "default"},
    )
    file_id = resp.json()["file_id"]

    response = test_client.get(f"/v1/test-tenant/search/status/{file_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == file_id
    assert data["indexing_status"] == "pending"


def test_indexing_status_not_found(test_client):
    response = test_client.get("/v1/test-tenant/search/status/nonexistent")
    assert response.status_code == 404


def test_semantic_search(test_client):
    mock_results = [
        {
            "file_id": "abc-123",
            "filename": "test.txt",
            "score": 0.95,
            "chunk_text": "relevant text chunk",
            "chunk_idx": 0,
            "namespace": "default",
        }
    ]

    with patch("agentic_fs.api.search.get_embedding_service") as mock_emb, \
         patch("agentic_fs.api.search.get_vector_store") as mock_vs:
        mock_emb.return_value.embed_query.return_value = [0.1] * 1536
        mock_vs.return_value.search_dense.return_value = mock_results

        response = test_client.post(
            "/v1/test-tenant/search/semantic",
            json={"query": "test query", "k": 5},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["filename"] == "test.txt"


def test_hybrid_search(test_client):
    mock_results = [
        {
            "file_id": "abc-456",
            "filename": "hybrid.txt",
            "score": 0.88,
            "chunk_text": "hybrid search result",
            "chunk_idx": 0,
            "namespace": "default",
        }
    ]

    with patch("agentic_fs.api.search.get_embedding_service") as mock_emb, \
         patch("agentic_fs.api.search.get_vector_store") as mock_vs:
        mock_emb.return_value.embed_query.return_value = [0.1] * 1536
        mock_vs.return_value.search_hybrid.return_value = mock_results

        response = test_client.post(
            "/v1/test-tenant/search/hybrid",
            json={"query": "hybrid test", "k": 5},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["filename"] == "hybrid.txt"
