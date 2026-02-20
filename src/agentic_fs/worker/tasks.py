import logging

from agentic_fs.worker.celery_app import celery_app
from agentic_fs.worker.pipeline import run_indexing_pipeline
from agentic_fs.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


@celery_app.task(name="agentic_fs.index_file", bind=True, max_retries=3)
def index_file(self, tenant_id: str, file_id: str):
    """Index a file: extract text, chunk, embed, and store vectors."""
    try:
        run_indexing_pipeline(tenant_id, file_id)
    except Exception as exc:
        logger.error(f"Task index_file failed for {file_id}: {exc}")
        raise self.retry(exc=exc, countdown=5 * (self.request.retries + 1))


@celery_app.task(name="agentic_fs.delete_vectors")
def delete_vectors(tenant_id: str, file_id: str):
    """Delete all vectors for a file."""
    try:
        vs = VectorStore()
        vs.delete_by_file(tenant_id, file_id)
        logger.info(f"Deleted vectors for file {file_id}")
    except Exception as exc:
        logger.error(f"Task delete_vectors failed for {file_id}: {exc}")
        raise
