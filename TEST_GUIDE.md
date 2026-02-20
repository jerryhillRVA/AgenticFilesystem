# Agentic Filesystem — Test Guide

This guide walks through every feature of the system with copy-paste commands.

## Prerequisites

```bash
# Start the stack (if not already running)
./dockerStart.sh --start

# Verify everything is healthy
./dockerStart.sh --status
```

---

## 1. Upload Files

### Upload a text file
```bash
curl -s -X POST http://localhost:8000/v1/my-org/files \
  -F "file=@seed/files/docs/architecture.md" \
  -F "namespace=docs" \
  -F "tags=architecture,design"
```

Response:
```json
{
  "file_id": "abc-123...",
  "filename": "architecture.md",
  "mime_type": "text/markdown",
  "size_bytes": 1941,
  "indexing_status": "pending",
  "message": "File uploaded successfully. Indexing in progress."
}
```

### Upload a PDF
```bash
curl -s -X POST http://localhost:8000/v1/my-org/files \
  -F "file=@seed/files/pdfs/research-paper.pdf" \
  -F "namespace=pdfs" \
  -F "tags=research,paper"
```

### Upload a Word document
```bash
curl -s -X POST http://localhost:8000/v1/my-org/files \
  -F "file=@seed/files/office/report.docx" \
  -F "namespace=office" \
  -F "tags=report,quarterly"
```

### Upload a spreadsheet
```bash
curl -s -X POST http://localhost:8000/v1/my-org/files \
  -F "file=@seed/files/office/data.xlsx" \
  -F "namespace=office" \
  -F "tags=data,metrics"
```

### Upload any file from your computer
```bash
curl -s -X POST http://localhost:8000/v1/my-org/files \
  -F "file=@/path/to/your/file.pdf" \
  -F "namespace=uploads" \
  -F "tags=custom,test"
```

**Save the `file_id` from each response — you'll need it for the commands below.**

---

## 2. Check Indexing Status

After uploading, files are indexed asynchronously. Check status:

```bash
# Replace FILE_ID with the actual file_id from the upload response
curl -s http://localhost:8000/v1/my-org/search/status/FILE_ID
```

Status values:
- `pending` — waiting in queue
- `processing` — worker is extracting/embedding
- `indexed` — ready for search
- `failed` — check `indexing_error` for details

### Poll until indexed (bash one-liner)
```bash
FILE_ID="paste-your-file-id-here"
while true; do
  STATUS=$(curl -s http://localhost:8000/v1/my-org/search/status/$FILE_ID | python3 -c "import sys,json; print(json.load(sys.stdin)['indexing_status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "indexed" ] || [ "$STATUS" = "failed" ] && break
  sleep 2
done
```

---

## 3. Download a File

```bash
curl -s http://localhost:8000/v1/my-org/files/FILE_ID --output downloaded_file.pdf
```

---

## 4. Batch Retrieve Files

Retrieve metadata and content for multiple files in a single call. This is the most efficient way for agents to consume search results.

### Standard JSON response
```bash
curl -s -X POST http://localhost:8000/v1/my-org/files/batch \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["FILE_ID_1", "FILE_ID_2", "FILE_ID_3"]
  }' | python3 -m json.tool
```

Response contains a `files` array where each entry includes:
- Full metadata (filename, mime_type, size, tags, etc.)
- `content_type`: `"text"`, `"json"`, `"binary"`, or `"error"`
- `content`: inline text, parsed JSON, or extracted text for binaries
- `download_url`: fully qualified URL for direct file download
- `truncated`: whether content was capped

### NDJSON streaming (one JSON line per file)
```bash
curl -s -X POST http://localhost:8000/v1/my-org/files/batch \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["FILE_ID_1", "FILE_ID_2"],
    "stream": true
  }'
```

### Metadata-only (skip content)
```bash
curl -s -X POST http://localhost:8000/v1/my-org/files/batch \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["FILE_ID_1"],
    "include_content": false
  }' | python3 -m json.tool
```

### Truncated content
```bash
curl -s -X POST http://localhost:8000/v1/my-org/files/batch \
  -H "Content-Type: application/json" \
  -d '{
    "file_ids": ["FILE_ID_1"],
    "max_text_chars": 500
  }' | python3 -m json.tool
```

The max files per batch defaults to 100 and is configurable via the `BATCH_MAX_FILES` environment variable.

---

## 5. View File Metadata

```bash
curl -s http://localhost:8000/v1/my-org/files/FILE_ID/meta | python3 -m json.tool
```

Shows: filename, mime_type, size, tags, indexing_status, timestamps, etc.

---

