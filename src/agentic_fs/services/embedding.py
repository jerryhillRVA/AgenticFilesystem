import logging

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from agentic_fs.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model
        self.batch_size = 2048  # OpenAI limit

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            response = self.client.embeddings.create(
                model=self.model,
                input=batch,
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def embed_query(self, query: str) -> list[float]:
        response = self.client.embeddings.create(
            model=self.model,
            input=query,
        )
        return response.data[0].embedding
