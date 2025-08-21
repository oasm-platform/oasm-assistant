"""
Authentication middleware for token-based authentication
"""
import logging
from typing import Optional
from fastapi import Request, status
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import os
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

# Security scheme for token authentication
security = HTTPBearer()

class TokenAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for token-based authentication
    Validates token from headers["token"] or Authorization header
    """
    
    def __init__(self, app, excluded_paths: Optional[list] = None):
        super().__init__(app)
        self.excluded_paths = excluded_paths or []
    

    async def dispatch(self, request: Request, call_next):
        # Skip authentication for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Extract token from headers
        token = self._extract_token(request)
        
        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Missing authentication token",
                    "details": "Token must be provided in 'token' header or Authorization header"
                }
            )
        
        # Validate token
        if not self._validate_token(token):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Invalid or expired token",
                    "details": "Please provide a valid authentication token"
                }
            )
        
        # Add validated token to request state
        request.state.token = token
        request.state.authenticated = True
        
        return await call_next(request)
    

    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract token from request headers"""
        token = request.headers.get("token")
        return token if token else None
    

    def _validate_token(self, token: str) -> bool:
        """
        Validate the authentication token
        Override this method to implement your token validation logic
        """
        if not token or len(token.strip()) == 0:
            return False

        return token == os.getenv("API_TOKEN")