## 6. Update Tags and Custom Metadata

```bash
curl -s -X PATCH http://localhost:8000/v1/my-org/files/FILE_ID/meta \
  -H "Content-Type: application/json" \
  -d '{
    "tags": ["reviewed", "approved", "q4-2024"],
    "custom_metadata": {
      "department": "engineering",
      "priority": "high",
      "reviewed_by": "jerry"
    }
  }' | python3 -m json.tool
```

---

## 7. List Files in a Directory

```bash
# List files in the "docs" namespace
curl -s "http://localhost:8000/v1/my-org/dirs/?namespace=docs" | python3 -m json.tool

# List files in the "office" namespace
curl -s "http://localhost:8000/v1/my-org/dirs/?namespace=office" | python3 -m json.tool
```

---

## 7b. Folder Organization

Organize files into meaningful folder structures — useful for project management, wikis, and any system with hierarchical content.

### Upload files to nested paths
```bash
# Create a project namespace with backlog and sprint folders
curl -s -X POST http://localhost:8000/v1/my-org/files \
  -F "file=@seed/files/docs/architecture.md" \
  -F "namespace=project" \
  -F "path=wiki/architecture"

curl -s -X POST http://localhost:8000/v1/my-org/files \
  -F "file=@seed/files/docs/meeting-notes.txt" \
  -F "namespace=project" \
  -F "path=sprints/sprint-1"
```

### Browse the directory tree
```bash
# Root of namespace — shows top-level folders
curl -s "http://localhost:8000/v1/my-org/dirs/?namespace=project" | python3 -m json.tool

# Drill into sprints/
curl -s "http://localhost:8000/v1/my-org/dirs/sprints?namespace=project" | python3 -m json.tool

# See files in sprint-1/
curl -s "http://localhost:8000/v1/my-org/dirs/sprints/sprint-1?namespace=project" | python3 -m json.tool
```

Each entry includes a `path` field showing the full path (e.g. `"sprints/sprint-1/meeting-notes.txt"`).

### Search within a path subtree
```bash
# Wait for indexing
sleep 10

# Search only within sprint-1
curl -s -X POST http://localhost:8000/v1/my-org/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "meeting notes",
    "k": 5,
    "path": "sprints/sprint-1"
  }' | python3 -m json.tool
```

Search results also include the `path` field, so agents know where each result lives.

### Create a directory before uploading
```bash
# Pre-create sprint-2 folder
curl -s -X POST http://localhost:8000/v1/my-org/dirs \
  -H "Content-Type: application/json" \
  -d '{"namespace": "project", "path": "sprints/sprint-2"}'

# Verify it exists
curl -s "http://localhost:8000/v1/my-org/dirs/sprints?namespace=project" | python3 -m json.tool
```

### Move files between folders
```bash
# Move a file from backlog to sprint-2 (replace FILE_ID with actual ID)
curl -s -X POST http://localhost:8000/v1/my-org/files/FILE_ID/move \
  -H "Content-Type: application/json" \
  -d '{"new_path": "sprints/sprint-2"}'

# Move a file to a different namespace
curl -s -X POST http://localhost:8000/v1/my-org/files/FILE_ID/move \
  -H "Content-Type: application/json" \
  -d '{"new_path": "archive", "new_namespace": "completed"}'
```

Moving a file updates its metadata, directory listings, and vector search payloads in-place — no re-indexing needed.

### Delete an empty directory
```bash
# First move/delete all files from the directory, then:
curl -s -X DELETE "http://localhost:8000/v1/my-org/dirs/sprints/sprint-1?namespace=project"

# Trying to delete a non-empty directory returns 409 Conflict
```

---

## 8. Semantic Search

Find documents by meaning, not just keywords:

```bash
curl -s -X POST http://localhost:8000/v1/my-org/search/semantic \
  -H "Content-Type: application/json" \
  -d '{
    "query": "how does the indexing pipeline work",
    "k": 5
  }' | python3 -m json.tool
```

### Search within a specific namespace
```bash
curl -s -X POST http://localhost:8000/v1/my-org/search/semantic \
  -H "Content-Type: application/json" \
  -d '{
    "query": "revenue and financial performance",
    "k": 3,
    "namespace": "office"
  }' | python3 -m json.tool
```

---

## 9. Hybrid Search (Dense + BM25)

Combines vector similarity with keyword matching for best results:

```bash
curl -s -X POST http://localhost:8000/v1/my-org/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "chunk size tokens overlap embedding model",
    "k": 5
  }' | python3 -m json.tool
```

Hybrid search is generally more accurate than pure semantic search,
especially when your query contains specific technical terms.

---

