"""
Example Python module demonstrating agent task processing.
This module shows how agents interact with the filesystem API
to process and manage documents.
"""

import asyncio
import httpx
from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentTask:
    task_id: str
    description: str
    priority: int = 1
    status: str = "pending"
    assigned_agent: Optional[str] = None


class DocumentProcessor:
    """Processes documents through the Agentic Filesystem pipeline."""

    def __init__(self, base_url: str, tenant: str):
        self.base_url = base_url
        self.tenant = tenant
        self.client = httpx.AsyncClient(base_url=base_url)

    async def upload_document(self, filepath: str, namespace: str = "default") -> dict:
        """Upload a document to the filesystem."""
        with open(filepath, "rb") as f:
            files = {"file": (filepath.split("/")[-1], f)}
            data = {"namespace": namespace}
            response = await self.client.post(
                f"/v1/{self.tenant}/files",
                files=files,
                data=data,
            )
            response.raise_for_status()
            return response.json()

    async def wait_for_indexing(self, file_id: str, timeout: int = 60) -> str:
        """Wait until a file is indexed."""
        for _ in range(timeout):
            response = await self.client.get(
                f"/v1/{self.tenant}/search/status/{file_id}"
            )
            status = response.json()["indexing_status"]
            if status in ("indexed", "failed"):
                return status
            await asyncio.sleep(1)
        return "timeout"

    async def search_documents(self, query: str, k: int = 5) -> list[dict]:
        """Search for documents using semantic search."""
        response = await self.client.post(
            f"/v1/{self.tenant}/search/semantic",
            json={"query": query, "k": k},
        )
        response.raise_for_status()
        return response.json()["results"]

    async def ask_question(self, question: str) -> str:
        """Ask a question using RAG."""
        response = await self.client.post(
            f"/v1/{self.tenant}/search/ask",
            json={"query": question, "k": 5},
        )
        response.raise_for_status()
        return response.json()["answer"]

    async def close(self):
        await self.client.aclose()


async def main():
    processor = DocumentProcessor("http://localhost:8000", "demo-tenant")

    # Upload a document
    result = await processor.upload_document("report.pdf", namespace="reports")
    print(f"Uploaded: {result['file_id']}")

    # Wait for indexing
    status = await processor.wait_for_indexing(result["file_id"])
    print(f"Indexing status: {status}")

    # Search
    results = await processor.search_documents("quarterly revenue")
    for r in results:
        print(f"  [{r['score']:.3f}] {r['filename']}: {r['chunk_text'][:100]}...")

    # Ask a question
    answer = await processor.ask_question("What was the quarterly revenue?")
    print(f"Answer: {answer}")

    await processor.close()


if __name__ == "__main__":
    asyncio.run(main())
