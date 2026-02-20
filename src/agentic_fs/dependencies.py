from functools import lru_cache

from agentic_fs.config import settings
from agentic_fs.services.file_store import FileStore
from agentic_fs.services.metadata_store import MetadataStore
from agentic_fs.services.vector_store import VectorStore
from agentic_fs.services.embedding import EmbeddingService
from agentic_fs.services.chunker import Chunker
from agentic_fs.services.extractor import Extractor


@lru_cache
def get_file_store() -> FileStore:
    return FileStore(base_path=settings.filestore_base_path)


@lru_cache
def get_metadata_store() -> MetadataStore:
    return MetadataStore(base_path=settings.filestore_base_path)


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore()


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


@lru_cache
def get_chunker() -> Chunker:
    return Chunker()


@lru_cache
def get_extractor() -> Extractor:
    return Extractor()
