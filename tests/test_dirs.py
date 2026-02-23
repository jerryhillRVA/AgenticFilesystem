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


def test_dir_entries_include_full_path(test_client):
    """DirEntry has computed path field for files and directories."""
    unique_ns = f"pathcheck-{uuid.uuid4().hex[:8]}"

    # Upload a file to a subdirectory
    test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("story.md", io.BytesIO(b"user story"), "text/plain")},
        data={"namespace": unique_ns, "path": "backlog"},
    )

    # List root — should see backlog directory
    response = test_client.get(f"/v1/test-tenant/dirs/?namespace={unique_ns}")
    assert response.status_code == 200
    entries = response.json()["entries"]
    dir_entry = [e for e in entries if e["type"] == "directory"][0]
    assert dir_entry["name"] == "backlog"
    assert dir_entry["path"] == "backlog"

    # List backlog — should see file with full path
    response = test_client.get(f"/v1/test-tenant/dirs/backlog?namespace={unique_ns}")
    assert response.status_code == 200
    entries = response.json()["entries"]
    file_entry = [e for e in entries if e["type"] == "file"][0]
    assert file_entry["name"] == "story.md"
    assert file_entry["path"] == "backlog/story.md"


def test_dir_nested_traversal(test_client):
    """Nested upload creates subdirectory entries with computed paths."""
    unique_ns = f"nested-{uuid.uuid4().hex[:8]}"

    test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("design.md", io.BytesIO(b"system design"), "text/plain")},
        data={"namespace": unique_ns, "path": "wiki/architecture"},
    )

    # Root shows wiki directory
    response = test_client.get(f"/v1/test-tenant/dirs/?namespace={unique_ns}")
    entries = response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["type"] == "directory"
    assert entries[0]["name"] == "wiki"
    assert entries[0]["path"] == "wiki"

    # wiki/ shows architecture directory
    response = test_client.get(f"/v1/test-tenant/dirs/wiki?namespace={unique_ns}")
    entries = response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["type"] == "directory"
    assert entries[0]["name"] == "architecture"
    assert entries[0]["path"] == "wiki/architecture"

    # wiki/architecture shows the file
    response = test_client.get(f"/v1/test-tenant/dirs/wiki/architecture?namespace={unique_ns}")
    entries = response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["type"] == "file"
    assert entries[0]["name"] == "design.md"
    assert entries[0]["path"] == "wiki/architecture/design.md"


def test_create_directory(test_client):
    """Create directory via API, then see it in listing."""
    unique_ns = f"createdir-{uuid.uuid4().hex[:8]}"

    response = test_client.post(
        "/v1/test-tenant/dirs",
        json={"namespace": unique_ns, "path": "sprints/sprint-3"},
    )
    assert response.status_code == 200
    assert response.json()["path"] == "sprints/sprint-3"

    # Root should show sprints directory
    response = test_client.get(f"/v1/test-tenant/dirs/?namespace={unique_ns}")
    entries = response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["name"] == "sprints"
    assert entries[0]["type"] == "directory"


def test_create_directory_nested(test_client):
    """Create nested directory — parent and child both appear."""
    unique_ns = f"nestdir-{uuid.uuid4().hex[:8]}"

    test_client.post(
        "/v1/test-tenant/dirs",
        json={"namespace": unique_ns, "path": "docs/api/v2"},
    )

    # docs/ shows api/
    response = test_client.get(f"/v1/test-tenant/dirs/docs?namespace={unique_ns}")
    entries = response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["name"] == "api"

    # docs/api/ shows v2/
    response = test_client.get(f"/v1/test-tenant/dirs/docs/api?namespace={unique_ns}")
    entries = response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["name"] == "v2"


def test_delete_empty_directory(test_client):
    """Delete empty directory succeeds and removes it from listing."""
    unique_ns = f"deldir-{uuid.uuid4().hex[:8]}"

    # Create a directory
    test_client.post(
        "/v1/test-tenant/dirs",
        json={"namespace": unique_ns, "path": "temp"},
    )

    # Verify it exists
    response = test_client.get(f"/v1/test-tenant/dirs/?namespace={unique_ns}")
    assert response.json()["total"] == 1

    # Delete it
    response = test_client.delete(f"/v1/test-tenant/dirs/temp?namespace={unique_ns}")
    assert response.status_code == 200

    # Verify it's gone
    response = test_client.get(f"/v1/test-tenant/dirs/?namespace={unique_ns}")
    assert response.json()["total"] == 0


