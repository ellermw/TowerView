"""
Rate limiting for authentication endpoints
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
from fastapi import Request, HTTPException, status
import hashlib
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter for authentication attempts"""

    def __init__(self, max_attempts: int = 5, window_minutes: int = 15):
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self.attempts: Dict[str, list] = {}

    def _get_client_id(self, request: Request, username: Optional[str] = None) -> str:
        """Generate a unique client identifier"""
        client_ip = request.client.host if request.client else "unknown"

        # Combine IP with username for more granular tracking
        if username:
            identifier = f"{client_ip}:{username}"
        else:
            identifier = client_ip

        # Hash the identifier for privacy
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]

    def _cleanup_old_attempts(self, client_id: str):
        """Remove attempts older than the time window"""
        if client_id not in self.attempts:
            return

        cutoff = datetime.utcnow() - timedelta(minutes=self.window_minutes)
        self.attempts[client_id] = [
            attempt for attempt in self.attempts[client_id]
            if attempt > cutoff
        ]

        # Remove empty entries
        if not self.attempts[client_id]:
            del self.attempts[client_id]

    def check_rate_limit(self, request: Request, username: Optional[str] = None) -> None:
        """
        Check if the client has exceeded the rate limit
        Raises HTTPException if limit exceeded
        """
        client_id = self._get_client_id(request, username)
        self._cleanup_old_attempts(client_id)

        if client_id in self.attempts:
            recent_attempts = self.attempts[client_id]
            if len(recent_attempts) >= self.max_attempts:
                # Calculate time until next attempt allowed
                oldest_attempt = min(recent_attempts)
                reset_time = oldest_attempt + timedelta(minutes=self.window_minutes)
                seconds_remaining = (reset_time - datetime.utcnow()).total_seconds()

                logger.warning(f"Rate limit exceeded for client {client_id[:8]}...")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many login attempts. Please try again in {int(seconds_remaining)} seconds."
                )

    def record_attempt(self, request: Request, username: Optional[str] = None):
        """Record a login attempt"""
        client_id = self._get_client_id(request, username)

        if client_id not in self.attempts:
            self.attempts[client_id] = []

        self.attempts[client_id].append(datetime.utcnow())

        # Log if approaching limit
        attempts_count = len(self.attempts[client_id])
        if attempts_count == self.max_attempts - 1:
            logger.info(f"Client {client_id[:8]}... has {attempts_count} attempts, one more until rate limit")

    def reset_client(self, request: Request, username: Optional[str] = None):
        """Reset attempts for a client (e.g., after successful login)"""
        client_id = self._get_client_id(request, username)
        if client_id in self.attempts:
            del self.attempts[client_id]


# Global rate limiter instances
auth_limiter = RateLimiter(max_attempts=5, window_minutes=15)
aggressive_limiter = RateLimiter(max_attempts=3, window_minutes=30)  # For sensitive endpoints