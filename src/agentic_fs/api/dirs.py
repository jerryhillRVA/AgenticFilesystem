from fastapi import APIRouter

from agentic_fs.dependencies import get_file_store
from agentic_fs.models.file import DirListResponse

router = APIRouter()


@router.get("/v1/{tenant}/dirs/{path:path}", response_model=DirListResponse)
async def list_directory(tenant: str, path: str = "", namespace: str = "default"):
    """List files and directories at a given path within a namespace.

    Use this to browse the file hierarchy when you need to discover available files
    without performing a search. Useful for agents building file-tree views or
    enumerating contents of a specific namespace or directory.

    Pass an empty path to list the root of the namespace. Subdirectory entries
    can be traversed by appending their `name` to the path.
    """
    fs = get_file_store()
    entries = fs.list_directory(tenant, namespace=namespace, path=path)
    return DirListResponse(
        tenant=tenant,
        path=path,
        entries=entries,
        total=len(entries),
    )
