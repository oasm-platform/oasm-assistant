import sys
from pathlib import Path
import uvicorn
# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from data.database import pg, chroma


from interfaces.api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    print("Starting up application...")
    try:
        health_status_pg = await pg.health_check()
        if not health_status_pg:
            raise Exception("PostgreSQL health check failed")
        health_status_chroma = await chroma.health_check()
        if not health_status_chroma:
            raise Exception("ChromaDB health check failed")
    except Exception as e:  
        print(f"Error during startup: {e}")
        raise
    
    yield
    
    print("Shutting down application...")
    try:
        print("Closing database connections...")
        await pg.close()
        await chroma.close()
        print("Database connections closed")
    except Exception as e:
        print(f"Error during shutdown: {e}")


def get_application() -> FastAPI:

    # Create FastAPI application
    application = FastAPI(
        title="OASM Assistant",
        description="An AI-powered cybersecurity assistant that leverages advanced agent architectures for threat monitoring, attack prevention, and web security protection.",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    application.include_router(router, prefix="/api/v1")

    return application

app = get_application()
if __name__ == '__main__':
    import uvicorn
    uvicorn.run("interfaces.api.app:app", host="0.0.0.0", port=8080, reload=True)