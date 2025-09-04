import sys
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from data.database import pg, chroma
from .routes import router
from common.exceptions import CustomException, http_exception_handler

from common.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting up application...")
    
    try:
        # Check PostgreSQL connection
        logger.info("Checking PostgreSQL connection...")
        if asyncio.iscoroutinefunction(pg.health_check):
            pg_status = await pg.health_check()
        else:
            pg_status = pg.health_check()
            
        if not pg_status:
            raise Exception("PostgreSQL health check failed")
        logger.info("PostgreSQL connection: OK")
        
        # Check ChromaDB connection
        logger.info("Checking ChromaDB connection...")
        if asyncio.iscoroutinefunction(chroma.health_check):
            chroma_status = await chroma.health_check()
        else:
            chroma_status = chroma.health_check()
            
        if not chroma_status:
            raise Exception("ChromaDB health check failed")
        logger.info("ChromaDB connection: OK")
        
        logger.info("Application startup completed successfully")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    try:
        if hasattr(pg, 'close'):
            if asyncio.iscoroutinefunction(pg.close):
                await pg.close()
            else:
                pg.close()
                
        if hasattr(chroma, 'close'):
            if asyncio.iscoroutinefunction(chroma.close):
                await chroma.close()
            else:
                chroma.close()
                
        logger.info("Application shutdown completed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="OASM Assistant",
        description="An AI-powered cybersecurity assistant that leverages advanced agent architectures for threat monitoring, attack prevention, and web security protection.",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")
    app.add_exception_handler(CustomException, http_exception_handler)
    return app


# Create application instance
app = create_app()


if __name__ == '__main__':
    uvicorn.run(
        "interfaces.api.app:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )