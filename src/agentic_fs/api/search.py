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
