import json
import logging
from typing import Generator

import agentic_fs.config
from agentic_fs.models.batch import BatchFileEntry, BatchRetrieveRequest, BatchRetrieveResponse
from agentic_fs.services.file_store import FileStore
from agentic_fs.services.extractor import Extractor
from agentic_fs.utils.mime import is_text_type, needs_extraction

logger = logging.getLogger(__name__)


class BatchService:
    def __init__(self, file_store: FileStore, extractor: Extractor):
        self.file_store = file_store
        self.extractor = extractor

    def build_download_url(self, tenant: str, file_id: str) -> str:
        settings = agentic_fs.config.settings
        base = settings.api_base_url
        if not base:
            host = settings.api_host
            if host == "0.0.0.0":
                host = "localhost"
            base = f"http://{host}:{settings.api_port}"
        return f"{base}/v1/{tenant}/files/{file_id}"

    def retrieve_single(
        self,
        tenant: str,
        file_id: str,
        include_content: bool = True,
        max_text_chars: int | None = None,
    ) -> BatchFileEntry:
        download_url = self.build_download_url(tenant, file_id)

        # Get metadata
        try:
            metadata = self.file_store.get_metadata(tenant, file_id)
        except FileNotFoundError:
            return BatchFileEntry(
                file_id=file_id,
                filename="",
                mime_type="",
                size_bytes=0,
                created_at="",
                updated_at="",
                indexing_status="",
                content_type="error",
                download_url=download_url,
                error=f"File {file_id} not found",
            )

        base_fields = dict(
            file_id=metadata.file_id,
            filename=metadata.filename,
            mime_type=metadata.mime_type,
            size_bytes=metadata.size_bytes,
            namespace=metadata.namespace,
            path=metadata.path,
            tags=metadata.tags,
            custom_metadata=metadata.custom_metadata,
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
            indexing_status=metadata.indexing_status,
            download_url=download_url,
        )

        if not include_content:
            return BatchFileEntry(**base_fields, content_type="text", content=None)

        try:
            if metadata.mime_type == "application/json":
                return self._handle_json_file(tenant, file_id, base_fields, max_text_chars)
            elif is_text_type(metadata.mime_type):
                return self._handle_text_file(tenant, file_id, base_fields, max_text_chars)
            else:
                return self._handle_binary_file(tenant, file_id, metadata.mime_type, base_fields, max_text_chars)
        except Exception as e:
            logger.error(f"Error retrieving content for {file_id}: {e}")
            return BatchFileEntry(
                **base_fields,
                content_type="error",
                error=f"Failed to retrieve content: {str(e)}",
            )

    def _handle_json_file(self, tenant, file_id, base_fields, max_text_chars):
        content_bytes, _ = self.file_store.get_file_content(tenant, file_id)
        text = content_bytes.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text)
            return BatchFileEntry(**base_fields, content_type="json", content=parsed)
        except json.JSONDecodeError:
            truncated = False
            if max_text_chars and len(text) > max_text_chars:
                text = text[:max_text_chars]
                truncated = True
            return BatchFileEntry(**base_fields, content_type="text", content=text, truncated=truncated)

    def _handle_text_file(self, tenant, file_id, base_fields, max_text_chars):
        content_bytes, _ = self.file_store.get_file_content(tenant, file_id)
        text = content_bytes.decode("utf-8", errors="replace")
        truncated = False
        if max_text_chars and len(text) > max_text_chars:
            text = text[:max_text_chars]
            truncated = True
        return BatchFileEntry(**base_fields, content_type="text", content=text, truncated=truncated)

    def _handle_binary_file(self, tenant, file_id, mime_type, base_fields, max_text_chars):
        if needs_extraction(mime_type):
            file_path = self.file_store.get_file_path(tenant, file_id)
            extracted = self.extractor.extract(file_path, mime_type)
            text = extracted.text
            truncated = False
            if max_text_chars and len(text) > max_text_chars:
                text = text[:max_text_chars]
                truncated = True
            return BatchFileEntry(**base_fields, content_type="binary", content=text, truncated=truncated)
        else:
            return BatchFileEntry(**base_fields, content_type="binary", content=None)

    def retrieve_batch(
        self,
        tenant: str,
        request: BatchRetrieveRequest,
    ) -> BatchRetrieveResponse:
        entries = []
        error_count = 0
        for file_id in request.file_ids:
            entry = self.retrieve_single(
                tenant,
                file_id,
                include_content=request.include_content,
                max_text_chars=request.max_text_chars,
            )
            if entry.content_type == "error":
                error_count += 1
            entries.append(entry)

        return BatchRetrieveResponse(
            files=entries,
            total_requested=len(request.file_ids),
            total_found=len(request.file_ids) - error_count,
            total_errors=error_count,
        )

    def retrieve_batch_stream(
        self,
        tenant: str,
        request: BatchRetrieveRequest,
    ) -> Generator[str, None, None]:
        for file_id in request.file_ids:
            entry = self.retrieve_single(
                tenant,
                file_id,
                include_content=request.include_content,
                max_text_chars=request.max_text_chars,
            )
            yield entry.model_dump_json() + "\n"
