from fastapi import APIRouter

router = APIRouter()

@router.post("",
    summary="Send a message",
    description="Send a message to the chat session"
)
async def create_message():
    return {"message": "Hello, World!"}
