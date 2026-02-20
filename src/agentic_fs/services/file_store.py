import os
import json
import shutil
from datetime import datetime, timezone

from agentic_fs.utils.ids import generate_file_id
from agentic_fs.utils.paths import sanitize_path_component
from agentic_fs.utils.mime import guess_mime_type
from agentic_fs.models.file import FileMetadata, DirEntry


class FileStore:
    def __init__(self, base_path: str = "/data"):
        self.base_path = base_path

    def _tenant_dir(self, tenant: str) -> str:
        return os.path.join(self.base_path, sanitize_path_component(tenant))

    def _file_dir(self, tenant: str, file_id: str) -> str:
        return os.path.join(self._tenant_dir(tenant), "files", file_id)

    def _namespace_dir(self, tenant: str, namespace: str, path: str = "") -> str:
        parts = [self._tenant_dir(tenant), "ns", sanitize_path_component(namespace)]
        if path:
            for p in path.strip("/").split("/"):
                if p:
                    parts.append(sanitize_path_component(p))
        return os.path.join(*parts)

    def save_file(
        self,
        tenant: str,
        content: bytes,
        filename: str,
        namespace: str = "default",
        path: str = "",
        tags: list[str] | None = None,
        custom_metadata: dict | None = None,
    ) -> FileMetadata:
        file_id = generate_file_id()
        file_dir = self._file_dir(tenant, file_id)
        os.makedirs(file_dir, exist_ok=True)

        # Write file content
        file_path = os.path.join(file_dir, filename)
        with open(file_path, "wb") as f:
            f.write(content)

        # Also create a link in the namespace directory
        ns_dir = self._namespace_dir(tenant, namespace, path)
        os.makedirs(ns_dir, exist_ok=True)

        now = datetime.now(timezone.utc).isoformat()
        mime_type = guess_mime_type(filename)

        metadata = FileMetadata(
            file_id=file_id,
            tenant_id=tenant,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(content),
            created_at=now,
            updated_at=now,
            tags=tags or [],
            custom_metadata=custom_metadata or {},
            indexing_status="pending",
            namespace=namespace,
            path=path,
        )

        # Write metadata sidecar
        meta_path = os.path.join(file_dir, f"{filename}.metadata")
        with open(meta_path, "w") as f:
            json.dump(metadata.model_dump(), f, indent=2)

        # Write a reference file in namespace dir for directory listing
        ref_path = os.path.join(ns_dir, f"{file_id}.ref")
        with open(ref_path, "w") as f:
            json.dump({"file_id": file_id, "filename": filename}, f)

        return metadata

    def get_file_content(self, tenant: str, file_id: str) -> tuple[bytes, str]:
        file_dir = self._file_dir(tenant, file_id)
        if not os.path.isdir(file_dir):
            raise FileNotFoundError(f"File {file_id} not found for tenant {tenant}")

        # Find the actual file (not .metadata, not .ref)
        for entry in os.listdir(file_dir):
            if not entry.endswith(".metadata") and not entry.endswith(".ref"):
                file_path = os.path.join(file_dir, entry)
                if os.path.isfile(file_path):
                    with open(file_path, "rb") as f:
                        return f.read(), entry

        raise FileNotFoundError(f"File content not found for {file_id}")

    def get_metadata(self, tenant: str, file_id: str) -> FileMetadata:
        file_dir = self._file_dir(tenant, file_id)
        if not os.path.isdir(file_dir):
            raise FileNotFoundError(f"File {file_id} not found for tenant {tenant}")

        for entry in os.listdir(file_dir):
            if entry.endswith(".metadata"):
                meta_path = os.path.join(file_dir, entry)
                with open(meta_path) as f:
                    return FileMetadata(**json.load(f))

        raise FileNotFoundError(f"Metadata not found for {file_id}")

    def update_metadata(self, tenant: str, file_id: str, **updates) -> FileMetadata:
        metadata = self.get_metadata(tenant, file_id)
        update_dict = metadata.model_dump()

        for key, value in updates.items():
            if value is not None:
                update_dict[key] = value

        update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated = FileMetadata(**update_dict)

        file_dir = self._file_dir(tenant, file_id)
        meta_path = os.path.join(file_dir, f"{updated.filename}.metadata")
        with open(meta_path, "w") as f:
            json.dump(updated.model_dump(), f, indent=2)

        return updated

    def delete_file(self, tenant: str, file_id: str) -> bool:
        file_dir = self._file_dir(tenant, file_id)
        if not os.path.isdir(file_dir):
            return False

        # Get metadata to find namespace ref
        try:
            metadata = self.get_metadata(tenant, file_id)
            ns_dir = self._namespace_dir(tenant, metadata.namespace, metadata.path)
            ref_path = os.path.join(ns_dir, f"{file_id}.ref")
            if os.path.exists(ref_path):
                os.remove(ref_path)
        except FileNotFoundError:
            pass

        shutil.rmtree(file_dir)
        return True

    def replace_file(self, tenant: str, file_id: str, content: bytes, filename: str) -> FileMetadata:
        metadata = self.get_metadata(tenant, file_id)
        file_dir = self._file_dir(tenant, file_id)

        # Remove old file content
        for entry in os.listdir(file_dir):
            entry_path = os.path.join(file_dir, entry)
            if not entry.endswith(".metadata") and not entry.endswith(".ref") and os.path.isfile(entry_path):
                os.remove(entry_path)
            elif entry.endswith(".metadata"):
                os.remove(entry_path)

        # Write new file
        file_path = os.path.join(file_dir, filename)
        with open(file_path, "wb") as f:
            f.write(content)

        now = datetime.now(timezone.utc).isoformat()
        updated = FileMetadata(
            file_id=file_id,
            tenant_id=tenant,
            filename=filename,
            mime_type=guess_mime_type(filename),
            size_bytes=len(content),
            created_at=metadata.created_at,
            updated_at=now,
            tags=metadata.tags,
            custom_metadata=metadata.custom_metadata,
            indexing_status="pending",
            namespace=metadata.namespace,
            path=metadata.path,
        )

        meta_path = os.path.join(file_dir, f"{filename}.metadata")
        with open(meta_path, "w") as f:
            json.dump(updated.model_dump(), f, indent=2)

        return updated

    def list_directory(self, tenant: str, namespace: str = "default", path: str = "") -> list[DirEntry]:
        ns_dir = self._namespace_dir(tenant, namespace, path)
        if not os.path.isdir(ns_dir):
            return []

        entries = []
        for item in sorted(os.listdir(ns_dir)):
            item_path = os.path.join(ns_dir, item)
            if os.path.isdir(item_path):
                entries.append(DirEntry(name=item, type="directory"))
            elif item.endswith(".ref"):
                with open(item_path) as f:
                    ref = json.load(f)
                try:
                    meta = self.get_metadata(tenant, ref["file_id"])
                    entries.append(DirEntry(
                        name=meta.filename,
                        type="file",
                        file_id=meta.file_id,
                        size_bytes=meta.size_bytes,
                        mime_type=meta.mime_type,
                        modified_at=meta.updated_at,
                    ))
                except FileNotFoundError:
                    pass

        return entries

    def get_file_path(self, tenant: str, file_id: str) -> str:
        file_dir = self._file_dir(tenant, file_id)
        if not os.path.isdir(file_dir):
            raise FileNotFoundError(f"File {file_id} not found")

        for entry in os.listdir(file_dir):
            if not entry.endswith(".metadata") and not entry.endswith(".ref"):
                full_path = os.path.join(file_dir, entry)
                if os.path.isfile(full_path):
                    return full_path

        raise FileNotFoundError(f"File content not found for {file_id}")
