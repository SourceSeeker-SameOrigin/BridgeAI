"""Security headers middleware -- adds defense-in-depth HTTP headers to all responses."""

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security-related HTTP headers to every response.

    Headers:
      - X-Content-Type-Options: nosniff
          Prevents MIME type sniffing.
      - X-Frame-Options: DENY
          Prevents clickjacking by disabling iframe embedding.
      - X-XSS-Protection: 1; mode=block
          Legacy XSS filter for older browsers.
      - Strict-Transport-Security (HSTS)
          Forces HTTPS connections (only for HTTPS requests).
      - Content-Security-Policy
          Restricts resource loading origins.
      - Referrer-Policy
          Limits referrer information leakage.
      - Permissions-Policy
          Restricts browser feature access.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Legacy XSS protection for older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HSTS -- only set when the request was received over HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss: https:; "
            "frame-ancestors 'none'"
        )

        # Limit referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        return response
