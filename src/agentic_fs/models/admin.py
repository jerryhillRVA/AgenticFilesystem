from pydantic import BaseModel, Field


class TenantListResponse(BaseModel):
    tenants: list[str] = Field(..., description="List of tenant names found in the storage root.")
    total: int = Field(..., description="Number of tenants.")


class NamespaceListResponse(BaseModel):
    tenant: str = Field(..., description="Tenant whose namespaces are listed.")
    namespaces: list[str] = Field(..., description="List of namespace names found for this tenant.")
    total: int = Field(..., description="Number of namespaces.")


class DeleteTenantResponse(BaseModel):
    tenant: str = Field(..., description="Name of the deleted tenant.")
    files_deleted: int = Field(..., description="Number of files removed from disk.")
    vectors_deleted: bool = Field(..., description="Whether vectors were purged from the index.")


class DuplicateGroupInfo(BaseModel):
    tenant: str = Field(..., description="Tenant containing the duplicates.")
    namespace: str = Field(..., description="Namespace containing the duplicates.")
    path: str = Field(..., description="Path within the namespace.")
    filename: str = Field(..., description="The duplicated filename.")
    file_ids: list[str] = Field(..., description="All file_ids sharing this identity.")
    keep: str = Field(..., description="The file_id that will be (or was) kept.")


class ReindexResponse(BaseModel):
    tenant: str = Field(..., description="Tenant whose files were queued for re-indexing.")
    files_queued: int = Field(..., description="Number of files enqueued for re-indexing.")
    files_skipped: int = Field(..., description="Number of files skipped (already indexed, use force=true to override).")
    file_ids: list[str] = Field(default_factory=list, description="IDs of files that were queued.")
    errors: list[str] = Field(default_factory=list, description="Errors encountered during enumeration.")


class DeduplicationResponse(BaseModel):
    tenants_scanned: int = Field(..., description="Number of tenants scanned.")
    duplicate_groups_found: int = Field(..., description="Number of groups with duplicates.")
    files_removed: int = Field(..., description="Number of duplicate files removed (0 if dry_run).")
    dry_run: bool = Field(..., description="Whether this was a dry run.")
    errors: list[str] = Field(default_factory=list, description="Errors encountered.")
    groups: list[DuplicateGroupInfo] = Field(default_factory=list, description="Duplicate groups found.")
