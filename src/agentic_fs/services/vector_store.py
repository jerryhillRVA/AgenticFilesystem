import logging
import re
import math
from collections import Counter

from qdrant_client import QdrantClient, models

from agentic_fs.config import settings
from agentic_fs.utils.ids import deterministic_point_id

logger = logging.getLogger(__name__)


def compute_sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """Simple BM25-style term frequency sparse vector."""
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return [], []

    counts = Counter(tokens)
    total = len(tokens)
    indices = []
    values = []

    for token, count in counts.items():
        # Use hash as index, map to positive 32-bit int
        idx = abs(hash(token)) % (2**31)
        tf = count / total
        indices.append(idx)
        values.append(tf)

    return indices, values


class VectorStore:
    def __init__(self):
        self.client = QdrantClient(url=settings.qdrant_url, timeout=30)
        self.collection_name = settings.qdrant_collection

    def ensure_collection(self):
        collections = self.client.get_collections().collections
        existing = [c.name for c in collections]

        if self.collection_name not in existing:
            logger.info(f"Creating Qdrant collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=1536,
                        distance=models.Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    "bm25": models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    ),
                },
            )
            # Payload indexes for filtering
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="tenant_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="file_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            logger.info(f"Collection {self.collection_name} created")
        else:
            logger.info(f"Collection {self.collection_name} already exists")

        # Ensure path index exists (idempotent — safe to call on every startup)
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="path",
                field_schema=models.PayloadSchemaType.TEXT,
            )
        except Exception:
            pass  # Index already exists

    def upsert_chunks(
        self,
        tenant_id: str,
        file_id: str,
        chunks: list,
        dense_vectors: list[list[float]],
        filename: str = "",
        namespace: str = "default",
        path: str = "",
    ):
        points = []
        for i, (chunk, dense_vec) in enumerate(zip(chunks, dense_vectors)):
            point_id = deterministic_point_id(file_id, chunk.chunk_idx)
            sparse_indices, sparse_values = compute_sparse_vector(chunk.text)

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_vec,
                        "bm25": models.SparseVector(
                            indices=sparse_indices,
                            values=sparse_values,
                        ),
                    },
                    payload={
                        "tenant_id": tenant_id,
                        "file_id": file_id,
                        "chunk_idx": chunk.chunk_idx,
                        "start_char": chunk.start_char,
                        "end_char": chunk.end_char,
                        "chunk_text": chunk.text,
                        "filename": filename,
                        "namespace": namespace,
                        "path": path,
                    },
                )
            )

        # Batch upsert in groups of 100
        for i in range(0, len(points), 100):
            batch = points[i : i + 100]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )

        logger.info(f"Upserted {len(points)} vectors for file {file_id}")

    def search_dense(
        self,
        tenant_id: str,
        query_vector: list[float],
        k: int = 10,
        namespace: str | None = None,
        path: str | None = None,
    ) -> list[dict]:
        must_conditions = [
            models.FieldCondition(
                key="tenant_id",
                match=models.MatchValue(value=tenant_id),
            )
        ]
        if namespace:
            must_conditions.append(
                models.FieldCondition(
                    key="namespace",
                    match=models.MatchValue(value=namespace),
                )
            )
        if path:
            must_conditions.append(
                models.FieldCondition(
                    key="path",
                    match=models.MatchText(text=path),
                )
            )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            using="dense",
            limit=k,
            with_payload=True,
            query_filter=models.Filter(must=must_conditions),
        )

        return [
            {
                "file_id": point.payload.get("file_id", ""),
                "filename": point.payload.get("filename", ""),
                "score": point.score,
                "chunk_text": point.payload.get("chunk_text", ""),
                "chunk_idx": point.payload.get("chunk_idx", 0),
                "namespace": point.payload.get("namespace"),
                "path": point.payload.get("path", ""),
                "metadata": point.payload,
            }
            for point in results.points
        ]

    def search_hybrid(
        self,
        tenant_id: str,
        query_vector: list[float],
        query_text: str,
        k: int = 10,
        namespace: str | None = None,
        path: str | None = None,
    ) -> list[dict]:
        must_conditions = [
            models.FieldCondition(
                key="tenant_id",
                match=models.MatchValue(value=tenant_id),
            )
        ]
        if namespace:
            must_conditions.append(
                models.FieldCondition(
                    key="namespace",
                    match=models.MatchValue(value=namespace),
                )
            )
        if path:
            must_conditions.append(
                models.FieldCondition(
                    key="path",
                    match=models.MatchText(text=path),
                )
            )

        query_filter = models.Filter(must=must_conditions)
        sparse_indices, sparse_values = compute_sparse_vector(query_text)

        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=query_vector,
                    using="dense",
                    limit=k * 3,
                    filter=query_filter,
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_indices,
                        values=sparse_values,
                    ),
                    using="bm25",
                    limit=k * 3,
                    filter=query_filter,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=k,
            with_payload=True,
        )

        return [
            {
                "file_id": point.payload.get("file_id", ""),
                "filename": point.payload.get("filename", ""),
                "score": point.score,
                "chunk_text": point.payload.get("chunk_text", ""),
                "chunk_idx": point.payload.get("chunk_idx", 0),
                "namespace": point.payload.get("namespace"),
                "path": point.payload.get("path", ""),
                "metadata": point.payload,
            }
            for point in results.points
        ]

    def find_similar(
        self,
        tenant_id: str,
        file_id: str,
        k: int = 10,
    ) -> list[dict]:
        # Get vectors for this file
        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="tenant_id",
                        match=models.MatchValue(value=tenant_id),
                    ),
                    models.FieldCondition(
                        key="file_id",
                        match=models.MatchValue(value=file_id),
                    ),
                ]
            ),
            limit=1,
            with_vectors=True,
        )

        if not scroll_result[0]:
            return []

        # Use first chunk's vector to find similar files
        first_point = scroll_result[0][0]
        query_vector = first_point.vector.get("dense", []) if isinstance(first_point.vector, dict) else first_point.vector

        # Search excluding the same file
        must_conditions = [
            models.FieldCondition(
                key="tenant_id",
                match=models.MatchValue(value=tenant_id),
            ),
        ]
        must_not_conditions = [
            models.FieldCondition(
                key="file_id",
                match=models.MatchValue(value=file_id),
            ),
        ]

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            using="dense",
            limit=k,
            with_payload=True,
            query_filter=models.Filter(
                must=must_conditions,
                must_not=must_not_conditions,
            ),
        )

        # Deduplicate by file_id, keep best score
        seen = {}
        for point in results.points:
            fid = point.payload.get("file_id", "")
            if fid not in seen or point.score > seen[fid]["score"]:
                seen[fid] = {
                    "file_id": fid,
                    "filename": point.payload.get("filename", ""),
                    "score": point.score,
                    "chunk_text": point.payload.get("chunk_text", ""),
                    "chunk_idx": point.payload.get("chunk_idx", 0),
                    "namespace": point.payload.get("namespace"),
                    "path": point.payload.get("path", ""),
                    "metadata": point.payload,
                }

        return list(seen.values())[:k]

    def update_file_path(
        self,
        tenant_id: str,
        file_id: str,
        new_path: str,
        new_namespace: str | None = None,
    ):
        payload_updates = {"path": new_path}
        if new_namespace is not None:
            payload_updates["namespace"] = new_namespace

        self.client.set_payload(
            collection_name=self.collection_name,
            payload=payload_updates,
            points=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id),
                        ),
                        models.FieldCondition(
                            key="file_id",
                            match=models.MatchValue(value=file_id),
                        ),
                    ]
                )
            ),
        )
        logger.info(f"Updated path for file {file_id} to '{new_path}'")

    def delete_by_file(self, tenant_id: str, file_id: str):
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id),
                        ),
                        models.FieldCondition(
                            key="file_id",
                            match=models.MatchValue(value=file_id),
                        ),
                    ]
                )
            ),
        )
        logger.info(f"Deleted vectors for file {file_id}")
