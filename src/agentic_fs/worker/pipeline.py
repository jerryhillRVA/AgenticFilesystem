import logging

from agentic_fs.config import settings
from agentic_fs.services.file_store import FileStore
from agentic_fs.services.extractor import Extractor
from agentic_fs.services.chunker import Chunker
from agentic_fs.services.embedding import EmbeddingService
from agentic_fs.services.vector_store import VectorStore
from agentic_fs.services.pairing import PairingService
from agentic_fs.utils.mime import is_text_type, needs_extraction

logger = logging.getLogger(__name__)


def run_indexing_pipeline(tenant_id: str, file_id: str):
    """Execute the 7-step indexing pipeline for a file."""
    file_store = FileStore(base_path=settings.filestore_base_path)
    extractor = Extractor()
    chunker = Chunker()
    embedding_service = EmbeddingService()
    vector_store = VectorStore()
    pairing_service = PairingService(file_store)

    try:
        # Step 1: Read file info
        logger.info(f"[Pipeline] Step 1: Reading file {file_id} for tenant {tenant_id}")
        metadata = file_store.get_metadata(tenant_id, file_id)
        file_path = file_store.get_file_path(tenant_id, file_id)

        # Step 2: Update status to processing
        logger.info(f"[Pipeline] Step 2: Updating status to processing")
        file_store.update_metadata(tenant_id, file_id, indexing_status="processing")

        # Step 3: Extract text
        logger.info(f"[Pipeline] Step 3: Extracting text from {metadata.filename} ({metadata.mime_type})")
        extracted = extractor.extract(file_path, metadata.mime_type)
        logger.info(f"[Pipeline] Extracted {extracted.char_count} chars via {extracted.method}")

        if not extracted.text.strip():
            logger.warning(f"[Pipeline] No text extracted from {file_id}, marking as indexed with empty content")
            file_store.update_metadata(tenant_id, file_id, indexing_status="indexed")
            return

        # Step 4: Handle binary pairing
        if needs_extraction(metadata.mime_type):
            logger.info(f"[Pipeline] Step 4: Creating binary-text pairing")
            pairing_service.create_pairing(tenant_id, file_id, extracted.text)

        # Step 5: Chunk text
        logger.info(f"[Pipeline] Step 5: Chunking text")
        chunks = chunker.chunk(extracted.text)
        logger.info(f"[Pipeline] Created {len(chunks)} chunks")

        if not chunks:
            file_store.update_metadata(tenant_id, file_id, indexing_status="indexed")
            return

        # Step 6: Batch embed chunks
        logger.info(f"[Pipeline] Step 6: Embedding {len(chunks)} chunks")
        chunk_texts = [c.text for c in chunks]
        dense_vectors = embedding_service.embed_texts(chunk_texts)

        # Step 7: Upsert to Qdrant
        logger.info(f"[Pipeline] Step 7: Upserting vectors to Qdrant")
        vector_store.upsert_chunks(
            tenant_id=tenant_id,
            file_id=file_id,
            chunks=chunks,
            dense_vectors=dense_vectors,
            filename=metadata.filename,
            namespace=metadata.namespace,
        )

        # Update status to indexed
        file_store.update_metadata(tenant_id, file_id, indexing_status="indexed")
        logger.info(f"[Pipeline] File {file_id} indexed successfully")

    except Exception as e:
        logger.error(f"[Pipeline] Failed to index file {file_id}: {e}", exc_info=True)
        try:
            file_store.update_metadata(
                tenant_id, file_id,
                indexing_status="failed",
                indexing_error=str(e),
            )
        except Exception:
            logger.error(f"[Pipeline] Failed to update error status for {file_id}")
        raise
