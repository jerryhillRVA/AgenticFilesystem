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
   docker compose up -d --build
   ```

   This starts 5 services:
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
| `GET` | `/v1/{tenant}/dirs/{path}` | List directory |
| `POST` | `/v1/{tenant}/files/{id}/link` | Pair binary↔text |

### Search Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/{tenant}/search/semantic` | Vector similarity search |
| `POST` | `/v1/{tenant}/search/hybrid` | Vector + BM25 hybrid search |
| `GET` | `/v1/{tenant}/search/similar/{id}` | Find similar files |
| `POST` | `/v1/{tenant}/search/ask` | RAG: answer + sources |
| `GET` | `/v1/{tenant}/search/status/{id}` | Check indexing status |

### Examples

**Upload a file:**
```bash
curl -X POST http://localhost:8000/v1/my-tenant/files \
  -F "file=@document.pdf" \
  -F "namespace=docs" \
  -F "tags=report,quarterly"
```

**Semantic search:**
```bash
curl -X POST http://localhost:8000/v1/my-tenant/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "system architecture design", "k": 5}'
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

## Project Structure

```
src/agentic_fs/
├── main.py           # FastAPI app + lifespan
├── config.py         # Settings from .env
├── api/              # REST endpoints
│   ├── files.py      # File CRUD
│   ├── search.py     # Search + RAG
│   └── dirs.py       # Directory listing
├── services/         # Business logic
│   ├── file_store.py # Local filesystem ops
│   ├── vector_store.py # Qdrant integration
│   ├── embedding.py  # OpenAI embeddings
│   ├── chunker.py    # Text chunking
│   └── extractor.py  # Text extraction
└── worker/           # Async processing
    ├── celery_app.py # Celery config
    ├── pipeline.py   # Indexing pipeline
    └── tasks.py      # Task definitions
```

## Stopping Services

```bash
docker compose down        # Stop containers
docker compose down -v     # Stop + remove volumes (clears all data)
```
