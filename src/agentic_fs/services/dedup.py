import os
import json
import logging
from dataclasses import dataclass, field

from agentic_fs.services.file_store import FileStore
from agentic_fs.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class DuplicateGroup:
    """A group of files with the same (tenant, namespace, path, filename)."""
    tenant: str
    namespace: str
    path: str
    filename: str
    file_ids: list[str] = field(default_factory=list)
    timestamps: dict[str, str] = field(default_factory=dict)  # file_id -> updated_at


@dataclass
class DeduplicationResult:
    """Summary of a deduplication run."""
    tenants_scanned: int = 0
    duplicates_found: int = 0
    files_removed: int = 0
    errors: list[str] = field(default_factory=list)
    groups: list[DuplicateGroup] = field(default_factory=list)


class DeduplicationService:
    def __init__(self, file_store: FileStore, vector_store: VectorStore | None = None):
        self.file_store = file_store
        self.vector_store = vector_store

    def scan_duplicates(self, tenant: str | None = None) -> DeduplicationResult:
        """Scan for duplicate files. If tenant is None, scan all tenants."""
        result = DeduplicationResult()
        tenants = [tenant] if tenant else self.file_store.list_tenants()
        result.tenants_scanned = len(tenants)

        for t in tenants:
            self._scan_tenant(t, result)

        return result

    def cleanup_duplicates(
        self, tenant: str | None = None, dry_run: bool = True
    ) -> DeduplicationResult:
        """Find and remove duplicate files, keeping the newest in each group."""
        result = self.scan_duplicates(tenant)

        if dry_run:
            for group in result.groups:
                result.files_removed += len(group.file_ids) - 1
            return result

        for group in result.groups:
            self._remove_duplicates_in_group(group, result)

        return result

    def _scan_tenant(self, tenant: str, result: DeduplicationResult):
        namespaces = self.file_store.list_namespaces(tenant)
        for namespace in namespaces:
            self._scan_namespace_dir(tenant, namespace, "", result)

    def _scan_namespace_dir(
        self, tenant: str, namespace: str, path: str, result: DeduplicationResult
    ):
        ns_dir = self.file_store._namespace_dir(tenant, namespace, path)
        if not os.path.isdir(ns_dir):
            return

        filename_to_refs: dict[str, list[dict]] = {}

        for item in os.listdir(ns_dir):
            item_path = os.path.join(ns_dir, item)

            if os.path.isdir(item_path):
                sub_path = f"{path}/{item}".strip("/") if path else item
                self._scan_namespace_dir(tenant, namespace, sub_path, result)
            elif item.endswith(".ref"):
                try:
                    with open(item_path) as f:
                        ref = json.load(f)
                    fn = ref.get("filename", "")
                    fid = ref.get("file_id", "")
                    if fn and fid:
                        filename_to_refs.setdefault(fn, []).append(ref)
                except (json.JSONDecodeError, OSError) as e:
                    result.errors.append(f"Error reading {item_path}: {e}")

        for filename, refs in filename_to_refs.items():
            if len(refs) <= 1:
                continue

            group = DuplicateGroup(
                tenant=tenant,
                namespace=namespace,
                path=path,
                filename=filename,
            )

            for ref in refs:
                fid = ref["file_id"]
                group.file_ids.append(fid)
                try:
                    metadata = self.file_store.get_metadata(tenant, fid)
                    group.timestamps[fid] = metadata.updated_at
                except FileNotFoundError:
                    group.timestamps[fid] = "1970-01-01T00:00:00+00:00"

            result.groups.append(group)
            result.duplicates_found += 1

    def _remove_duplicates_in_group(
        self, group: DuplicateGroup, result: DeduplicationResult
    ):
        sorted_ids = sorted(
            group.file_ids,
            key=lambda fid: group.timestamps.get(fid, ""),
            reverse=True,
        )

        keep_id = sorted_ids[0]
        remove_ids = sorted_ids[1:]

        logger.info(
            f"[Dedup] {group.tenant}/{group.namespace}/{group.path}/{group.filename}: "
            f"keeping {keep_id}, removing {len(remove_ids)} duplicates"
        )

        for fid in remove_ids:
            try:
                deleted = self.file_store.delete_file(group.tenant, fid)
                if deleted:
                    result.files_removed += 1

                if self.vector_store:
                    try:
                        self.vector_store.delete_by_file(group.tenant, fid)
                    except Exception as e:
                        result.errors.append(f"Failed to delete vectors for {fid}: {e}")
            except Exception as e:
                result.errors.append(f"Failed to delete file {fid}: {e}")
