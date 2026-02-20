import io
import json
from unittest.mock import patch, MagicMock


# ── Text file tests ─────────────────────────────────────────────────────


def test_batch_retrieve_single_text_file(test_client):
    """Text file returns inline content, correct metadata, and download URL."""
    content = b"Hello, this is text content for batch test."
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("readme.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "default"},
    )
    file_id = resp.json()["file_id"]

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [file_id]},
    )
    assert batch_resp.status_code == 200
    data = batch_resp.json()
    assert data["total_requested"] == 1
    assert data["total_found"] == 1
    assert data["total_errors"] == 0

    entry = data["files"][0]
    assert entry["file_id"] == file_id
    assert entry["filename"] == "readme.txt"
    assert entry["mime_type"] == "text/plain"
    assert entry["size_bytes"] == len(content)
    assert entry["content_type"] == "text"
    assert entry["content"] == "Hello, this is text content for batch test."
    assert entry["truncated"] is False
    assert entry["error"] is None
    assert entry["download_url"].endswith(f"/v1/test-tenant/files/{file_id}")
    assert entry["indexing_status"] == "pending"


# ── JSON file tests ─────────────────────────────────────────────────────


def test_batch_retrieve_json_file(test_client):
    """JSON files have content_type='json' with parsed dict content."""
    payload = {"key": "value", "nested": {"a": 1}}
    content = json.dumps(payload).encode()
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("data.json", io.BytesIO(content), "application/json")},
        data={"namespace": "default"},
    )
    file_id = resp.json()["file_id"]

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [file_id]},
    )
    assert batch_resp.status_code == 200
    entry = batch_resp.json()["files"][0]
    assert entry["content_type"] == "json"
    assert entry["content"] == payload


def test_batch_retrieve_json_array(test_client):
    """JSON array files have content_type='json' with parsed list content."""
    payload = [1, 2, {"name": "test"}]
    content = json.dumps(payload).encode()
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("list.json", io.BytesIO(content), "application/json")},
        data={"namespace": "default"},
    )
    file_id = resp.json()["file_id"]

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [file_id]},
    )
    entry = batch_resp.json()["files"][0]
    assert entry["content_type"] == "json"
    assert entry["content"] == payload


def test_batch_retrieve_malformed_json(test_client):
    """Malformed JSON falls back to content_type='text'."""
    content = b'{"broken": true, missing_quote}'
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("bad.json", io.BytesIO(content), "application/json")},
        data={"namespace": "default"},
    )
    file_id = resp.json()["file_id"]

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [file_id]},
    )
    entry = batch_resp.json()["files"][0]
    assert entry["content_type"] == "text"
    assert isinstance(entry["content"], str)
    assert "broken" in entry["content"]


# ── Multiple files ───────────────────────────────────────────────────────


def test_batch_retrieve_multiple_files(test_client):
    """Batch returns entries in same order as requested file_ids."""
    ids = []
    for i in range(3):
        resp = test_client.post(
            "/v1/test-tenant/files",
            files={"file": (f"file{i}.txt", io.BytesIO(f"content {i}".encode()), "text/plain")},
            data={"namespace": "default"},
        )
        ids.append(resp.json()["file_id"])

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": ids},
    )
    data = batch_resp.json()
    assert data["total_requested"] == 3
    assert data["total_found"] == 3
    assert data["total_errors"] == 0
    assert [f["file_id"] for f in data["files"]] == ids
    for i, entry in enumerate(data["files"]):
        assert entry["content"] == f"content {i}"


# ── Error handling ───────────────────────────────────────────────────────


def test_batch_retrieve_file_not_found(test_client):
    """Non-existent file_id returns error entry; valid file still succeeds."""
    content = b"valid file"
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("valid.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "default"},
    )
    valid_id = resp.json()["file_id"]

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [valid_id, "nonexistent-id"]},
    )
    data = batch_resp.json()
    assert data["total_requested"] == 2
    assert data["total_found"] == 1
    assert data["total_errors"] == 1
    assert data["files"][0]["content_type"] == "text"
    assert data["files"][0]["content"] == "valid file"
    assert data["files"][1]["content_type"] == "error"
    assert "not found" in data["files"][1]["error"]


def test_batch_retrieve_all_not_found(test_client):
    """All missing IDs produce total_found=0 and total_errors=N."""
    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": ["bad-id-1", "bad-id-2", "bad-id-3"]},
    )
    data = batch_resp.json()
    assert data["total_requested"] == 3
    assert data["total_found"] == 0
    assert data["total_errors"] == 3
    for entry in data["files"]:
        assert entry["content_type"] == "error"


# ── Truncation ───────────────────────────────────────────────────────────


def test_batch_retrieve_with_max_text_chars(test_client):
    """Content is truncated and truncated=True when max_text_chars is set."""
    content = b"A" * 1000
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("long.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "default"},
    )
    file_id = resp.json()["file_id"]

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [file_id], "max_text_chars": 100},
    )
    entry = batch_resp.json()["files"][0]
    assert len(entry["content"]) == 100
    assert entry["truncated"] is True


def test_batch_retrieve_no_truncation_short_file(test_client):
    """Short file is not truncated even when max_text_chars is set."""
    content = b"Short"
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("short.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "default"},
    )
    file_id = resp.json()["file_id"]

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [file_id], "max_text_chars": 1000},
    )
    entry = batch_resp.json()["files"][0]
    assert entry["content"] == "Short"
    assert entry["truncated"] is False


# ── include_content=false ────────────────────────────────────────────────


