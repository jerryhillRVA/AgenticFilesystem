# Agentic Filesystem — Claude Code Context

## Project Summary

This is the **Agentic Filesystem** — a tenant-scoped file storage and semantic search API. It is one subsystem of the larger Agentic Platform. The system allows AI agents (and other clients) to upload files, which are automatically indexed for semantic search via an async pipeline.

## Tech Stack

- **Python 3.12** with **FastAPI** (API server)
- **Celery** + **Redis** (async job queue for indexing)
- **Qdrant** (vector database — dense + BM25 sparse hybrid search)
- **Apache Tika** (binary file text extraction)
- **OpenAI API** (embeddings via `text-embedding-3-small`, RAG via `gpt-4o-mini`)
- **Docker Compose** (local development — 5 services)

## Key Architecture

### Data Flow
1. Client uploads file → `POST /v1/{tenant}/files`
2. File saved to local filesystem at `FILESTORE_BASE_PATH/{tenant}/files/{file_id}/`
3. Metadata saved as `.metadata` JSON sidecar alongside the file
4. Celery task `index_file` enqueued
5. Worker extracts text (Tika for binaries, direct read for text files)
6. Text chunked (512 tokens, 10% overlap) via `tiktoken`
7. Chunks embedded via OpenAI API
8. Vectors upserted to Qdrant with payload `{tenant_id, file_id, chunk_idx, ...}`

### Tenant Isolation
- All vectors share one Qdrant collection (`agentic_fs_chunks`)
- Every query includes `must` filter on `tenant_id`
- File storage is partitioned: `{base_path}/{tenant}/files/{file_id}/`

### File Storage
- No database — metadata is in `.metadata` JSON sidecar files
- Content: `{FILESTORE_BASE_PATH}/{tenant}/files/{file_id}/{filename}`
- Metadata: `{FILESTORE_BASE_PATH}/{tenant}/files/{file_id}/{filename}.metadata`
- Namespace ref: `{FILESTORE_BASE_PATH}/{tenant}/ns/{namespace}/{path}/{file_id}.ref`
- Ref files are JSON pointers: `{"file_id": "...", "filename": "..."}`
- Directory listings scan `.ref` files; actual content lives in `files/{file_id}/`

### Search Modes
- **Dense**: Cosine similarity on 1536-dim vectors
- **BM25 Sparse**: Term-frequency sparse vectors
- **Hybrid**: Qdrant Query API with RRF (Reciprocal Rank Fusion) combining both
- **RAG**: Hybrid search → context assembly → OpenAI chat completion

## Source Layout

```
src/agentic_fs/
├── main.py           # FastAPI app factory, lifespan (Qdrant collection init)
├── config.py         # Pydantic Settings, reads .env
├── dependencies.py   # DI via @lru_cache factories
├── api/
│   ├── router.py     # Aggregates file, dir, search, batch, admin routers
│   ├── files.py      # File CRUD: upload (with dedup), download, replace, delete, link, move
│   ├── batch.py      # Batch file retrieval (metadata + content)
│   ├── dirs.py       # Directory listing, create, delete, namespaces
│   ├── search.py     # Semantic, hybrid, similar, RAG, status
│   ├── admin.py      # Admin: list tenants, deduplication scan/cleanup
│   └── middleware.py  # Request logging
├── models/
│   ├── file.py       # FileMetadata, FileUploadResponse, DirEntry, etc.
│   ├── batch.py      # BatchRetrieveRequest/Response, BatchFileEntry
│   ├── search.py     # SearchRequest/Response, RAGRequest/Response
│   ├── admin.py      # TenantListResponse, DeduplicationResponse
│   └── common.py     # Shared models
├── services/
│   ├── file_store.py     # Filesystem abstraction (save, get, delete, list, find_existing_file)
│   ├── batch.py          # Batch retrieval logic (multi-file content fetch)
│   ├── dedup.py          # DeduplicationService: scan + cleanup duplicate files
│   ├── metadata_store.py # Read/write .metadata JSON files
│   ├── vector_store.py   # Qdrant client (collection setup, upsert, search, delete)
│   ├── embedding.py      # OpenAI embedding client with retry
│   ├── chunker.py        # tiktoken-based text chunking
│   ├── extractor.py      # Text extraction (Tika + Python fallbacks)
│   └── pairing.py        # Binary↔Text file pairing
├── worker/
│   ├── celery_app.py     # Celery config (Redis broker)
│   ├── tasks.py          # index_file, delete_vectors
│   └── pipeline.py       # 7-step indexing orchestration
└── utils/
    ├── ids.py            # UUID generation, deterministic point IDs
    ├── paths.py          # Path sanitization
    └── mime.py           # MIME type detection
```

