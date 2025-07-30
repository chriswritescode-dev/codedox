"""Authentication middleware and utilities for CodeDox API."""

import logging
from typing import Optional
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Security scheme for bearer token
security = HTTPBearer(auto_error=False)


class MCPAuthMiddleware:
    """Middleware for MCP authentication."""
    
    def __init__(self):
        """Initialize the middleware."""
        self.settings = settings.mcp_auth
    
    async def __call__(self, request: Request, credentials: Optional[HTTPAuthorizationCredentials] = None) -> bool:
        """Verify MCP authentication.
        
        Args:
            request: The FastAPI request object
            credentials: Optional bearer token credentials
            
        Returns:
            True if authenticated, raises HTTPException otherwise
        """
        # Skip auth if not enabled
        if not self.settings.enabled:
            return True
        
        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning(f"MCP auth failed: No Authorization header from {request.client.host}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Extract token from header
        try:
            scheme, token = auth_header.split(" ", 1)
            if scheme.lower() != "bearer":
                raise ValueError("Invalid authentication scheme")
        except ValueError:
            logger.warning(f"MCP auth failed: Invalid Authorization header format from {request.client.host}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Validate token
        if not self.settings.is_token_valid(token):
            logger.warning(f"MCP auth failed: Invalid token from {request.client.host}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.debug(f"MCP auth successful for {request.client.host}")
        return True


# Singleton instance
mcp_auth = MCPAuthMiddleware()


async def verify_mcp_token(request: Request, credentials: HTTPAuthorizationCredentials = security) -> bool:
    """Dependency for MCP authentication.
    
    Use this as a dependency in FastAPI routes:
    ```python
    @router.get("/protected", dependencies=[Depends(verify_mcp_token)])
    async def protected_route():
        return {"message": "Authenticated!"}
    ```
    """
    return await mcp_auth(request, credentials)


def get_bearer_token(auth_header: Optional[str]) -> Optional[str]:
    """Extract bearer token from authorization header.
    
    Args:
        auth_header: The Authorization header value
        
    Returns:
        The token if valid bearer format, None otherwise
    """
    if not auth_header:
        return None
    
    try:
        scheme, token = auth_header.split(" ", 1)
        if scheme.lower() == "bearer":
            return token
    except ValueError:
        pass
    
    return None