import io


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
