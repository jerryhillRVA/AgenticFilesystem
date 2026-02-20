from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # File Store
    filestore_base_path: str = "/data"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "agentic_fs_chunks"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"

    # Tika
    tika_url: str = "http://localhost:9998"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = ""  # e.g. "http://localhost:8000" — if empty, auto-built from api_host/api_port
    log_level: str = "info"

    # Batch retrieval
    batch_max_files: int = 100

    # Chunking
    chunk_size_tokens: int = 512
    chunk_overlap_percent: int = 10

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
