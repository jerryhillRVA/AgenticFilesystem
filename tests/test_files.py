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


def test_upload_duplicate_replaces_existing(test_client):
    """Uploading a file with the same name/namespace/path reuses the file_id."""
    unique_ns = f"dedup-{uuid.uuid4().hex[:8]}"

    resp1 = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("report.txt", io.BytesIO(b"version 1"), "text/plain")},
        data={"namespace": unique_ns, "path": "docs"},
    )
    assert resp1.status_code == 200
    file_id_1 = resp1.json()["file_id"]

    resp2 = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("report.txt", io.BytesIO(b"version 2"), "text/plain")},
        data={"namespace": unique_ns, "path": "docs"},
    )
    assert resp2.status_code == 200
    file_id_2 = resp2.json()["file_id"]

    assert file_id_1 == file_id_2

    download = test_client.get(f"/v1/test-tenant/files/{file_id_1}")
    assert download.content == b"version 2"


def test_upload_duplicate_directory_no_duplicates(test_client):
    """After uploading same file 3 times, directory listing shows only one entry."""
    unique_ns = f"dedup-dir-{uuid.uuid4().hex[:8]}"

    for i in range(3):
        test_client.post(
            "/v1/test-tenant/files",
            files={"file": ("notes.txt", io.BytesIO(f"v{i}".encode()), "text/plain")},
            data={"namespace": unique_ns},
        )

    listing = test_client.get(f"/v1/test-tenant/dirs/?namespace={unique_ns}")
    file_entries = [e for e in listing.json()["entries"] if e["type"] == "file"]
    assert len(file_entries) == 1
    assert file_entries[0]["name"] == "notes.txt"


def test_upload_same_name_different_path_creates_new(test_client):
    """Same filename in different paths should create separate files."""
    unique_ns = f"diffpath-{uuid.uuid4().hex[:8]}"

    resp1 = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("readme.txt", io.BytesIO(b"path a"), "text/plain")},
        data={"namespace": unique_ns, "path": "a"},
    )
    resp2 = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("readme.txt", io.BytesIO(b"path b"), "text/plain")},
        data={"namespace": unique_ns, "path": "b"},
    )

    assert resp1.json()["file_id"] != resp2.json()["file_id"]


def test_upload_same_name_different_namespace_creates_new(test_client):
    """Same filename in different namespaces should create separate files."""
    ns1 = f"ns1-{uuid.uuid4().hex[:8]}"
    ns2 = f"ns2-{uuid.uuid4().hex[:8]}"

    resp1 = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("config.json", io.BytesIO(b"{}"), "application/json")},
        data={"namespace": ns1},
    )
    resp2 = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("config.json", io.BytesIO(b"{}"), "application/json")},
        data={"namespace": ns2},
    )

    assert resp1.json()["file_id"] != resp2.json()["file_id"]


def test_move_file_overwrites_existing_at_destination(test_client):
    """Moving a file to a path where same-named file exists overwrites it."""
    unique_ns = f"moveow-{uuid.uuid4().hex[:8]}"

    # Create file at destination
    resp_dest = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("data.txt", io.BytesIO(b"old data"), "text/plain")},
        data={"namespace": unique_ns, "path": "dest"},
    )
    dest_file_id = resp_dest.json()["file_id"]

    # Create file at source with same name
    resp_src = test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("data.txt", io.BytesIO(b"new data"), "text/plain")},
        data={"namespace": unique_ns, "path": "src"},
    )
    src_file_id = resp_src.json()["file_id"]

    # Move source to dest
    with patch("agentic_fs.api.files.get_vector_store") as mock_vs:
        mock_vs.return_value.update_file_path = MagicMock()
        move_resp = test_client.post(
            f"/v1/test-tenant/files/{src_file_id}/move",
            json={"new_path": "dest"},
        )
    assert move_resp.status_code == 200

    # Destination listing should have exactly one file
    listing = test_client.get(f"/v1/test-tenant/dirs/dest?namespace={unique_ns}")
    file_entries = [e for e in listing.json()["entries"] if e["type"] == "file"]
    assert len(file_entries) == 1
    assert file_entries[0]["file_id"] == src_file_id

    # Old destination file should be gone
    resp = test_client.get(f"/v1/test-tenant/files/{dest_file_id}")
    assert resp.status_code == 404


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
