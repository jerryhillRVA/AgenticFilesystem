# Agentic Filesystem API Reference

## Base URL
```
http://localhost:8000/v1/{tenant}
```

## File Operations

### Upload File
```
POST /v1/{tenant}/files
Content-Type: multipart/form-data

Parameters:
- file: The file to upload (required)
- namespace: Logical grouping (default: "default")
- path: Sub-path within namespace
- tags: Comma-separated tags

Response: { file_id, filename, mime_type, size_bytes, indexing_status }
```

### Download File
```
GET /v1/{tenant}/files/{id}
Response: Binary file content with appropriate Content-Type
```

### Get Metadata
```
GET /v1/{tenant}/files/{id}/meta
Response: Complete file metadata including indexing status
```

### Replace File
```
PUT /v1/{tenant}/files/{id}
Content-Type: multipart/form-data
Triggers re-indexing of the file.
```

### Update Metadata
```
PATCH /v1/{tenant}/files/{id}/meta
Body: { tags: [...], custom_metadata: {...} }
```

### Delete File
```
DELETE /v1/{tenant}/files/{id}
Removes file, metadata, and associated vectors.
```

### List Directory
```
GET /v1/{tenant}/dirs/{path}?namespace=default
Response: { entries: [{ name, type, file_id, size_bytes }] }
```

## Search Operations

### Semantic Search
```
POST /v1/{tenant}/search/semantic
Body: { query: "search text", k: 10, namespace: "optional" }
Uses dense vector similarity for retrieval.
```

### Hybrid Search
```
POST /v1/{tenant}/search/hybrid
Body: { query: "search text", k: 10, namespace: "optional" }
Combines dense vectors with BM25 sparse retrieval using RRF fusion.
```

### Find Similar
```
GET /v1/{tenant}/search/similar/{file_id}?k=10
Finds files with similar content to the specified file.
```

### RAG Ask
```
POST /v1/{tenant}/search/ask
Body: { query: "your question", k: 5, system_prompt: "optional" }
Retrieves relevant chunks and generates an answer using an LLM.
```

### Indexing Status
```
GET /v1/{tenant}/search/status/{file_id}
Response: { file_id, indexing_status, indexing_error }
Status values: pending, processing, indexed, failed
```
