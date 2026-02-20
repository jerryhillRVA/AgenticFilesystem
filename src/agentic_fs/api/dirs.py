from fastapi import APIRouter, HTTPException, Query

from agentic_fs.dependencies import get_file_store
from agentic_fs.models.file import DirListResponse, CreateDirectoryRequest

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


@router.post("/v1/{tenant}/dirs")
async def create_directory(tenant: str, body: CreateDirectoryRequest):
    """Create an empty directory at the specified path.

    Creates the directory (and any parent directories) within the given namespace.
    This is useful for pre-creating folder structures before uploading files
    (e.g. setting up `sprints/sprint-3/` before moving user stories into it).

    The operation is idempotent — creating an already-existing directory is a no-op.
    """
    fs = get_file_store()
    created_path = fs.create_directory(tenant, body.namespace, body.path)
    return {"message": "Directory created", "path": created_path, "namespace": body.namespace}


@router.delete("/v1/{tenant}/dirs/{path:path}")
async def delete_directory(
    tenant: str,
    path: str,
    namespace: str = Query(default="default", description="Namespace containing the directory."),
):
    """Delete an empty directory.

    Only empty directories can be deleted. If the directory contains files or
    subdirectories, the request will fail with a 409 Conflict status. Move or
    delete all contents first.

    **Tip:** Use `GET /v1/{tenant}/dirs/{path}` to check directory contents
    before attempting deletion.
    """
    fs = get_file_store()
    try:
        fs.delete_directory(tenant, namespace, path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Directory not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"message": "Directory deleted", "path": path}
