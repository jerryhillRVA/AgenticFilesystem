import io
import uuid

import pytest

from agentic_fs.services.file_store import FileStore
from agentic_fs.services.dedup import DeduplicationService


def test_scan_finds_no_duplicates_when_clean(temp_file_store):
    """No duplicates reported for unique files."""
    fs = FileStore(base_path=temp_file_store)
    fs.save_file("t1", b"a", "a.txt", namespace="docs")
    fs.save_file("t1", b"b", "b.txt", namespace="docs")

    service = DeduplicationService(file_store=fs)
    result = service.scan_duplicates("t1")

    assert result.duplicates_found == 0
    assert len(result.groups) == 0


def test_scan_finds_duplicates(temp_file_store):
    """Two files with same name/namespace/path are detected as duplicates."""
    fs = FileStore(base_path=temp_file_store)
    fs.save_file("t1", b"v1", "report.txt", namespace="docs", path="q1")
    fs.save_file("t1", b"v2", "report.txt", namespace="docs", path="q1")

    service = DeduplicationService(file_store=fs)
    result = service.scan_duplicates("t1")

    assert result.duplicates_found == 1
    assert len(result.groups) == 1
    assert result.groups[0].filename == "report.txt"
    assert len(result.groups[0].file_ids) == 2


def test_cleanup_dry_run_does_not_delete(temp_file_store):
    """Dry run reports files_removed but does not actually delete."""
    fs = FileStore(base_path=temp_file_store)
    m1 = fs.save_file("t1", b"v1", "dup.txt", namespace="docs")
    m2 = fs.save_file("t1", b"v2", "dup.txt", namespace="docs")

    service = DeduplicationService(file_store=fs)
    result = service.cleanup_duplicates("t1", dry_run=True)

    assert result.files_removed == 1  # Would remove 1

    # Both files should still exist
    fs.get_metadata("t1", m1.file_id)
    fs.get_metadata("t1", m2.file_id)


def test_cleanup_removes_older_duplicate(temp_file_store):
    """Cleanup keeps newest and removes older file."""
    fs = FileStore(base_path=temp_file_store)
    m1 = fs.save_file("t1", b"v1", "dup.txt", namespace="docs")
    m2 = fs.save_file("t1", b"v2", "dup.txt", namespace="docs")

    # m2 is newer (created after m1)
    service = DeduplicationService(file_store=fs)
    result = service.cleanup_duplicates("t1", dry_run=False)

    assert result.files_removed == 1

    # Newer file should survive
    surviving = fs.get_metadata("t1", m2.file_id)
    assert surviving is not None

    # Older file should be gone
    with pytest.raises(FileNotFoundError):
        fs.get_metadata("t1", m1.file_id)


def test_different_paths_not_considered_duplicates(temp_file_store):
    """Same filename in different paths are not duplicates."""
    fs = FileStore(base_path=temp_file_store)
    fs.save_file("t1", b"a", "readme.txt", namespace="docs", path="a")
    fs.save_file("t1", b"b", "readme.txt", namespace="docs", path="b")

    service = DeduplicationService(file_store=fs)
    result = service.scan_duplicates("t1")

    assert result.duplicates_found == 0


def test_different_namespaces_not_considered_duplicates(temp_file_store):
    """Same filename in different namespaces are not duplicates."""
    fs = FileStore(base_path=temp_file_store)
    fs.save_file("t1", b"a", "readme.txt", namespace="ns1")
    fs.save_file("t1", b"b", "readme.txt", namespace="ns2")

    service = DeduplicationService(file_store=fs)
    result = service.scan_duplicates("t1")

    assert result.duplicates_found == 0


def test_dedup_endpoint_dry_run(test_client):
    """POST /admin/dedup with dry_run=true returns scan results."""
    unique_ns = f"dedup-ep-{uuid.uuid4().hex[:8]}"

    # Upload a file normally
    test_client.post(
        "/v1/test-tenant/files",
        files={"file": ("same.txt", io.BytesIO(b"v1"), "text/plain")},
        data={"namespace": unique_ns},
    )

    # Create a duplicate by calling FileStore.save_file directly (bypasses dedup logic)
    from agentic_fs.dependencies import get_file_store
    fs = get_file_store()
    fs.save_file("test-tenant", b"v2", "same.txt", namespace=unique_ns)

    response = test_client.post(f"/admin/dedup?tenant=test-tenant&dry_run=true")
    assert response.status_code == 200
    data = response.json()
    assert data["dry_run"] is True
    assert data["duplicate_groups_found"] >= 1
    assert data["files_removed"] >= 1

    # Verify groups contain useful info
    matching = [g for g in data["groups"] if g["filename"] == "same.txt" and g["namespace"] == unique_ns]
    assert len(matching) == 1
    assert len(matching[0]["file_ids"]) == 2
    assert matching[0]["keep"] in matching[0]["file_ids"]
