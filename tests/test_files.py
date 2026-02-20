import io
import uuid
from unittest.mock import patch, MagicMock


def test_health(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_file(test_client):
    file_content = b"Hello, this is a test file with some content."
    response = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        data={"namespace": "default", "path": "", "tags": "test,unit"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["size_bytes"] == len(file_content)
    assert data["indexing_status"] == "pending"
    assert "file_id" in data


def test_download_file(test_client):
    # Upload first
    content = b"Download me please"
    upload_resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("download.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "default"},
    )
    file_id = upload_resp.json()["file_id"]

    # Download
    response = test_client.get(f"/v1/test-tenant/files/{file_id}")
    assert response.status_code == 200
    assert response.content == content


def test_get_metadata(test_client):
    content = b"Metadata test file"
    upload_resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("meta.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "docs", "tags": "meta,test"},
    )
    file_id = upload_resp.json()["file_id"]

    response = test_client.get(f"/v1/test-tenant/files/{file_id}/meta")
    assert response.status_code == 200
    meta = response.json()
    assert meta["filename"] == "meta.txt"
    assert meta["tenant_id"] == "test-tenant"
    assert "meta" in meta["tags"]
    assert meta["indexing_status"] == "pending"


def test_update_metadata(test_client):
    content = b"Update test"
    upload_resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("update.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "default"},
    )
    file_id = upload_resp.json()["file_id"]

    # Update tags
    response = test_client.patch(
        f"/v1/test-tenant/files/{file_id}/meta",
        json={"tags": ["updated", "new-tag"], "custom_metadata": {"priority": "high"}},
    )
    assert response.status_code == 200
    meta = response.json()
    assert "updated" in meta["tags"]
    assert meta["custom_metadata"]["priority"] == "high"


def test_delete_file(test_client):
    content = b"Delete me"
    upload_resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("delete.txt", io.BytesIO(content), "text/plain")},
        data={"namespace": "default"},
    )
    file_id = upload_resp.json()["file_id"]

    # Delete
    response = test_client.delete(f"/v1/test-tenant/files/{file_id}")
    assert response.status_code == 200

    # Verify it's gone
    response = test_client.get(f"/v1/test-tenant/files/{file_id}")
    assert response.status_code == 404


def test_replace_file(test_client):
    # Upload original
    upload_resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("original.txt", io.BytesIO(b"original"), "text/plain")},
        data={"namespace": "default"},
    )
    file_id = upload_resp.json()["file_id"]

    # Replace
    new_content = b"replaced content"
    response = test_client.put(
        f"/v1/test-tenant/files/{file_id}",
        files={"file": ("replaced.txt", io.BytesIO(new_content), "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "replaced.txt"

    # Download and verify
    download_resp = test_client.get(f"/v1/test-tenant/files/{file_id}")
    assert download_resp.content == new_content


def test_file_not_found(test_client):
    response = test_client.get("/v1/test-tenant/files/nonexistent-id")
    assert response.status_code == 404


def test_move_file_changes_path(test_client):
    """Move file to new path — metadata updated, old listing empty, new listing has file."""
    unique_ns = f"move-{uuid.uuid4().hex[:8]}"

    # Upload to backlog/
    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("story.md", io.BytesIO(b"user story"), "text/plain")},
        data={"namespace": unique_ns, "path": "backlog"},
    )
    file_id = resp.json()["file_id"]

    # Move to sprints/sprint-1
    with patch("agentic_fs.api.files.get_vector_store") as mock_vs:
        mock_vs.return_value.update_file_path = MagicMock()
        move_resp = test_client.post(
            f"/v1/test-tenant/files/{file_id}/move",
            json={"new_path": "sprints/sprint-1"},
        )

    assert move_resp.status_code == 200
    assert move_resp.json()["path"] == "sprints/sprint-1"

    # Old path should be empty
    old_listing = test_client.get(f"/v1/test-tenant/dirs/backlog?namespace={unique_ns}")
    assert old_listing.json()["total"] == 0

    # New path should have the file
    new_listing = test_client.get(f"/v1/test-tenant/dirs/sprints/sprint-1?namespace={unique_ns}")
    file_entries = [e for e in new_listing.json()["entries"] if e["type"] == "file"]
    assert len(file_entries) == 1
    assert file_entries[0]["file_id"] == file_id


def test_move_file_changes_namespace(test_client):
    """Move file to a different namespace."""
    src_ns = f"srcns-{uuid.uuid4().hex[:8]}"
    dst_ns = f"dstns-{uuid.uuid4().hex[:8]}"

    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("doc.txt", io.BytesIO(b"content"), "text/plain")},
        data={"namespace": src_ns},
    )
    file_id = resp.json()["file_id"]

    with patch("agentic_fs.api.files.get_vector_store") as mock_vs:
        mock_vs.return_value.update_file_path = MagicMock()
        move_resp = test_client.post(
            f"/v1/test-tenant/files/{file_id}/move",
            json={"new_path": "archive", "new_namespace": dst_ns},
        )

    assert move_resp.status_code == 200
    assert move_resp.json()["namespace"] == dst_ns
    assert move_resp.json()["path"] == "archive"

    # File should be in destination namespace
    new_listing = test_client.get(f"/v1/test-tenant/dirs/archive?namespace={dst_ns}")
    file_entries = [e for e in new_listing.json()["entries"] if e["type"] == "file"]
    assert len(file_entries) == 1
    assert file_entries[0]["file_id"] == file_id


def test_move_file_not_found(test_client):
    """Move nonexistent file returns 404."""
    with patch("agentic_fs.api.files.get_vector_store") as mock_vs:
        mock_vs.return_value.update_file_path = MagicMock()
        response = test_client.post(
            "/v1/test-tenant/files/nonexistent-id/move",
            json={"new_path": "somewhere"},
        )
    assert response.status_code == 404


def test_move_file_updates_batch_response(test_client):
    """After move, batch retrieval shows new path."""
    unique_ns = f"movebatch-{uuid.uuid4().hex[:8]}"

    resp = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("report.txt", io.BytesIO(b"quarterly report"), "text/plain")},
        data={"namespace": unique_ns, "path": "drafts"},
    )
    file_id = resp.json()["file_id"]

    # Move to published/
    with patch("agentic_fs.api.files.get_vector_store") as mock_vs:
        mock_vs.return_value.update_file_path = MagicMock()
        test_client.post(
            f"/v1/test-tenant/files/{file_id}/move",
            json={"new_path": "published"},
        )

    # Batch should reflect new path
    batch_resp = test_client.post(
        "/v1/test-tenant/files/batch",
        json={"file_ids": [file_id]},
    )
    entry = batch_resp.json()["files"][0]
    assert entry["path"] == "published"


def test_link_files(test_client):
    # Upload two files
    resp_a = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("file_a.txt", io.BytesIO(b"file a"), "text/plain")},
        data={"namespace": "default"},
    )
    resp_b = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("file_b.txt", io.BytesIO(b"file b"), "text/plain")},
        data={"namespace": "default"},
    )
    id_a = resp_a.json()["file_id"]
    id_b = resp_b.json()["file_id"]

    # Link them
    response = test_client.post(
        f"/v1/test-tenant/files/{id_a}/link",
        json={"target_file_id": id_b},
    )
    assert response.status_code == 200
    assert "pairing_id" in response.json()
