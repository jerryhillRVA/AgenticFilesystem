import os
import json

from agentic_fs.models.file import FileMetadata


class MetadataStore:
    def __init__(self, base_path: str = "/data"):
        self.base_path = base_path

    def _file_dir(self, tenant: str, file_id: str) -> str:
        return os.path.join(self.base_path, tenant, "files", file_id)

    def get(self, tenant: str, file_id: str) -> FileMetadata | None:
        file_dir = self._file_dir(tenant, file_id)
        if not os.path.isdir(file_dir):
            return None

        for entry in os.listdir(file_dir):
            if entry.endswith(".metadata"):
                with open(os.path.join(file_dir, entry)) as f:
                    return FileMetadata(**json.load(f))
        return None

    def update(self, tenant: str, file_id: str, **fields) -> FileMetadata | None:
        metadata = self.get(tenant, file_id)
        if not metadata:
            return None

        data = metadata.model_dump()
        for key, value in fields.items():
            if value is not None:
                data[key] = value

        updated = FileMetadata(**data)
        file_dir = self._file_dir(tenant, file_id)
        meta_path = os.path.join(file_dir, f"{updated.filename}.metadata")
        with open(meta_path, "w") as f:
            json.dump(updated.model_dump(), f, indent=2)

        return updated
