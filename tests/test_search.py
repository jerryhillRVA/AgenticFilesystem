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


def test_semantic_search_includes_path(test_client):
    """Path from vector store results appears in SearchHit response."""
    mock_results = [
        {
            "file_id": "path-123",
            "filename": "story.md",
            "score": 0.91,
            "chunk_text": "user story content",
            "chunk_idx": 0,
            "namespace": "project",
            "path": "sprints/sprint-2",
        }
    ]

    with patch("agentic_fs.api.search.get_embedding_service") as mock_emb, \
         patch("agentic_fs.api.search.get_vector_store") as mock_vs:
        mock_emb.return_value.embed_query.return_value = [0.1] * 1536
        mock_vs.return_value.search_dense.return_value = mock_results

        response = test_client.post(
            "/v1/test-tenant/search/semantic",
            json={"query": "user story", "k": 5},
        )

    assert response.status_code == 200
    hit = response.json()["results"][0]
    assert hit["path"] == "sprints/sprint-2"
    assert hit["namespace"] == "project"


def test_search_hit_path_defaults_empty(test_client):
    """Missing path in vector results defaults to empty string."""
    mock_results = [
        {
            "file_id": "no-path-123",
            "filename": "old.txt",
            "score": 0.85,
            "chunk_text": "some text",
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
            json={"query": "test", "k": 5},
        )

    assert response.status_code == 200
    hit = response.json()["results"][0]
    assert hit["path"] == ""


def test_semantic_search_with_path_filter(test_client):
    """Semantic search passes path filter to vector store."""
    with patch("agentic_fs.api.search.get_embedding_service") as mock_emb, \
         patch("agentic_fs.api.search.get_vector_store") as mock_vs:
        mock_emb.return_value.embed_query.return_value = [0.1] * 1536
        mock_vs.return_value.search_dense.return_value = []

        response = test_client.post(
            "/v1/test-tenant/search/semantic",
            json={"query": "test", "k": 5, "path": "sprints/sprint-2"},
        )

    assert response.status_code == 200
    mock_vs.return_value.search_dense.assert_called_once()
    call_kwargs = mock_vs.return_value.search_dense.call_args
    assert call_kwargs.kwargs.get("path") == "sprints/sprint-2" or \
           (len(call_kwargs.args) > 4 and call_kwargs.args[4] == "sprints/sprint-2")


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


def test_hybrid_search_with_path_filter(test_client):
    """Hybrid search passes path filter to vector store."""
    with patch("agentic_fs.api.search.get_embedding_service") as mock_emb, \
         patch("agentic_fs.api.search.get_vector_store") as mock_vs:
        mock_emb.return_value.embed_query.return_value = [0.1] * 1536
        mock_vs.return_value.search_hybrid.return_value = []

        response = test_client.post(
            "/v1/test-tenant/search/hybrid",
            json={"query": "test", "k": 5, "path": "wiki/architecture"},
        )

    assert response.status_code == 200
    mock_vs.return_value.search_hybrid.assert_called_once()
    call_kwargs = mock_vs.return_value.search_hybrid.call_args
    assert call_kwargs.kwargs.get("path") == "wiki/architecture" or \
           (len(call_kwargs.args) > 5 and call_kwargs.args[5] == "wiki/architecture")


def test_search_path_filter_defaults_none(test_client):
    """Omitting path from search request passes None (no path condition)."""
    with patch("agentic_fs.api.search.get_embedding_service") as mock_emb, \
         patch("agentic_fs.api.search.get_vector_store") as mock_vs:
        mock_emb.return_value.embed_query.return_value = [0.1] * 1536
        mock_vs.return_value.search_dense.return_value = []

        response = test_client.post(
            "/v1/test-tenant/search/semantic",
            json={"query": "test", "k": 5},
        )

    assert response.status_code == 200
    call_kwargs = mock_vs.return_value.search_dense.call_args
    assert call_kwargs.kwargs.get("path") is None


def test_rag_search_with_path_filter(test_client):
    """RAG ask passes path filter to hybrid search."""
    mock_results = [
        {
            "file_id": "rag-123",
            "filename": "policy.md",
            "score": 0.9,
            "chunk_text": "refund policy content",
            "chunk_idx": 0,
            "namespace": "docs",
            "path": "wiki",
        }
    ]

    mock_openai_response = MagicMock()
    mock_openai_response.choices = [MagicMock()]
    mock_openai_response.choices[0].message.content = "The refund policy states..."

    with patch("agentic_fs.api.search.get_embedding_service") as mock_emb, \
         patch("agentic_fs.api.search.get_vector_store") as mock_vs, \
         patch("agentic_fs.api.search.OpenAI") as mock_openai:
        mock_emb.return_value.embed_query.return_value = [0.1] * 1536
        mock_vs.return_value.search_hybrid.return_value = mock_results
        mock_openai.return_value.chat.completions.create.return_value = mock_openai_response

        response = test_client.post(
            "/v1/test-tenant/search/ask",
            json={"query": "What is the refund policy?", "path": "wiki"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["sources"][0]["path"] == "wiki"
    call_kwargs = mock_vs.return_value.search_hybrid.call_args
    assert call_kwargs.kwargs.get("path") == "wiki"
