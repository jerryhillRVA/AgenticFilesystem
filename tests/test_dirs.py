import io
import uuid


def test_list_empty_directory(test_client):
    unique_ns = f"empty-{uuid.uuid4().hex[:8]}"
    response = test_client.get(f"/v1/test-tenant/dirs/?namespace={unique_ns}")
    assert response.status_code == 200
    data = response.json()
    assert data["entries"] == []
    assert data["total"] == 0


def test_list_directory_with_files(test_client):
    unique_ns = f"listing-{uuid.uuid4().hex[:8]}"

    # Upload files to the unique namespace
    for name in ["file1.txt", "file2.txt"]:
        test_client.post(
            "/v1/test-tenant/files",
            files={"file": (name, io.BytesIO(f"content of {name}".encode()), "text/plain")},
            data={"namespace": unique_ns},
        )

    response = test_client.get(f"/v1/test-tenant/dirs/?namespace={unique_ns}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    names = [e["name"] for e in data["entries"]]
    assert "file1.txt" in names
    assert "file2.txt" in names