## 10. Find Similar Files

Given a file, find others with similar content:

```bash
# Replace FILE_ID with an actual file_id
curl -s "http://localhost:8000/v1/my-org/search/similar/FILE_ID?k=5" | python3 -m json.tool
```

---

## 11. RAG — Ask a Question

Ask a natural language question and get an answer with source citations:

```bash
curl -s -X POST http://localhost:8000/v1/my-org/search/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the key technical achievements mentioned in the documents?",
    "k": 5
  }' | python3 -m json.tool
```

### With a custom system prompt
```bash
curl -s -X POST http://localhost:8000/v1/my-org/search/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Summarize the architecture in 3 bullet points",
    "k": 5,
    "system_prompt": "You are a technical writer. Answer concisely in bullet points. Always cite which document the information came from."
  }' | python3 -m json.tool
```

---

## 12. Replace a File

Upload a new version of an existing file (triggers re-indexing):

```bash
curl -s -X PUT http://localhost:8000/v1/my-org/files/FILE_ID \
  -F "file=@/path/to/updated_file.txt"
```

---

## 13. Link Two Files (Binary-Text Pairing)

Manually pair a binary file with its text counterpart:

```bash
curl -s -X POST http://localhost:8000/v1/my-org/files/BINARY_FILE_ID/link \
  -H "Content-Type: application/json" \
  -d '{"target_file_id": "TEXT_FILE_ID"}'
```

---

## 14. Delete a File

Removes the file, its metadata, and all vectors from the search index:

```bash
curl -s -X DELETE http://localhost:8000/v1/my-org/files/FILE_ID
```

Verify it's gone:
```bash
curl -s http://localhost:8000/v1/my-org/files/FILE_ID
# Returns: {"detail": "File not found"}
```

---

## 15. Tenant Isolation Test

Prove that tenants can't see each other's data:

```bash
# Upload to tenant-a
curl -s -X POST http://localhost:8000/v1/tenant-a/files \
  -F "file=@seed/files/docs/architecture.md" \
  -F "namespace=docs"

# Upload to tenant-b
curl -s -X POST http://localhost:8000/v1/tenant-b/files \
  -F "file=@seed/files/docs/meeting-notes.txt" \
  -F "namespace=docs"

# Wait for indexing
sleep 10

# Search from tenant-a — should NOT find tenant-b's meeting notes
curl -s -X POST http://localhost:8000/v1/tenant-a/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "sprint planning meeting", "k": 5}'

# Search from tenant-b — should NOT find tenant-a's architecture doc
curl -s -X POST http://localhost:8000/v1/tenant-b/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "system architecture", "k": 5}'
```

---

## 16. Automated Seed & Demo

Upload all sample files and run demo searches in one command:

```bash
# Generate binary test files (PDFs, DOCX, XLSX, images)
python3 seed/create_binary_seeds.py

# Upload everything and run demo queries
python3 seed/upload_seed.py
```

---

## 17. Run Unit Tests

```bash
# Install dev dependencies (first time only)
pip install -e ".[dev]"

# Run all unit tests
python -m pytest tests/ -v
```

---

## 18. Interactive API Docs

Open your browser to the auto-generated Swagger UI:

```
http://localhost:8000/docs
```

You can try every endpoint interactively — upload files, run searches, etc.

---

## Quick Reference

| Action | Command |
|--------|---------|
| Start stack | `./dockerStart.sh --start` |
| Stop stack | `./dockerStart.sh --stop` |
| Rebuild | `./dockerStart.sh --rebuild` |
| View logs | `./dockerStart.sh --logs` |
| API logs only | `./dockerStart.sh --logs api` |
| Worker logs | `./dockerStart.sh --logs worker` |
| Service status | `./dockerStart.sh --status` |
| Run tests | `python -m pytest tests/ -v` |
| Seed data | `python3 seed/upload_seed.py` |
| API docs | `http://localhost:8000/docs` |
| Qdrant dashboard | `http://localhost:6333/dashboard` |

---

## Troubleshooting

**Files stuck in "pending" status:**
```bash
./dockerStart.sh --logs worker
# Check if the Celery worker is running and processing tasks
```

**API returning 500 errors:**
```bash
./dockerStart.sh --logs api
# Look for Python tracebacks
```

**Search returns no results:**
- Make sure files have `indexing_status: "indexed"` (check with `/search/status/{id}`)
- The indexing worker needs a few seconds to process each file
- Check worker logs for embedding errors (bad API key, rate limits)

**Reset everything and start fresh:**
```bash
./dockerStart.sh --stop
docker compose down -v    # Removes all data volumes
./dockerStart.sh --start
```
