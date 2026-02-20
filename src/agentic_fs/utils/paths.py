import os
import re


def sanitize_path_component(component: str) -> str:
    sanitized = re.sub(r"[^\w\-.]", "_", component)
    sanitized = sanitized.strip("._")
    return sanitized or "unnamed"


def build_storage_path(base_path: str, tenant: str, namespace: str, *parts: str) -> str:
    safe_tenant = sanitize_path_component(tenant)
    safe_namespace = sanitize_path_component(namespace)
    safe_parts = [sanitize_path_component(p) for p in parts if p]
    return os.path.join(base_path, safe_tenant, safe_namespace, *safe_parts)


def build_tenant_path(base_path: str, tenant: str) -> str:
    return os.path.join(base_path, sanitize_path_component(tenant))
