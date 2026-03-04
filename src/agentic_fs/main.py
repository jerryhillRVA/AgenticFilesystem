import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from agentic_fs.config import settings
from agentic_fs.services.vector_store import VectorStore
from agentic_fs.api.router import api_router
from agentic_fs.api.middleware import log_request

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure Qdrant collection exists
    vs = VectorStore()
    vs.ensure_collection()
    yield


APP_DESCRIPTION = """\
Tenant-scoped file storage and semantic search API designed for AI agent workflows.

## Agent Quick-Start

**Recommended workflow: Upload → Wait for Indexing → Search → Batch Retrieve**

1. **Upload files** via `POST /v1/{tenant}/files` (multipart). Each upload returns a `file_id`
   and triggers async indexing. Text is extracted, chunked, and embedded automatically.
2. **Check indexing status** via `GET /v1/{tenant}/search/status/{file_id}`. Wait for
   `indexing_status: "indexed"` before searching. Newly uploaded files with status `"pending"`
   or `"processing"` will not appear in search results.
3. **Search** using the endpoint that best fits your need:
   - `semantic` — pure vector similarity. Best for conceptual/meaning-based queries.
   - `hybrid` — combines vector + BM25 keyword matching (recommended default). Best for
     queries mixing specific terms with conceptual intent.
   - `ask` (RAG) — returns a natural-language answer with cited sources. Use when the user
     needs a synthesized answer, not a list of documents.
   - `similar/{file_id}` — find files similar to a known file. Useful for deduplication or
     "more like this" workflows.
4. **Retrieve full file content** via `POST /v1/{tenant}/files/batch`. Pass the `file_id`
   values from search results to get metadata + inline content for all files in one call.
   This is much more efficient than fetching files individually.

## Key Concepts

- **Tenant isolation**: Every API path is scoped to `{tenant}`. Files and search results
  from one tenant are never visible to another.
- **Namespaces**: Organize files within a tenant (e.g. `docs`, `reports`, `code`). Searches
  can be filtered by namespace.
- **Paths / Folders**: Files can be organized into folder hierarchies within a namespace
  (e.g. `sprints/sprint-2/`, `wiki/architecture/`). Search results include the file's `path`,
  and you can scope searches to a subtree using the `path` parameter. Use the directory
  management endpoints to create folders, move files between paths, and clean up empty directories.
- **Indexing is async**: File uploads return immediately. Content extraction, chunking, and
  embedding happen in the background. Poll the status endpoint or use a reasonable delay
  (typically 2-10 seconds for text files, longer for large binaries).
- **Content types**: Text and JSON files are returned inline. Binary files (PDF, DOCX, etc.)
  have their text extracted and returned alongside a `download_url` for the original binary.

## Anti-Patterns

- **Don't fetch files one at a time** after search — use the batch endpoint instead.
- **Don't poll indexing status in a tight loop** — use exponential backoff or a fixed delay.
- **Don't use semantic search for exact keyword lookups** — use hybrid search instead.
- **Don't skip indexing status checks** — searching immediately after upload returns no results.
"""

OPENAPI_TAGS = [
    {
        "name": "admin",
        "description": (
            "Administrative and introspection endpoints for troubleshooting. "
            "List tenants, namespaces, and other system-level information."
        ),
    },
    {
        "name": "files",
        "description": (
            "Upload, download, replace, move, and delete files. Every file is stored under a "
            "tenant and assigned a unique `file_id`. Uploading a file automatically "
            "triggers async indexing (text extraction → chunking → embedding). Use the "
            "search status endpoint to confirm indexing is complete before searching. "
            "Files can be moved between paths/namespaces without re-indexing. "
            "For retrieving multiple files at once, prefer the batch endpoint over "
            "individual downloads."
        ),
    },
    {
        "name": "batch",
        "description": (
            "Retrieve metadata and inline content for multiple files in a single call. "
            "This is the recommended way to fetch file content after a search operation "
            "returns `file_id` values. Supports text, JSON, and binary files (with "
            "extracted text). Use `include_content: false` for metadata-only retrieval, "
            "or `stream: true` for NDJSON streaming of large result sets."
        ),
    },
    {
        "name": "search",
        "description": (
            "Search across indexed files using vector similarity, hybrid (vector + BM25), "
            "or RAG (retrieval-augmented generation). **Choosing a search mode:** Use "
            "`hybrid` as the default — it combines semantic understanding with keyword "
            "matching. Use `semantic` when the query is conceptual and exact terms don't "
            "matter. Use `ask` (RAG) when you need a synthesized natural-language answer "
            "with source citations. Use `similar/{file_id}` for 'more like this' discovery. "
            "All search endpoints accept an optional `path` parameter to scope results to a "
            "subtree (e.g. `path: 'sprints/sprint-2'`). All search endpoints return `file_id` "
            "references — pass these to the batch endpoint to retrieve full file content."
        ),
    },
    {
        "name": "directories",
        "description": (
            "Browse, create, and delete directories within a tenant and namespace. Useful "
            "for agents that need to discover available files without searching, set up "
            "folder structures before uploading files, or clean up empty directories. "
            "Returns file and directory entries with metadata including full paths."
        ),
    },
]

app = FastAPI(
    title="Agentic Filesystem",
    description=APP_DESCRIPTION,
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
)

app.add_middleware(BaseHTTPMiddleware, dispatch=log_request)
app.include_router(api_router)

admin_dir = Path(__file__).parent / "admin"
app.mount("/admin", StaticFiles(directory=str(admin_dir), html=True), name="admin")


@app.get("/health")
async def health():
    return {"status": "ok"}
