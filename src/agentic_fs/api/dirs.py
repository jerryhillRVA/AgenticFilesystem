from fastapi import APIRouter

from agentic_fs.dependencies import get_file_store
from agentic_fs.models.file import DirListResponse

router = APIRouter()


@router.get("/v1/{tenant}/dirs/{path:path}", response_model=DirListResponse)
async def list_directory(tenant: str, path: str = "", namespace: str = "default"):
    fs = get_file_store()
    entries = fs.list_directory(tenant, namespace=namespace, path=path)
    return DirListResponse(
        tenant=tenant,
        path=path,
        entries=entries,
        total=len(entries),
    )