def test_batch_retrieve_include_content_false(test_client):
    """Metadata-only mode: content is None but metadata fields are present."""
    content = b"metadata only test"
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("meta.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "default"},
    )
    file_id = resp.json()["file_id"]

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [file_id], "include_content": False},
    )
    entry = batch_resp.json()["files"][0]
    assert entry["content"] is None
    assert entry["filename"] == "meta.txt"
    assert entry["mime_type"] == "text/plain"
    assert entry["size_bytes"] == len(content)
    assert entry["download_url"].endswith(f"/v1/test-tenant/files/{file_id}")


# ── Download URL ─────────────────────────────────────────────────────────


def test_batch_retrieve_download_url_format(test_client):
    """Download URL is fully qualified with http:// and correct path."""
    content = b"url test"
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("url.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "default"},
    )
    file_id = resp.json()["file_id"]

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [file_id]},
    )
    url = batch_resp.json()["files"][0]["download_url"]
    assert url.startswith("http://")
    assert f"/v1/test-tenant/files/{file_id}" in url


def test_batch_retrieve_download_url_custom_base(test_client):
    """API_BASE_URL env var overrides auto-constructed URL."""
    content = b"custom base url"
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("base.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "default"},
    )
    file_id = resp.json()["file_id"]

    # Patch settings to use a custom base URL
    import agentic_fs.config
    original_base_url = agentic_fs.config.settings.api_base_url
    agentic_fs.config.settings.api_base_url = "https://api.example.com"
    try:
        batch_resp = test_client.post(
            "/v1/test-tenant/files/batch",
            json={"file_ids": [file_id]},
        )
        url = batch_resp.json()["files"][0]["download_url"]
        assert url == f"https://api.example.com/v1/test-tenant/files/{file_id}"
    finally:
        agentic_fs.config.settings.api_base_url = original_base_url


# ── Validation ───────────────────────────────────────────────────────────


def test_batch_retrieve_empty_file_ids(test_client):
    """Empty file_ids list returns 422."""
    resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": []},
    )
    assert resp.status_code == 422


def test_batch_retrieve_too_many_file_ids(test_client):
    """>100 file_ids (default limit) returns 422 with helpful message."""
    resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [f"id-{i}" for i in range(101)]},
    )
    assert resp.status_code == 422
    assert "BATCH_MAX_FILES" in resp.json()["detail"]


# ── NDJSON streaming ─────────────────────────────────────────────────────


def test_batch_retrieve_ndjson_stream(test_client):
    """stream=True returns NDJSON with one JSON line per file."""
    ids = []
    for i in range(2):
        resp = test_client.post(
            "/v1/test-tenant/files",
            files={"file": (f"stream{i}.txt", io.BytesIO(f"stream content {i}".encode()), "text/plain")},
            data={"namespace": "default"},
        )
        ids.append(resp.json()["file_id"])

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": ids, "stream": True},
    )
    assert batch_resp.status_code == 200
    assert "application/x-ndjson" in batch_resp.headers["content-type"]

    lines = batch_resp.text.strip().split("\n")
    assert len(lines) == 2
    for i, line in enumerate(lines):
        entry = json.loads(line)
        assert entry["file_id"] == ids[i]
        assert entry["content_type"] == "text"
        assert entry["content"] == f"stream content {i}"


# ── Binary file with mocked extractor ────────────────────────────────────


def test_batch_retrieve_binary_file(test_client):
    """Binary file returns extracted text and download_url."""
    content = b"%PDF-fake-binary-content"
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("doc.pdf", io.BytesIO(content), "application/pdf")},
        data={"namespace": "default"},
    )
    file_id = resp.json()["file_id"]

    # Mock the extractor used by the batch service
    from agentic_fs.services.extractor import ExtractedText
    from agentic_fs import dependencies

    mock_extractor = MagicMock()
    mock_extractor.extract.return_value = ExtractedText(
        text="Extracted PDF text content", method="mock", char_count=25
    )

    # Clear the batch service cache, provide a new one with the mock extractor
    dependencies.get_batch_service.cache_clear()
    original_get_batch = dependencies.get_batch_service.__wrapped__

    from agentic_fs.services.batch import BatchService

    def mock_get_batch():
        return BatchService(
            file_store=dependencies.get_file_store(),
            extractor=mock_extractor,
        )

    with patch.object(dependencies, "get_batch_service", mock_get_batch):
        batch_resp = test_client.post(
            "/v1/test-tenant/files/batch",
            json={"file_ids": [file_id]},
        )

    # Restore cache
    dependencies.get_batch_service.cache_clear()

    assert batch_resp.status_code == 200
    entry = batch_resp.json()["files"][0]
    assert entry["content_type"] == "binary"
    assert entry["content"] == "Extracted PDF text content"
    assert entry["download_url"].endswith(f"/v1/test-tenant/files/{file_id}")
    assert entry["mime_type"] == "application/pdf"


# ── Path in batch response ────────────────────────────────────────────


def test_batch_retrieve_includes_path(test_client):
    """Upload with path, verify path appears in batch response."""
    content = b"file in a subfolder"
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("nested.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "project", "path": "sprints/sprint-1"},
    )
    file_id = resp.json()["file_id"]

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [file_id]},
    )
    assert batch_resp.status_code == 200
    entry = batch_resp.json()["files"][0]
    assert entry["path"] == "sprints/sprint-1"
    assert entry["namespace"] == "project"


def test_batch_retrieve_path_defaults_empty(test_client):
    """Upload without path, verify path defaults to empty string."""
    content = b"root level file"
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("root.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "default"},
    )
    file_id = resp.json()["file_id"]

    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [file_id]},
    )
    assert batch_resp.status_code == 200
    entry = batch_resp.json()["files"][0]
    assert entry["path"] == ""
