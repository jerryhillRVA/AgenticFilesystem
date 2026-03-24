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
- **Node.js** >= 18 (for the CLI)
- An **OpenAI API key** (for embeddings and RAG)

## Installation

Install globally via npm:

```bash
npm install -g @jhill/agentic-filesystem
```

Or as a project dependency:

```bash
npm install @jhill/agentic-filesystem
```

## Quick Start (npm CLI)

1. **Initialize config in your project**
   ```bash
   afs init
   ```
   This creates an `afs.config.json` in the current directory.

2. **Set your OpenAI API key**

   ```bash
   export OPENAI_API_KEY=sk-...
   ```

   The config file (`afs.config.json`) is for port configuration only — it's safe to commit.

3. **Start all services**
   ```bash
   afs start
   ```

4. **Verify health**
   ```bash
   afs status
   ```

5. **Open API docs**
   ```
   http://localhost:8000/docs
   ```

## CLI Commands

| Command | Description |
|---------|-------------|
| `afs init` | Create `afs.config.json` in the current project |
| `afs start` | Start all services (builds images if needed) |
| `afs start --no-wait` | Start without waiting for health checks |
| `afs stop` | Stop all services |
| `afs status` | Show service status and health checks |
| `afs logs` | Tail logs from all services |
| `afs logs api` | Tail logs from a specific service (api\|worker\|qdrant\|redis\|tika) |
| `afs rebuild` | Force rebuild images and restart |
| `afs clean` | Wipe all data (volumes) and restart fresh |

## Config File (`afs.config.json`)

The `OPENAI_API_KEY` environment variable must be set in your shell before running `afs start`.

| Field | Default | Description |
|-------|---------|-------------|
| `apiPort` | `8000` | Host port for the FastAPI server |
| `qdrantPort` | `6333` | Host port for Qdrant |
| `redisPort` | `6379` | Host port for Redis |
| `tikaPort` | `9998` | Host port for Apache Tika |
| `filestorePath` | `"/data"` | File storage path inside the container |
| `apiBaseUrl` | _(auto)_ | Base URL for download links |

## Services

| Service | Default Port | Purpose |
|---------|-------------|---------|
| api | 8000 | FastAPI server |
| worker | — | Celery indexing worker |
| qdrant | 6333 | Vector database |
| redis | 6379 | Job queue broker |
| tika | 9998 | Text extraction |

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
| `DELETE` | `/admin/tenants/{tenant}` | Delete a tenant and all its data |

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

**Batch retrieve files:**
```bash
curl -X POST http://localhost:8000/v1/my-tenant/files/batch \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["FILE_ID_1", "FILE_ID_2", "FILE_ID_3"],
    "include_content": true
  }'
```

## Releasing

Bump version and publish to npm:

```bash
npm run release -- 1.0.0
```

This will:
1. Update the version in `package.json`
2. Run `npm install` to sync the lockfile
3. Publish to npm (`@jhill/agentic-filesystem`)
4. Create a git commit and tag (`v1.0.0`)

Push after releasing:
```bash
git push && git push --tags
```

## Development

### Quick Start (local dev)

```bash
cd AgenticFilesystem
cp .env.example .env    # Set your OPENAI_API_KEY
./dockerStart.sh --start
```

### Docker Management

```bash
./dockerStart.sh --start              # Build, start, wait for health
./dockerStart.sh --rebuild            # Force rebuild (no cache) and restart
./dockerStart.sh --stop               # Stop all services
./dockerStart.sh --logs               # Tail all logs
./dockerStart.sh --logs api           # Tail a specific service
./dockerStart.sh --status             # Show status + health checks
```

### Testing

**Unit tests** (no Docker required):
```bash
pip install -e ".[dev]"
pytest tests/ -v --ignore=tests/test_integration.py
```

**Full test suite** (requires Docker):
```bash
bash scripts/run_tests.sh
```

## Deduplication

Uploading a file with the same **filename**, **namespace**, and **path** as an existing file automatically replaces it — the `file_id` stays the same, the content is updated, and the file is re-indexed.

Moving a file to a destination where a same-named file already exists also overwrites the existing file.

For bulk cleanup of older duplicates:
```bash
# Dry run
curl -X POST "http://localhost:8000/admin/dedup?tenant=my-tenant&dry_run=true"
# Remove duplicates (keeps newest)
curl -X POST "http://localhost:8000/admin/dedup?tenant=my-tenant&dry_run=false"
```

## Configuration (Environment Variables)

For local development with `.env`:

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
| `API_BASE_URL` | _(auto)_ | Base URL for download links |
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
