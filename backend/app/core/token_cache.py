"""
Redis-backed token cache for Plex authentication tokens
"""
import json
import redis
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from .config import settings
import logging

logger = logging.getLogger(__name__)


class TokenCache:
    """Persistent token cache using Redis"""

    def __init__(self):
        # Parse Redis URL to get connection parameters
        redis_url = settings.redis_url
        if redis_url.startswith("redis://"):
            # Extract host and port from URL
            # Format: redis://host:port or redis://host:port/db
            url_parts = redis_url.replace("redis://", "").split("/")[0]
            if ":" in url_parts:
                host, port = url_parts.split(":")
                port = int(port)
            else:
                host = url_parts
                port = 6379
        else:
            host = "localhost"
            port = 6379

        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=0,
            decode_responses=True
        )
        self.prefix = "plex_token:"
        self.ttl = 82800  # 23 hours in seconds

    def get_token(self, server_id: int) -> Optional[Dict[str, Any]]:
        """Get cached token data for a server"""
        try:
            key = f"{self.prefix}{server_id}"
            data = self.redis_client.get(key)
            if data:
                token_data = json.loads(data)
                # Check if token is expired
                expiry = datetime.fromisoformat(token_data.get("expiry", "1970-01-01"))
                if datetime.utcnow() < expiry:
                    logger.debug(f"Found valid cached token for server {server_id}")
                    return token_data
                else:
                    logger.debug(f"Cached token for server {server_id} is expired")
                    self.redis_client.delete(key)
            return None
        except Exception as e:
            logger.error(f"Error getting token from cache: {e}")
            return None

    def set_token(self, server_id: int, token: str, expiry: Optional[datetime] = None):
        """Cache a token for a server"""
        try:
            if not expiry:
                expiry = datetime.utcnow() + timedelta(hours=23)

            token_data = {
                "token": token,
                "expiry": expiry.isoformat(),
                "cached_at": datetime.utcnow().isoformat()
            }

            key = f"{self.prefix}{server_id}"
            self.redis_client.set(
                key,
                json.dumps(token_data),
                ex=self.ttl
            )
            logger.debug(f"Cached token for server {server_id} (expires: {expiry})")
        except Exception as e:
            logger.error(f"Error setting token in cache: {e}")

    def get_rate_limit_info(self, server_id: int) -> Optional[datetime]:
        """Get rate limit cooldown for a server"""
        try:
            key = f"{self.prefix}rate_limit:{server_id}"
            cooldown = self.redis_client.get(key)
            if cooldown:
                return datetime.fromisoformat(cooldown)
            return None
        except Exception as e:
            logger.error(f"Error getting rate limit info: {e}")
            return None

    def set_rate_limit(self, server_id: int, cooldown_minutes: int = 10):
        """Set rate limit cooldown for a server"""
        try:
            cooldown_until = datetime.utcnow() + timedelta(minutes=cooldown_minutes)
            key = f"{self.prefix}rate_limit:{server_id}"
            self.redis_client.set(
                key,
                cooldown_until.isoformat(),
                ex=cooldown_minutes * 60
            )
            logger.debug(f"Set rate limit cooldown for server {server_id} until {cooldown_until}")
        except Exception as e:
            logger.error(f"Error setting rate limit: {e}")

    def clear_token(self, server_id: int):
        """Clear cached token for a server"""
        try:
            key = f"{self.prefix}{server_id}"
            self.redis_client.delete(key)
            logger.debug(f"Cleared cached token for server {server_id}")
        except Exception as e:
            logger.error(f"Error clearing token: {e}")


# Global token cache instance
token_cache = TokenCache()