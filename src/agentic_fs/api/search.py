import logging

from fastapi import APIRouter, HTTPException
from openai import OpenAI

from agentic_fs.config import settings
from agentic_fs.dependencies import get_file_store, get_vector_store, get_embedding_service
from agentic_fs.models.search import (
    SemanticSearchRequest,
    HybridSearchRequest,
    RAGRequest,
    SearchHit,
    SearchResponse,
    RAGResponse,
    IndexingStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/{tenant}/search/semantic", response_model=SearchResponse)
async def semantic_search(tenant: str, body: SemanticSearchRequest):
    """Pure vector similarity search using cosine distance on embeddings.

    Best for conceptual queries where meaning matters more than exact wording
    (e.g. "system architecture overview" will find documents about design patterns
    even if they don't contain those exact words).

    **When to use this vs. hybrid:** Use semantic when your query is abstract or
    conceptual. Use hybrid (recommended default) when your query contains specific
    terms or names that should be matched literally alongside semantic meaning.

    Returns a list of `SearchHit` objects with `file_id`, relevance `score`, and
    a `chunk_text` snippet. Pass the `file_id` values to the batch endpoint to
    retrieve full file content.
    """
    embedding_svc = get_embedding_service()
    vector_store = get_vector_store()

    query_vector = embedding_svc.embed_query(body.query)

    raw_results = vector_store.search_dense(
        tenant_id=tenant,
        query_vector=query_vector,
        k=body.k,
        namespace=body.namespace,
    )

    results = [
        SearchHit(
            file_id=r["file_id"],
            filename=r["filename"],
            score=r["score"],
            chunk_text=r["chunk_text"],
            chunk_idx=r["chunk_idx"],
            namespace=r.get("namespace"),
        )
        for r in raw_results
    ]

    return SearchResponse(results=results, query=body.query, total=len(results))


@router.post("/v1/{tenant}/search/hybrid", response_model=SearchResponse)
async def hybrid_search(tenant: str, body: HybridSearchRequest):
    """Combined vector + BM25 keyword search using Reciprocal Rank Fusion (RRF).

    **This is the recommended default search mode.** It combines semantic vector
    similarity with traditional keyword matching (BM25), so it handles both
    conceptual queries and specific term lookups well.

    Use this when: the query mixes concepts with specific terms (e.g. "Q4 revenue
    trends"), you're unsure which search mode to use, or you want the most
    robust results across different query types.

    Returns a list of `SearchHit` objects. Pass the `file_id` values to the
    batch endpoint to retrieve full file content.
    """
    embedding_svc = get_embedding_service()
    vector_store = get_vector_store()

    query_vector = embedding_svc.embed_query(body.query)

    raw_results = vector_store.search_hybrid(
        tenant_id=tenant,
        query_vector=query_vector,
        query_text=body.query,
        k=body.k,
        namespace=body.namespace,
    )

    results = [
        SearchHit(
            file_id=r["file_id"],
            filename=r["filename"],
            score=r["score"],
            chunk_text=r["chunk_text"],
            chunk_idx=r["chunk_idx"],
            namespace=r.get("namespace"),
        )
        for r in raw_results
    ]

    return SearchResponse(results=results, query=body.query, total=len(results))


@router.get("/v1/{tenant}/search/similar/{file_id}", response_model=SearchResponse)
async def find_similar(tenant: str, file_id: str, k: int = 10):
    """Find files similar to a known file by vector proximity.

    Useful for: deduplication checks ("are there other files like this?"),
    content discovery ("show me more like this document"), and clustering
    related files. The target file must already be indexed.

    Returns files ranked by similarity to the given file's embeddings.
    """
    vector_store = get_vector_store()

    raw_results = vector_store.find_similar(
        tenant_id=tenant,
        file_id=file_id,
        k=k,
    )

    results = [
        SearchHit(
            file_id=r["file_id"],
            filename=r["filename"],
            score=r["score"],
            chunk_text=r["chunk_text"],
            chunk_idx=r["chunk_idx"],
            namespace=r.get("namespace"),
        )
        for r in raw_results
    ]

    return SearchResponse(
        results=results,
        query=f"similar to {file_id}",
        total=len(results),
    )


@router.post("/v1/{tenant}/search/ask", response_model=RAGResponse)
async def rag_ask(tenant: str, body: RAGRequest):
    """Ask a question and get a natural-language answer with source citations (RAG).

    This performs hybrid search behind the scenes, assembles the top-k chunks into
    context, and sends them to an LLM to generate a synthesized answer. The response
    includes both the `answer` text and the `sources` (SearchHit list) used to produce it.

    **When to use this vs. search:** Use `ask` when the user needs a direct answer to a
    question (e.g. "What is our refund policy?"). Use `semantic` or `hybrid` when you
    need a ranked list of relevant documents rather than a synthesized answer.

    **Tip:** Keep `k` between 3-7 for focused answers. Higher values provide more context
    but may dilute the answer with less relevant content. You can customize the LLM
    behavior via `system_prompt`.
    """
    embedding_svc = get_embedding_service()
    vector_store = get_vector_store()

    # Step 1: Retrieve relevant chunks via hybrid search
    query_vector = embedding_svc.embed_query(body.query)
    raw_results = vector_store.search_hybrid(
        tenant_id=tenant,
        query_vector=query_vector,
        query_text=body.query,
        k=body.k,
        namespace=body.namespace,
    )

    if not raw_results:
        return RAGResponse(
            answer="No relevant documents found to answer your question.",
            sources=[],
            query=body.query,
        )

    # Step 2: Build context from chunks
    context_parts = []
    for i, r in enumerate(raw_results):
        context_parts.append(
            f"[Source {i+1}: {r['filename']}]\n{r['chunk_text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    # Step 3: Call LLM
    system_prompt = body.system_prompt or (
        "You are a helpful assistant that answers questions based on the provided context. "
        "Always cite the source documents when answering. "
        "If the context doesn't contain enough information, say so."
    )

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {body.query}",
            },
        ],
        max_tokens=1024,
        temperature=0.3,
    )

    answer = response.choices[0].message.content

    sources = [
        SearchHit(
            file_id=r["file_id"],
            filename=r["filename"],
            score=r["score"],
            chunk_text=r["chunk_text"],
            chunk_idx=r["chunk_idx"],
            namespace=r.get("namespace"),
        )
        for r in raw_results
    ]

    return RAGResponse(answer=answer, sources=sources, query=body.query)


@router.get(
    "/v1/{tenant}/search/status/{file_id}",
    response_model=IndexingStatusResponse,
)
async def indexing_status(tenant: str, file_id: str):
    """Check the indexing status of an uploaded file.

    Returns one of: `pending` (queued), `processing` (in progress), `indexed`
    (searchable), or `failed` (check `indexing_error` for details).

    **Agent tip:** After uploading a file, poll this endpoint with exponential
    backoff (e.g. 1s, 2s, 4s) until status is `indexed` before issuing search
    queries. Files in `pending` or `processing` state will not appear in search results.
    """
    fs = get_file_store()
    try:
        metadata = fs.get_metadata(tenant, file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

    return IndexingStatusResponse(
        file_id=metadata.file_id,
        indexing_status=metadata.indexing_status,
        indexing_error=metadata.indexing_error,
    )
