import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import Response

from agentic_fs.dependencies import get_file_store
from agentic_fs.models.file import (
    FileUploadResponse,
    FileMetadata,
    FileMetadataUpdate,
    FileLinkRequest,
)
from agentic_fs.worker.tasks import index_file, delete_vectors
from agentic_fs.services.pairing import PairingService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/{tenant}/files", response_model=FileUploadResponse)
async def upload_file(
    tenant: str,
    file: UploadFile = File(..., description="The file to upload (any type: text, JSON, PDF, DOCX, images, etc.)"),
    namespace: str = Form(default="default", description="Logical grouping for the file (e.g. 'docs', 'reports'). Used to filter searches."),
    path: str = Form(default="", description="Optional subdirectory path within the namespace."),
    tags: str = Form(default="", description="Comma-separated tags for categorization (e.g. 'report,quarterly,2024')."),
):
    """Upload a file and trigger async indexing.

    The file is stored immediately and a background job is enqueued to extract text,
    chunk it, generate embeddings, and index it in the vector store. The response
    includes a `file_id` that can be used with all other endpoints.

    **Important:** The file will not appear in search results until indexing completes.
    Check `GET /v1/{tenant}/search/status/{file_id}` and wait for `indexing_status: "indexed"`.
    Typical indexing time: 2-10 seconds for text files, longer for large binaries.
    """
    fs = get_file_store()
    content = await file.read()

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    metadata = fs.save_file(
        tenant=tenant,
        content=content,
        filename=file.filename or "unnamed",
        namespace=namespace,
        path=path,
        tags=tag_list,
    )

    # Enqueue indexing
    index_file.delay(tenant, metadata.file_id)

    return FileUploadResponse(
        file_id=metadata.file_id,
        filename=metadata.filename,
        mime_type=metadata.mime_type,
        size_bytes=metadata.size_bytes,
    )


@router.get("/v1/{tenant}/files/{file_id}")
async def download_file(tenant: str, file_id: str):
    """Download the raw file content by file_id.

    Returns the original binary content with appropriate Content-Type and
    Content-Disposition headers. For retrieving multiple files or getting
    inline text content, prefer `POST /v1/{tenant}/files/batch` instead.
    """
    fs = get_file_store()
    try:
        content, filename = fs.get_file_content(tenant, file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

    metadata = fs.get_metadata(tenant, file_id)
    return Response(
        content=content,
        media_type=metadata.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/v1/{tenant}/files/{file_id}/meta", response_model=FileMetadata)
async def get_file_metadata(tenant: str, file_id: str):
    """Get metadata for a single file without downloading its content.

    Returns file metadata including filename, MIME type, size, tags, namespace,
    and current indexing status. For metadata on multiple files at once, use the
    batch endpoint with `include_content: false`.
    """
    fs = get_file_store()
    try:
        return fs.get_metadata(tenant, file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")


@router.put("/v1/{tenant}/files/{file_id}", response_model=FileUploadResponse)
async def replace_file(
    tenant: str,
    file_id: str,
    file: UploadFile = File(..., description="The replacement file content."),
):
    """Replace a file's content while keeping the same file_id.

    The existing vectors are deleted and the file is re-indexed. The file_id
    remains stable, so any references to it (e.g. in agent memory or conversations)
    continue to work. Wait for re-indexing to complete before searching.
    """
    fs = get_file_store()
    content = await file.read()

    try:
        metadata = fs.replace_file(tenant, file_id, content, file.filename or "unnamed")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

    # Re-index
    delete_vectors.delay(tenant, file_id)
    index_file.delay(tenant, file_id)

    return FileUploadResponse(
        file_id=metadata.file_id,
        filename=metadata.filename,
        mime_type=metadata.mime_type,
        size_bytes=metadata.size_bytes,
        indexing_status="pending",
        message="File replaced. Re-indexing in progress.",
    )


@router.patch("/v1/{tenant}/files/{file_id}/meta", response_model=FileMetadata)
async def update_file_metadata(
    tenant: str,
    file_id: str,
    update: FileMetadataUpdate,
):
    """Update a file's tags or custom metadata without re-uploading.

    Only the provided fields are updated; omitted fields are left unchanged.
    This does not trigger re-indexing — tags and custom_metadata are stored in
    the sidecar metadata file only.
    """
    fs = get_file_store()
    try:
        kwargs = {}
        if update.tags is not None:
            kwargs["tags"] = update.tags
        if update.custom_metadata is not None:
            kwargs["custom_metadata"] = update.custom_metadata
        return fs.update_metadata(tenant, file_id, **kwargs)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")


@router.delete("/v1/{tenant}/files/{file_id}")
async def delete_file(tenant: str, file_id: str):
    """Delete a file and its associated vectors from the index.

    This permanently removes the file content, metadata, and all indexed vectors.
    The file_id will no longer be valid for any operations. This action cannot be undone.
    """
    fs = get_file_store()
    deleted = fs.delete_file(tenant, file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")

    # Delete vectors
    delete_vectors.delay(tenant, file_id)

    return {"message": "File deleted", "file_id": file_id}


@router.post("/v1/{tenant}/files/{file_id}/link")
async def link_files(tenant: str, file_id: str, body: FileLinkRequest):
    """Create a bidirectional link between two files (e.g. binary and its text transcript).

    Useful for pairing a binary file (PDF, image) with a separate text file that
    contains its human-readable content. Both files must already exist. The pairing
    is stored in both files' metadata via `pairing_id` and `paired_file_id`.
    """
    fs = get_file_store()
    pairing = PairingService(fs)

    try:
        pairing_id = pairing.link_files(tenant, file_id, body.target_file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="One or both files not found")

    return {"pairing_id": pairing_id, "file_a": file_id, "file_b": body.target_file_id}
