import io


def test_list_tenants_empty(test_client):
    """Fresh store returns no tenants."""
    response = test_client.get("/admin/tenants")
    assert response.status_code == 200
    data = response.json()
    assert data["tenants"] == []
    assert data["total"] == 0


def test_list_tenants_after_upload(test_client):
    """Uploading files to different tenants makes them appear in listing."""
    test_client.post(
        "/v1/alpha/files",
        files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    test_client.post(
        "/v1/beta/files",
        files={"file": ("b.txt", io.BytesIO(b"world"), "text/plain")},
    )

    response = test_client.get("/admin/tenants")
    assert response.status_code == 200
    data = response.json()
    assert "alpha" in data["tenants"]
    assert "beta" in data["tenants"]
    assert data["total"] >= 2