## Key Patterns

- **Service layer**: All business logic in `services/`, API layer just calls services
- **Sidecar metadata**: No SQL database — `{filename}.metadata` JSON files
- **Deterministic point IDs**: `uuid5(file_id:chunk_idx)` — re-indexing is idempotent
- **Payload filtering**: Qdrant tenant isolation via `tenant_id` in every point payload
- **Async pipeline**: Celery tasks for indexing, decoupled from API response
- **Dedup on upload**: `FileStore.find_existing_file()` scans `.ref` files in the target namespace dir. If a match is found (same namespace + path + filename), the upload delegates to `replace_file()` — same `file_id`, content overwritten, re-indexed. No duplicate entries created.
- **Move-file overwrite**: Moving a file to a location where a same-named file already exists auto-deletes the conflicting file and its vectors before placing the moved file.
- **Admin dedup cleanup**: `DeduplicationService` walks all namespace directories, groups `.ref` files by `(tenant, namespace, path, filename)`, and deletes older copies. Available via `POST /admin/dedup`.
- **Module-level settings access**: `dependencies.py` uses `agentic_fs.config.settings` (not `from ... import settings`) so that `importlib.reload(config)` in tests works correctly. New modules should follow this pattern.
- **Test isolation**: `conftest.py` reloads `config`, clears all `@lru_cache` deps. When adding a new cached dependency, add its `cache_clear()` to both setup and teardown in conftest.

## Environment Variables

Key vars in `.env`:
- `FILESTORE_BASE_PATH` — where files are stored (default: `/data`)
- `QDRANT_URL` — Qdrant server (default: `http://qdrant:6333`)
- `REDIS_URL` — Redis for Celery (default: `redis://redis:6379/0`)
- `OPENAI_API_KEY` — required for embeddings and RAG
- `TIKA_URL` — Tika server (default: `http://tika:9998`)
- `API_BASE_URL` — base URL for download links (default: auto-built from host/port)
- `BATCH_MAX_FILES` — max files per batch retrieve request (default: `100`)

## Running

```bash
docker compose up -d --build    # Start everything
docker compose logs -f api      # Watch API logs
docker compose logs -f worker   # Watch worker logs
```

## Testing

```bash
pytest tests/ -v                               # Unit tests (mocked services)
pytest tests/test_integration.py -v            # Integration tests (needs Docker)
```

## Adding a New Extractor

1. Add extraction method in `services/extractor.py`
2. Add MIME type mapping in the `_fallback_extract()` dispatcher
3. Update `utils/mime.py` `needs_extraction()` if it's a binary format
4. Test with `tests/test_extractor.py`

## Adding a New Search Mode

1. Add Pydantic models in `models/search.py`
2. Add endpoint in `api/search.py`
3. Add query method in `services/vector_store.py`
4. Test with `tests/test_search.py`

## Adding a New Admin Endpoint

1. Add the endpoint function in `api/admin.py`
2. Add Pydantic request/response models in `models/admin.py`
3. The admin router is already registered in `api/router.py`
4. Test with `tests/test_admin.py`

## MVP Limitations (to be addressed later)

- No API key authentication or rate limiting
- No file versioning
- No presigned URL support
- No audio transcription (Whisper)
- Single Qdrant collection (no per-tenant collections)
