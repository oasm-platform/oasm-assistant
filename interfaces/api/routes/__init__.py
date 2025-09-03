from fastapi import APIRouter
from .healthcheck import router as healthcheck
from .chat_session import router as chat_session
from .messages import router as messages


router = APIRouter()

router.include_router(healthcheck, tags=["Health Check"], prefix="/healthcheck")
router.include_router(chat_session, tags=["Chat Session"], prefix="/chat_session")
router.include_router(messages, tags=["Messages"], prefix="/messages")
