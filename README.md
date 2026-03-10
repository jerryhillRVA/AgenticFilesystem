# Agentic Filesystem

Tenant-scoped file storage and semantic search API. Upload files, automatically extract text and generate embeddings, then search using semantic similarity, hybrid (vector + BM25) search, or RAG-based Q&A.

## Architecture

```
Clients (Agents / Web UI / API)
        │
        ▼  HTTPS / REST
┌─────────────────────────┐
│     API Gateway         │
│  (FastAPI · port 8000)  │
├────────────┬────────────┤
│  File API  │ Search API │
└─────┬──────┴──────┬─────┘
      │             │
      ▼             ▼
┌──────────┐  ┌───────────┐
│ File     │  │ Vector    │
│ Store    │  │ Index     │
│ (local)  │  │ (Qdrant)  │
└──────────┘  └───────────┘
      ▲
      │
┌─────┴──────────────────┐
│   Indexing Pipeline     │
│ (Celery + Redis)        │
│  Extract → Chunk →      │
│  Embed → Upsert         │
└─────────────────────────┘
```

## Prerequisites

- **Docker** and **Docker Compose** v2
- An **OpenAI API key** (for embeddings and RAG)

## Quick Start

1. **Clone and configure**
   ```bash
   cd AgenticFilesystem
   cp .env.example .env
   # Edit .env and set your OPENAI_API_KEY
   ```

2. **Start all services**
   ```bash
   ./dockerStart.sh --start
   ```

   This builds images, starts all 5 services, waits for health checks, and displays status:

   | Service | Port | Purpose |
   |---------|------|---------|
   | api | 8000 | FastAPI server |
   | worker | — | Celery indexing worker |
   | qdrant | 6333 | Vector database |
   | redis | 6379 | Job queue broker |
   | tika | 9998 | Text extraction |

3. **Verify health**
   ```bash
   curl http://localhost:8000/health
   # {"status": "ok"}
   ```

4. **Open API docs**
   ```
   http://localhost:8000/docs
   ```

## API Reference

### File Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/{tenant}/files` | Upload file (multipart) |
| `GET` | `/v1/{tenant}/files/{id}` | Download file |
| `GET` | `/v1/{tenant}/files/{id}/meta` | Get metadata |
| `PUT` | `/v1/{tenant}/files/{id}` | Replace file |
| `PATCH` | `/v1/{tenant}/files/{id}/meta` | Update tags/metadata |
| `DELETE` | `/v1/{tenant}/files/{id}` | Delete file + vectors |
| `POST` | `/v1/{tenant}/files/{id}/move` | Move file to new path/namespace |
| `POST` | `/v1/{tenant}/files/{id}/link` | Pair binary↔text |
| `POST` | `/v1/{tenant}/files/batch` | Batch retrieve files (metadata + content) |

### Directory Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/{tenant}/dirs/{path}` | List directory contents (`?recursive=true` for flat tree) |
| `POST` | `/v1/{tenant}/dirs` | Create a directory |
| `DELETE` | `/v1/{tenant}/dirs/{path}` | Delete an empty directory |
| `GET` | `/v1/{tenant}/namespaces` | List all namespaces for a tenant |

### Search Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/{tenant}/search/semantic` | Vector similarity search |
| `POST` | `/v1/{tenant}/search/hybrid` | Vector + BM25 hybrid search |
| `GET` | `/v1/{tenant}/search/similar/{id}` | Find similar files |
| `POST` | `/v1/{tenant}/search/ask` | RAG: answer + sources |
| `GET` | `/v1/{tenant}/search/status/{id}` | Check indexing status |

### Admin Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/tenants` | List all tenants with data |
| `POST` | `/admin/dedup` | Scan/remove duplicate files (`?dry_run=true`) |

### Examples

**Upload a file to a path:**
```bash
curl -X POST http://localhost:8000/v1/my-tenant/files \
  -F "file=@document.pdf" \
  -F "namespace=project" \
  -F "path=sprints/sprint-2" \
  -F "tags=report,quarterly"
```

**Semantic search:**
```bash
curl -X POST http://localhost:8000/v1/my-tenant/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "system architecture design", "k": 5}'
```

**Search within a path subtree:**
```bash
curl -X POST http://localhost:8000/v1/my-tenant/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{"query": "user story acceptance criteria", "k": 5, "path": "sprints/sprint-2"}'
```

**RAG Q&A:**
```bash
curl -X POST http://localhost:8000/v1/my-tenant/search/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the key design decisions?", "k": 5}'
```

**Check indexing status:**
```bash
curl http://localhost:8000/v1/my-tenant/search/status/{file_id}
```

**Batch retrieve files** (get metadata + content for multiple files in one call):
```bash
curl -X POST http://localhost:8000/v1/my-tenant/files/batch \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["FILE_ID_1", "FILE_ID_2", "FILE_ID_3"],
    "include_content": true
  }'
```

Each file entry in the response includes metadata, a `content_type` discriminator (`text`, `json`, `binary`, or `error`), inline content (raw text, parsed JSON, or extracted text for binaries), a `path` showing the file's location, and a fully qualified `download_url`. Set `"stream": true` for NDJSON streaming.

**Move a file to a new path:**
```bash
curl -X POST http://localhost:8000/v1/my-tenant/files/{file_id}/move \
  -H "Content-Type: application/json" \
  -d '{"new_path": "sprints/sprint-3"}'
```

**Create a directory:**
```bash
curl -X POST http://localhost:8000/v1/my-tenant/dirs \
  -H "Content-Type: application/json" \
  -d '{"namespace": "project", "path": "sprints/sprint-4"}'
```

**Delete an empty directory:**
```bash
curl -X DELETE "http://localhost:8000/v1/my-tenant/dirs/sprints/sprint-4?namespace=project"
```

