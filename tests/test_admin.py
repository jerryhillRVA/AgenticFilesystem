import io
from unittest.mock import MagicMock, patch


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


def test_delete_tenant_not_found(test_client):
    """Deleting a nonexistent tenant returns 404."""
    with patch("agentic_fs.api.admin.get_vector_store") as mock_get_vs:
        mock_get_vs.return_value = MagicMock()
        response = test_client.delete("/admin/tenants/nonexistent")
        assert response.status_code == 404


def test_delete_tenant_success(test_client):
    """Deleting a tenant removes all its files and the tenant itself."""
    # Upload files to two tenants
    test_client.post(
        "/v1/deleteme/files",
        files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    test_client.post(
        "/v1/deleteme/files",
        files={"file": ("b.txt", io.BytesIO(b"world"), "text/plain")},
    )
    test_client.post(
        "/v1/keeper/files",
        files={"file": ("c.txt", io.BytesIO(b"keep"), "text/plain")},
    )

    # Verify both tenants exist
    tenants = test_client.get("/admin/tenants").json()["tenants"]
    assert "deleteme" in tenants
    assert "keeper" in tenants

    # Delete one tenant (mock VectorStore to avoid needing Qdrant)
    with patch("agentic_fs.api.admin.get_vector_store") as mock_get_vs:
        mock_vs = MagicMock()
        mock_get_vs.return_value = mock_vs

        response = test_client.delete("/admin/tenants/deleteme")
        assert response.status_code == 200
        data = response.json()
        assert data["tenant"] == "deleteme"
        assert data["files_deleted"] == 2
        assert data["vectors_deleted"] is True

        # Verify delete_by_tenant was called
        mock_vs.delete_by_tenant.assert_called_once_with("deleteme")

    # Verify it's gone but the other tenant remains
    tenants = test_client.get("/admin/tenants").json()["tenants"]
    assert "deleteme" not in tenants
    assert "keeper" in tenants
