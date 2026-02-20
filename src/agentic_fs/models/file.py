from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FileMetadata(BaseModel):
    file_id: str = Field(..., description="Unique identifier for this file. Use with all file/search/batch endpoints.")
    tenant_id: str = Field(..., description="Tenant this file belongs to.")
    filename: str = Field(..., description="Original filename as uploaded.")
    mime_type: str = Field(..., description="Detected MIME type (e.g. 'text/plain', 'application/pdf').")
    size_bytes: int = Field(..., description="File size in bytes.")
    created_at: str = Field(..., description="ISO 8601 timestamp of when the file was uploaded.")
    updated_at: str = Field(..., description="ISO 8601 timestamp of the last metadata or content update.")
    tags: list[str] = Field(default_factory=list, description="User-defined tags for categorization and filtering.")
    custom_metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary key-value metadata attached to the file.")
    indexing_status: str = Field(default="pending", description="One of: pending, processing, indexed, failed. File is searchable only when 'indexed'.")
    indexing_error: str | None = Field(default=None, description="Error details if indexing failed.")
    pairing_id: str | None = Field(default=None, description="ID linking this file to a paired file (e.g. binary + text transcript).")
    paired_file_id: str | None = Field(default=None, description="The file_id of the paired file, if any.")
    namespace: str = Field(default="default", description="Logical grouping (e.g. 'docs', 'reports'). Used to filter searches and organize files.")
    path: str = Field(default="", description="Subdirectory path within the namespace.")
    extracted_text_path: str | None = Field(default=None, description="Internal path to extracted text file, if applicable.")


class FileUploadResponse(BaseModel):
    file_id: str = Field(..., description="Unique identifier for the uploaded file. Save this for subsequent operations.")
    filename: str = Field(..., description="Filename as stored.")
    mime_type: str = Field(..., description="Detected MIME type.")
    size_bytes: int = Field(..., description="File size in bytes.")
    indexing_status: str = Field(default="pending", description="Always 'pending' on upload. Poll /search/status/{file_id} to track progress.")
    message: str = Field(default="File uploaded successfully. Indexing in progress.", description="Human-readable status message.")


class FileMetadataUpdate(BaseModel):
    tags: list[str] | None = Field(default=None, description="New tag list (replaces existing tags). Omit to leave unchanged.")
    custom_metadata: dict[str, Any] | None = Field(default=None, description="New custom metadata (replaces existing). Omit to leave unchanged.")


class DirEntry(BaseModel):
    name: str = Field(..., description="File or directory name.")
    type: str = Field(..., description="'file' or 'directory'.")
    file_id: str | None = Field(default=None, description="File ID (present only for type='file').")
    size_bytes: int | None = Field(default=None, description="File size (present only for type='file').")
    mime_type: str | None = Field(default=None, description="MIME type (present only for type='file').")
    modified_at: str | None = Field(default=None, description="Last modification timestamp.")


class DirListResponse(BaseModel):
    tenant: str = Field(..., description="Tenant scoping this listing.")
    path: str = Field(..., description="Directory path that was listed.")
    entries: list[DirEntry] = Field(..., description="Files and subdirectories at this path.")
    total: int = Field(..., description="Number of entries returned.")


class FileLinkRequest(BaseModel):
    target_file_id: str = Field(..., description="The file_id to link with. Creates a bidirectional pairing.")
