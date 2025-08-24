from apis.endpoints.core import router
from apis.rest.routes.langchain_endpoints import router as langchain_router
from apis.middlewares.auth import TokenAuthMiddleware

# Combine routers
from fastapi import APIRouter
main_router = APIRouter()
main_router.include_router(router)
main_router.include_router(langchain_router)

# Export main router as 'router' for backward compatibility
router = main_router
