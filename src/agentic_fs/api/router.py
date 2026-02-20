from fastapi import APIRouter

from agentic_fs.api.files import router as files_router
from agentic_fs.api.dirs import router as dirs_router
from agentic_fs.api.search import router as search_router
from agentic_fs.api.batch import router as batch_router

api_router = APIRouter()

api_router.include_router(files_router, tags=["files"])
api_router.include_router(dirs_router, tags=["directories"])
api_router.include_router(search_router, tags=["search"])
api_router.include_router(batch_router, tags=["batch"])
