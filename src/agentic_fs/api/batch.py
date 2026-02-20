import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

import agentic_fs.config
import agentic_fs.dependencies
from agentic_fs.models.batch import BatchRetrieveRequest, BatchRetrieveResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/{tenant}/files/batch", response_model=BatchRetrieveResponse)
async def batch_retrieve(tenant: str, body: BatchRetrieveRequest):
    """Retrieve metadata and content for multiple files in a single call.

    **This is the recommended way to fetch files after a search.** Pass the `file_id`
    values from search results to get all file content in one request, rather than
    making N individual download calls.

    Each file entry includes a `content_type` discriminator:
    - `text`: Raw text content inline (plain text, markdown, code, etc.)
    - `json`: Parsed JSON content inline (dict or list, not stringified)
    - `binary`: Extracted text from binary files (PDF, DOCX, etc.) plus a `download_url`
      for the original binary
    - `error`: File not found or extraction failed — check the `error` field

    **Streaming:** Set `stream: true` for NDJSON output (one JSON object per line),
    useful when retrieving many files to start processing before the full response arrives.

    **Metadata-only:** Set `include_content: false` to skip content loading — useful when
    you only need file metadata, sizes, and download URLs.
    """
    max_files = agentic_fs.config.settings.batch_max_files
    if len(body.file_ids) > max_files:
        raise HTTPException(
            status_code=422,
            detail=f"Too many file_ids: {len(body.file_ids)}. "
            f"Maximum allowed is {max_files} "
            f"(configurable via BATCH_MAX_FILES).",
        )

    svc = agentic_fs.dependencies.get_batch_service()

    if body.stream:
        return StreamingResponse(
            svc.retrieve_batch_stream(tenant, body),
            media_type="application/x-ndjson",
        )

    return svc.retrieve_batch(tenant, body)
