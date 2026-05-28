from fastapi import APIRouter
from ..tools.registry import AVAILABLE_TOOLS

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
def list_available_tools():
    return {"tools": AVAILABLE_TOOLS}
