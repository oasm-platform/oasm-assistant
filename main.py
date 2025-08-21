"""
Main entry point of the OASM Assistant
"""
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apis import router, TokenAuthMiddleware

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)
# Suppress watchfiles INFO messages
logging.getLogger("watchfiles").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting OASM Assistant")
    yield
    logger.info("Shutting down OASM Assistant")


app = FastAPI(
    title="OASM Assistant",
    description="⚔️ Smart assistant for threat monitoring, attack prevention, and web protection.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add authentication middleware
app.add_middleware(
    TokenAuthMiddleware,
    excluded_paths=["/health", "/docs", "/redoc", "/openapi.json"]
)

app.include_router(router)


@app.get("/health")
async def health_check():
    try:
        return {
            "message": "OASM Assistant",
            "version": "1.0.0",
        }
    except Exception as e:
        return {
            "message": "OASM Assistant",
            "version": "1.0.0",
            "status": "degraded",
            "error": str(e)
        }


if __name__ == "__main__":
    # Get configuration from settings
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=os.getenv("PORT", 8000),
        reload=True,
    )