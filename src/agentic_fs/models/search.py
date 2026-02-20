from typing import Any

from pydantic import BaseModel, Field


class SemanticSearchRequest(BaseModel):
    query: str
    k: int = Field(default=10, ge=1, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)
    namespace: str | None = None


class HybridSearchRequest(BaseModel):
    query: str
    k: int = Field(default=10, ge=1, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)
    namespace: str | None = None


class RAGRequest(BaseModel):
    query: str
    k: int = Field(default=5, ge=1, le=20)
    system_prompt: str | None = None
    namespace: str | None = None


class SearchHit(BaseModel):
    file_id: str
    filename: str
    score: float
    chunk_text: str
    chunk_idx: int
    namespace: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    results: list[SearchHit]
    query: str
    total: int


class RAGResponse(BaseModel):
    answer: str
    sources: list[SearchHit]
    query: str


class IndexingStatusResponse(BaseModel):
    file_id: str
    indexing_status: str
    indexing_error: str | None = None
