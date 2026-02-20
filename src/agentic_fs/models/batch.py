from typing import Any, Literal

from pydantic import BaseModel, Field


class BatchRetrieveRequest(BaseModel):
    file_ids: list[str] = Field(
        ..., min_length=1,
        description="List of file_id values to retrieve. Typically these come from search result hits. Max limit is configurable via BATCH_MAX_FILES (default 100).",
    )
    include_content: bool = Field(
        default=True,
        description="Set to false for metadata-only retrieval (faster, no content loading). Useful when you only need file sizes, types, and download URLs.",
    )
    max_text_chars: int | None = Field(
        default=None, ge=100, le=500_000,
        description="Truncate text/binary content to this many characters. Use to limit response size when you only need a preview. Omit for full content.",
    )
    stream: bool = Field(
        default=False,
        description="If true, returns NDJSON (one JSON object per line) instead of a JSON envelope. Use for large result sets to start processing before the full response arrives.",
    )


class BatchFileEntry(BaseModel):
    file_id: str = Field(..., description="Unique file identifier.")
    filename: str = Field(..., description="Original filename as uploaded.")
    mime_type: str = Field(..., description="MIME type of the file (e.g. 'text/plain', 'application/pdf').")
    size_bytes: int = Field(..., description="File size in bytes.")
    namespace: str | None = Field(default=None, description="Namespace the file belongs to.")
    tags: list[str] = Field(default_factory=list, description="User-defined tags.")
    custom_metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary key-value metadata.")
    created_at: str = Field(..., description="ISO 8601 upload timestamp.")
    updated_at: str = Field(..., description="ISO 8601 last-update timestamp.")
    indexing_status: str = Field(..., description="pending | processing | indexed | failed.")
    content_type: Literal["text", "json", "binary", "error"] = Field(
        ...,
        description="Discriminator for the content field. 'text': raw text inline. 'json': parsed JSON (dict or list). 'binary': extracted text from binary files. 'error': file not found or extraction failed.",
    )
    content: str | dict | list | None = Field(
        default=None,
        description="Inline content. Type depends on content_type: string for text/binary, dict/list for json, None if include_content=false or on error.",
    )
    download_url: str = Field(..., description="Fully qualified URL to download the original file. Always present, even for text files.")
    truncated: bool = Field(default=False, description="True if content was truncated by max_text_chars.")
    error: str | None = Field(default=None, description="Error message if content_type is 'error' (e.g. 'File not found').")


class BatchRetrieveResponse(BaseModel):
    files: list[BatchFileEntry] = Field(..., description="One entry per requested file_id, in the same order as the request.")
    total_requested: int = Field(..., description="Number of file_ids in the request.")
    total_found: int = Field(..., description="Number of files successfully retrieved.")
    total_errors: int = Field(..., description="Number of files that could not be retrieved (not found, extraction failed, etc.).")
