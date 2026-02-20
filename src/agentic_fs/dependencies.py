from functools import lru_cache

import agentic_fs.config
from agentic_fs.services.file_store import FileStore
from agentic_fs.services.metadata_store import MetadataStore
from agentic_fs.services.vector_store import VectorStore
from agentic_fs.services.embedding import EmbeddingService
from agentic_fs.services.chunker import Chunker
from agentic_fs.services.extractor import Extractor
from agentic_fs.services.batch import BatchService


@lru_cache
def get_file_store() -> FileStore:
    return FileStore(base_path=agentic_fs.config.settings.filestore_base_path)


@lru_cache
def get_metadata_store() -> MetadataStore:
    return MetadataStore(base_path=agentic_fs.config.settings.filestore_base_path)


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


@lru_cache
def get_batch_service() -> BatchService:
    return BatchService(
        file_store=get_file_store(),
        extractor=get_extractor(),
    )
