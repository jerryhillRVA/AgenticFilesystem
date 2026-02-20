import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from agentic_fs.config import settings
from agentic_fs.services.vector_store import VectorStore
from agentic_fs.api.router import api_router
from agentic_fs.api.middleware import log_request

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure Qdrant collection exists
    vs = VectorStore()
    vs.ensure_collection()
    yield


app = FastAPI(
    title="Agentic Filesystem",
    description="Tenant-scoped file storage and semantic search API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(BaseHTTPMiddleware, dispatch=log_request)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
