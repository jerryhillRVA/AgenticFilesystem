from fastapi import APIRouter, HTTPException, Query

from agentic_fs.dependencies import get_file_store, get_vector_store
from agentic_fs.models.admin import TenantListResponse, DeleteTenantResponse, DeduplicationResponse
from agentic_fs.services.dedup import DeduplicationService

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


@router.delete("/admin/tenants/{tenant}", response_model=DeleteTenantResponse)
async def delete_tenant(tenant: str):
    """Delete a tenant and all of its files and vectors.

    Removes every file from disk and purges all vectors from the index.
    This action is irreversible.
    """
    fs = get_file_store()
    vs = get_vector_store()

    try:
        files_deleted = fs.delete_tenant(tenant)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Tenant not found: {tenant}")

    vs.delete_by_tenant(tenant)

    return DeleteTenantResponse(
        tenant=tenant,
        files_deleted=files_deleted,
        vectors_deleted=True,
    )


@router.post("/admin/dedup", response_model=DeduplicationResponse)
async def deduplicate_files(
    tenant: str | None = Query(default=None, description="Scope to a single tenant. Omit to scan all."),
    dry_run: bool = Query(default=True, description="If true (default), report duplicates without deleting."),
):
    """Scan for and optionally remove duplicate files.

    A duplicate is defined as multiple files with the same (tenant, namespace, path, filename).
    When removing, the newest file (by updated_at) is kept. Always run with dry_run=true first.
    """
    fs = get_file_store()
    vs = get_vector_store() if not dry_run else None
    service = DeduplicationService(file_store=fs, vector_store=vs)
    result = service.cleanup_duplicates(tenant=tenant, dry_run=dry_run)

    return DeduplicationResponse(
        tenants_scanned=result.tenants_scanned,
        duplicate_groups_found=result.duplicates_found,
        files_removed=result.files_removed,
        dry_run=dry_run,
        errors=result.errors,
        groups=[
            {
                "tenant": g.tenant,
                "namespace": g.namespace,
                "path": g.path,
                "filename": g.filename,
                "file_ids": g.file_ids,
                "keep": sorted(
                    g.file_ids,
                    key=lambda fid: g.timestamps.get(fid, ""),
                    reverse=True,
                )[0],
            }
            for g in result.groups
        ],
    )
