from fastapi import APIRouter
from .agents import router as agents_router
from .workflows import router as workflows_router
from .runs import router as runs_router
from .monitor import router as monitor_router
from .tools import router as tools_router

api_router = APIRouter(prefix="/api")
api_router.include_router(agents_router)
api_router.include_router(workflows_router)
api_router.include_router(runs_router)
api_router.include_router(monitor_router)
api_router.include_router(tools_router)
