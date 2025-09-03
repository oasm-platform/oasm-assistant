from fastapi import APIRouter

router = APIRouter()

@router.post("/start",
    summary="Start a new chat session",
    description="Start a new chat session for a user"
)
async def start_chat():
    return {"message": "Hello, World!"}
