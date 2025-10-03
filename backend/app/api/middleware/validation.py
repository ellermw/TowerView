"""
Validation Middleware
Provides request validation and sanitization
"""
from typing import Callable, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class ValidationMiddleware:
    """
    Middleware for validating and sanitizing incoming requests
    """

    def __init__(self):
        self.max_request_size = 10 * 1024 * 1024  # 10MB
        self.blocked_patterns = [
            r'<script',
            r'javascript:',
            r'on\w+\s*=',  # onclick, onload, etc.
            r'\.\./',  # Path traversal
            r'%00',  # Null byte injection
            r'\x00',  # Null byte
            r'union\s+select',  # SQL injection patterns
            r'drop\s+table',
            r'insert\s+into',
            r'delete\s+from',
            r'update\s+set',
            r'exec\(',
            r'execute\(',
            r'xp_cmdshell',
            r'sp_executesql',
        ]
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.blocked_patterns]

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Process the request through validation"""
        try:
            # Check request size
            if request.headers.get('content-length'):
                content_length = int(request.headers['content-length'])
                if content_length > self.max_request_size:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={"detail": "Request too large"}
                    )

            # Validate path
            if not self._validate_path(request.url.path):
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid request path"}
                )

            # Validate query parameters
            for key, value in request.query_params.items():
                if not self._validate_input(key) or not self._validate_input(value):
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"detail": f"Invalid query parameter: {key}"}
                    )

            # Validate headers
            suspicious_headers = ['x-forwarded-host', 'x-original-url', 'x-rewrite-url']
            for header in suspicious_headers:
                if header in request.headers:
                    logger.warning(f"Suspicious header detected: {header} from {request.client.host}")

            # Process the request
            response = await call_next(request)

            # Add security headers to response
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            return response

        except Exception as e:
            logger.error(f"Validation middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )

    def _validate_path(self, path: str) -> bool:
        """Validate request path"""
        # Check for path traversal
        if '..' in path or '//' in path:
            return False

        # Check for null bytes
        if '\x00' in path or '%00' in path:
            return False

        # Check path length
        if len(path) > 2048:
            return False

        return True

    def _validate_input(self, value: str) -> bool:
        """Validate input for malicious patterns"""
        if not value:
            return True

        # Check against blocked patterns
        for pattern in self.compiled_patterns:
            if pattern.search(value):
                logger.warning(f"Blocked pattern detected: {pattern.pattern} in value: {value[:100]}")
                return False

        return True


class RateLimitMiddleware:
    """
    Rate limiting middleware to prevent abuse
    """

    def __init__(self):
        self.requests = {}  # Simple in-memory store
        self.max_requests = 100  # Max requests per minute
        self.window_seconds = 60

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting"""
        client_id = self._get_client_id(request)
        current_time = datetime.utcnow()

        # Clean old entries
        self._clean_old_entries(current_time)

        # Check rate limit
        if client_id in self.requests:
            requests_in_window = self.requests[client_id]
            if len(requests_in_window) >= self.max_requests:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many requests. Please try again later."}
                )
            requests_in_window.append(current_time)
        else:
            self.requests[client_id] = [current_time]

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            self.max_requests - len(self.requests.get(client_id, []))
        )
        response.headers["X-RateLimit-Reset"] = str(
            int((current_time.timestamp() + self.window_seconds))
        )

        return response

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Use IP address as client ID
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return client_ip

    def _clean_old_entries(self, current_time: datetime):
        """Remove entries older than the time window"""
        cutoff_time = current_time.timestamp() - self.window_seconds

        for client_id in list(self.requests.keys()):
            # Filter out old requests
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id]
                if req_time.timestamp() > cutoff_time
            ]

            # Remove client if no requests remain
            if not self.requests[client_id]:
                del self.requests[client_id]


class SanitizationMiddleware:
    """
    Middleware for sanitizing output data
    """

    def __init__(self):
        self.sensitive_keys = [
            'password',
            'token',
            'api_key',
            'secret',
            'credential',
            'auth',
            'private',
        ]

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Process response to sanitize sensitive data in logs"""
        response = await call_next(request)

        # Log sanitized request
        self._log_request(request)

        return response

    def _log_request(self, request: Request):
        """Log request with sensitive data removed"""
        safe_headers = {}
        for key, value in request.headers.items():
            if any(sensitive in key.lower() for sensitive in self.sensitive_keys):
                safe_headers[key] = "***REDACTED***"
            else:
                safe_headers[key] = value

        logger.info(f"Request: {request.method} {request.url.path}")
        logger.debug(f"Headers: {safe_headers}")

    def _sanitize_dict(self, data: dict) -> dict:
        """Recursively sanitize dictionary"""
        sanitized = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in self.sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized


class ContentTypeValidationMiddleware:
    """
    Validate content types for requests
    """

    def __init__(self):
        self.allowed_content_types = [
            'application/json',
            'application/x-www-form-urlencoded',
            'multipart/form-data',
            'text/plain',
        ]

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Validate content type"""
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get('content-type', '').lower()

            # Extract base content type (ignore charset, etc.)
            if ';' in content_type:
                content_type = content_type.split(';')[0].strip()

            # Check if content type is allowed
            if content_type and not any(
                allowed in content_type for allowed in self.allowed_content_types
            ):
                return JSONResponse(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    content={"detail": f"Unsupported content type: {content_type}"}
                )

        return await call_next(request)


class InputSizeMiddleware:
    """
    Validate input sizes to prevent abuse
    """

    def __init__(self):
        self.max_string_length = 10000
        self.max_array_length = 1000
        self.max_json_depth = 10

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Check input sizes"""
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Only check JSON bodies
                if "application/json" in request.headers.get("content-type", ""):
                    body = await request.body()
                    if body:
                        import json
                        data = json.loads(body)
                        if not self._validate_json_size(data):
                            return JSONResponse(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                content={"detail": "Input exceeds size limits"}
                            )
            except Exception as e:
                logger.error(f"Error validating input size: {e}")

        return await call_next(request)

    def _validate_json_size(self, data, depth=0) -> bool:
        """Recursively validate JSON size and depth"""
        if depth > self.max_json_depth:
            return False

        if isinstance(data, str):
            if len(data) > self.max_string_length:
                return False
        elif isinstance(data, list):
            if len(data) > self.max_array_length:
                return False
            for item in data:
                if not self._validate_json_size(item, depth + 1):
                    return False
        elif isinstance(data, dict):
            for key, value in data.items():
                if len(str(key)) > self.max_string_length:
                    return False
                if not self._validate_json_size(value, depth + 1):
                    return False

        return True