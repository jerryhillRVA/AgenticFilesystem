from typing import Any

from pydantic import BaseModel, Field


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., description="Natural-language search query. Describe what you're looking for conceptually.")
    k: int = Field(default=10, ge=1, le=100, description="Number of results to return. Use 3-5 for precise retrieval, 10-20 for broad discovery.")
    filters: dict[str, Any] = Field(default_factory=dict, description="Additional payload filters (advanced). Rarely needed for standard use.")
    namespace: str | None = Field(default=None, description="Restrict search to a specific namespace. Omit to search all namespaces.")


class HybridSearchRequest(BaseModel):
    query: str = Field(..., description="Natural-language search query. Works well with both conceptual phrases and specific terms.")
    k: int = Field(default=10, ge=1, le=100, description="Number of results to return. Use 3-5 for precise retrieval, 10-20 for broad discovery.")
    filters: dict[str, Any] = Field(default_factory=dict, description="Additional payload filters (advanced). Rarely needed for standard use.")
    namespace: str | None = Field(default=None, description="Restrict search to a specific namespace. Omit to search all namespaces.")


class RAGRequest(BaseModel):
    query: str = Field(..., description="The question to answer. Phrased as a question gets the best results (e.g. 'What is our refund policy?').")
    k: int = Field(default=5, ge=1, le=20, description="Number of source chunks to retrieve for context. 3-5 for focused answers, up to 10 for comprehensive ones.")
    system_prompt: str | None = Field(default=None, description="Override the default LLM system prompt. Use to customize answer style, length, or domain focus.")
    namespace: str | None = Field(default=None, description="Restrict source documents to a specific namespace.")


class SearchHit(BaseModel):
    file_id: str = Field(..., description="Unique file identifier. Pass to the batch endpoint to retrieve full content.")
    filename: str = Field(..., description="Original filename as uploaded.")
    score: float = Field(..., description="Relevance score (higher is more relevant). Scale varies by search mode.")
    chunk_text: str = Field(..., description="Text snippet from the matching chunk. Use for previews; retrieve full content via the batch endpoint.")
    chunk_idx: int = Field(..., description="Index of the matching chunk within the file (0-based).")
    namespace: str | None = Field(default=None, description="Namespace the file belongs to.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata from the file's sidecar.")


class SearchResponse(BaseModel):
    results: list[SearchHit] = Field(..., description="Ranked list of matching file chunks, ordered by relevance score.")
    query: str = Field(..., description="The original query string (echoed back).")
    total: int = Field(..., description="Number of results returned.")


class RAGResponse(BaseModel):
    answer: str = Field(..., description="Synthesized natural-language answer based on the retrieved sources.")
    sources: list[SearchHit] = Field(..., description="The source chunks used to generate the answer. Use file_id values with the batch endpoint for full content.")
    query: str = Field(..., description="The original question (echoed back).")


class IndexingStatusResponse(BaseModel):
    file_id: str = Field(..., description="The file being checked.")
    indexing_status: str = Field(..., description="One of: pending, processing, indexed, failed. Wait for 'indexed' before searching.")
    indexing_error: str | None = Field(default=None, description="Error details if indexing_status is 'failed'.")
