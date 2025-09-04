from fastapi import APIRouter
from .healthcheck import router as healthcheck
from .chats import router as chats

router = APIRouter()

router.include_router(healthcheck, tags=["Health Check"], prefix="/health")
router.include_router(chats, tags=["Chats"], prefix="/chats")

__all__ = ["router"]