**Browse directory tree:**
```bash
curl http://localhost:8000/v1/my-tenant/dirs/?namespace=project
curl http://localhost:8000/v1/my-tenant/dirs/sprints/sprint-2?namespace=project
```

**Recursive directory listing** (flat list of all files and dirs):
```bash
curl "http://localhost:8000/v1/my-tenant/dirs/?namespace=project&recursive=true"
```

**List namespaces:**
```bash
curl http://localhost:8000/v1/my-tenant/namespaces
```

**List tenants:**
```bash
curl http://localhost:8000/admin/tenants
```

**Scan for duplicate files** (dry run — no deletions):
```bash
curl -X POST "http://localhost:8000/admin/dedup?tenant=my-tenant&dry_run=true"
```

**Remove duplicate files** (keeps newest, deletes older copies):
```bash
curl -X POST "http://localhost:8000/admin/dedup?tenant=my-tenant&dry_run=false"
```

## Deduplication

Uploading a file with the same **filename**, **namespace**, and **path** as an existing file automatically replaces it — the `file_id` stays the same, the content is updated, and the file is re-indexed. No duplicate entries are created.

Moving a file to a destination where a same-named file already exists also overwrites the existing file at that location.

If duplicates accumulated before this behavior was added, use the admin dedup endpoint to clean them up:

```bash
# 1. Scan for duplicates (dry run — reports without deleting)
curl -X POST "http://localhost:8000/admin/dedup?tenant=my-tenant&dry_run=true"

# 2. Review the response — check groups[].file_ids and groups[].keep
# 3. Remove duplicates (keeps newest by updated_at timestamp)
curl -X POST "http://localhost:8000/admin/dedup?tenant=my-tenant&dry_run=false"
```

## File Path Structure

All data is stored on the local filesystem — no SQL database. The layout:

```
{FILESTORE_BASE_PATH}/
└── {tenant}/
    ├── files/
    │   └── {file_id}/                  # One directory per file (keyed by UUID)
    │       ├── {filename}              # Actual file content
    │       └── {filename}.metadata     # JSON sidecar with FileMetadata
    │
    └── ns/                             # Namespace hierarchy
        └── {namespace}/
            └── {path}/                 # Nested subdirectories
                └── {file_id}.ref       # JSON pointer: {"file_id": "...", "filename": "..."}
```

- **File content** is stored in `files/{file_id}/` — the directory name is the UUID, not the filename
- **Metadata** is a `.metadata` JSON sidecar alongside the file content
- **`.ref` files** in namespace directories link the browsable directory tree to actual file storage
- Moving or renaming a file updates the `.ref` file location; the `files/{file_id}/` directory stays put

## Seed Data

Generate binary test files and upload seed data:

```bash
# Install deps locally (for seed script)
pip install httpx pypdf python-docx openpyxl Pillow

# Generate binary seed files (PDFs, DOCX, XLSX, images)
python seed/create_binary_seeds.py

# Upload all seed files and run demo searches
python seed/upload_seed.py
```

## Testing

**Unit tests** (no Docker required):
```bash
pip install -e ".[dev]"
pytest tests/ -v --ignore=tests/test_integration.py
```

**Full test suite** (requires Docker):
```bash
bash scripts/run_tests.sh
```

## Configuration

All configuration is via environment variables (`.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `FILESTORE_BASE_PATH` | `/data` | Root path for file storage |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant connection URL |
| `QDRANT_COLLECTION` | `agentic_fs_chunks` | Qdrant collection name |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `OPENAI_API_KEY` | — | OpenAI API key (required) |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | Chat model for RAG |
| `TIKA_URL` | `http://tika:9998` | Tika server URL |
| `CHUNK_SIZE_TOKENS` | `512` | Chunk size in tokens |
| `CHUNK_OVERLAP_PERCENT` | `10` | Chunk overlap percentage |
| `API_BASE_URL` | _(auto)_ | Base URL for download links (e.g. `https://api.example.com`) |
| `BATCH_MAX_FILES` | `100` | Max file IDs per batch retrieve request |

## Project Structure

```
src/agentic_fs/
├── main.py           # FastAPI app + lifespan
├── config.py         # Settings from .env
├── api/              # REST endpoints
│   ├── files.py      # File CRUD + dedup-on-upload
│   ├── batch.py      # Batch file retrieval
│   ├── search.py     # Search + RAG
│   ├── dirs.py       # Directory listing, create, delete
│   └── admin.py      # Admin: tenants, deduplication
├── services/         # Business logic
│   ├── file_store.py # Local filesystem ops + find_existing_file
│   ├── batch.py      # Batch retrieval logic
│   ├── dedup.py      # Duplicate file scan + cleanup
│   ├── vector_store.py # Qdrant integration
│   ├── embedding.py  # OpenAI embeddings
│   ├── chunker.py    # Text chunking
│   └── extractor.py  # Text extraction
└── worker/           # Async processing
    ├── celery_app.py # Celery config
    ├── pipeline.py   # Indexing pipeline
    └── tasks.py      # Task definitions
```

## Docker Management

Use `dockerStart.sh` to manage the Docker Compose stack:

```bash
./dockerStart.sh --start              # Build, start all services, wait for health checks
./dockerStart.sh --rebuild            # Force rebuild images (no cache) and restart
./dockerStart.sh --stop               # Stop all services
./dockerStart.sh --logs               # Tail logs from all services
./dockerStart.sh --logs api           # Tail logs from a specific service (api|worker|qdrant|redis|tika)
./dockerStart.sh --status             # Show service status and health checks
```

To also remove volumes and clear all data:
```bash
docker compose down -v
```
