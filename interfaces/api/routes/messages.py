from fastapi import APIRouter

router = APIRouter()

@router.post("/send",
    summary="Send a message",
    description="Send a message to the chat session"
)
async def send_message():
    return {"message": "Hello, World!"}
