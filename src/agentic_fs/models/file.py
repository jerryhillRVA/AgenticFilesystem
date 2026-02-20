from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FileMetadata(BaseModel):
    file_id: str
    tenant_id: str
    filename: str
    mime_type: str
    size_bytes: int
    created_at: str
    updated_at: str
    tags: list[str] = Field(default_factory=list)
    custom_metadata: dict[str, Any] = Field(default_factory=dict)
    indexing_status: str = "pending"  # pending | processing | indexed | failed
    indexing_error: str | None = None
    pairing_id: str | None = None
    paired_file_id: str | None = None
    namespace: str = "default"
    path: str = ""
    extracted_text_path: str | None = None


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    mime_type: str
    size_bytes: int
    indexing_status: str = "pending"
    message: str = "File uploaded successfully. Indexing in progress."


class FileMetadataUpdate(BaseModel):
    tags: list[str] | None = None
    custom_metadata: dict[str, Any] | None = None


class DirEntry(BaseModel):
    name: str
    type: str  # "file" | "directory"
    file_id: str | None = None
    size_bytes: int | None = None
    mime_type: str | None = None
    modified_at: str | None = None


class DirListResponse(BaseModel):
    tenant: str
    path: str
    entries: list[DirEntry]
    total: int


class FileLinkRequest(BaseModel):
    target_file_id: str
