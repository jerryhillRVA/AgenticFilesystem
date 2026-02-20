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
    file: UploadFile = File(...),
    namespace: str = Form(default="default"),
    path: str = Form(default=""),
    tags: str = Form(default=""),
):
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
    fs = get_file_store()
    try:
        return fs.get_metadata(tenant, file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")


@router.put("/v1/{tenant}/files/{file_id}", response_model=FileUploadResponse)
async def replace_file(
    tenant: str,
    file_id: str,
    file: UploadFile = File(...),
):
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
    fs = get_file_store()
    deleted = fs.delete_file(tenant, file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")

    # Delete vectors
    delete_vectors.delay(tenant, file_id)

    return {"message": "File deleted", "file_id": file_id}


@router.post("/v1/{tenant}/files/{file_id}/link")
async def link_files(tenant: str, file_id: str, body: FileLinkRequest):
    fs = get_file_store()
    pairing = PairingService(fs)

    try:
        pairing_id = pairing.link_files(tenant, file_id, body.target_file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="One or both files not found")

    return {"pairing_id": pairing_id, "file_a": file_id, "file_b": body.target_file_id}
