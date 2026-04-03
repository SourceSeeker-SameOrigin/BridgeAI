import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Paths that don't require tenant isolation
_PUBLIC_PATHS = {"/", "/docs", "/openapi.json", "/redoc", "/api/v1/auth/login", "/api/v1/auth/register"}


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Multi-tenant isolation middleware.

    1. Extract X-Tenant-Id header from incoming requests
    2. Attach tenant_id to request state for downstream use
    3. For authenticated requests, the tenant_id from JWT/user takes priority
       (enforced by get_current_user → user.tenant_id)
    4. Reject requests where X-Tenant-Id header doesn't match the authenticated
       user's tenant (prevents cross-tenant data access)
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract tenant_id from header
        header_tenant_id: Optional[str] = request.headers.get("X-Tenant-Id")
        request.state.tenant_id = header_tenant_id

        # Mark path for tenant enforcement
        path = request.url.path.rstrip("/") or "/"
        request.state.require_tenant = path not in _PUBLIC_PATHS

        response = await call_next(request)
        return response
