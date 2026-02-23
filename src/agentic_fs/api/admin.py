from fastapi import APIRouter

from agentic_fs.dependencies import get_file_store
from agentic_fs.models.admin import TenantListResponse

router = APIRouter()


@router.get("/admin/tenants", response_model=TenantListResponse)
async def list_tenants():
    """List all tenants that have data in the filesystem.

    Scans the base storage directory for tenant directories. Each top-level
    directory in the storage root represents a tenant. Intended for
    troubleshooting and administration.
    """
    fs = get_file_store()
    tenants = fs.list_tenants()
    return TenantListResponse(tenants=tenants, total=len(tenants))
