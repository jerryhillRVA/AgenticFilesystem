from pydantic import BaseModel, Field


class TenantListResponse(BaseModel):
    tenants: list[str] = Field(..., description="List of tenant names found in the storage root.")
    total: int = Field(..., description="Number of tenants.")


class NamespaceListResponse(BaseModel):
    tenant: str = Field(..., description="Tenant whose namespaces are listed.")
    namespaces: list[str] = Field(..., description="List of namespace names found for this tenant.")
    total: int = Field(..., description="Number of namespaces.")