def test_delete_nonempty_directory_fails(test_client):
    """Delete directory with files returns 409 Conflict."""
    unique_ns = f"nonempty-{uuid.uuid4().hex[:8]}"

    # Upload a file into the directory
    test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("file.txt", io.BytesIO(b"content"), "text/plain")},
        data={"namespace": unique_ns, "path": "occupied"},
    )

    # Try to delete — should fail
    response = test_client.delete(f"/v1/test-tenant/dirs/occupied?namespace={unique_ns}")
    assert response.status_code == 409
    assert "not empty" in response.json()["detail"]


def test_list_namespaces_empty(test_client):
    """Tenant with no namespaces returns empty list."""
    response = test_client.get("/v1/nonexistent-tenant/namespaces")
    assert response.status_code == 200
    data = response.json()
    assert data["namespaces"] == []
    assert data["total"] == 0


def test_list_namespaces_after_upload(test_client):
    """Uploading files to different namespaces shows them in listing."""
    ns1 = f"ns-{uuid.uuid4().hex[:8]}"
    ns2 = f"ns-{uuid.uuid4().hex[:8]}"
    test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("a.txt", io.BytesIO(b"a"), "text/plain")},
        data={"namespace": ns1},
    )
    test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("b.txt", io.BytesIO(b"b"), "text/plain")},
        data={"namespace": ns2},
    )
    response = test_client.get("/v1/test-tenant/namespaces")
    assert response.status_code == 200
    data = response.json()
    assert ns1 in data["namespaces"]
    assert ns2 in data["namespaces"]


def test_list_root_directory_no_path(test_client):
    """GET /v1/{tenant}/dirs (no path segment) lists namespace root."""
    unique_ns = f"root-{uuid.uuid4().hex[:8]}"
    test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("root.txt", io.BytesIO(b"content"), "text/plain")},
        data={"namespace": unique_ns},
    )
    # No trailing slash, no path segment
    response = test_client.get(f"/v1/test-tenant/dirs?namespace={unique_ns}")
    assert response.status_code == 200
    data = response.json()
    assert data["path"] == ""
    assert data["total"] >= 1
    names = [e["name"] for e in data["entries"]]
    assert "root.txt" in names


def test_recursive_listing(test_client):
    """recursive=true returns flat list of all nested entries."""
    unique_ns = f"recurse-{uuid.uuid4().hex[:8]}"
    test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("a.txt", io.BytesIO(b"a"), "text/plain")},
        data={"namespace": unique_ns},
    )
    test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("b.txt", io.BytesIO(b"b"), "text/plain")},
        data={"namespace": unique_ns, "path": "sub"},
    )
    test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("c.txt", io.BytesIO(b"c"), "text/plain")},
        data={"namespace": unique_ns, "path": "sub/deep"},
    )

    response = test_client.get(
        f"/v1/test-tenant/dirs?namespace={unique_ns}&recursive=true"
    )
    assert response.status_code == 200
    data = response.json()
    names = [e["name"] for e in data["entries"]]
    # All three files should appear
    assert "a.txt" in names
    assert "b.txt" in names
    assert "c.txt" in names
    # Directory entries should also appear
    paths = [e["path"] for e in data["entries"]]
    assert "sub" in paths
    assert "sub/deep" in paths


def test_recursive_false_default(test_client):
    """recursive defaults to false, only shows immediate children."""
    unique_ns = f"norecurse-{uuid.uuid4().hex[:8]}"
    test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("top.txt", io.BytesIO(b"top"), "text/plain")},
        data={"namespace": unique_ns},
    )
    test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("nested.txt", io.BytesIO(b"nested"), "text/plain")},
        data={"namespace": unique_ns, "path": "child"},
    )
    response = test_client.get(f"/v1/test-tenant/dirs?namespace={unique_ns}")
    assert response.status_code == 200
    data = response.json()
    names = [e["name"] for e in data["entries"]]
    assert "top.txt" in names
    assert "child" in names
    assert "nested.txt" not in names
