"""
Portainer Authentication Service
Handles automatic token refresh for Portainer API
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
import aiohttp
from sqlalchemy.orm import Session

from ..models.settings import PortainerIntegration

logger = logging.getLogger(__name__)


class PortainerAuthService:
    """Service to handle Portainer authentication with automatic token refresh"""

    @staticmethod
    def is_token_expired(token: str) -> bool:
        """Check if a JWT token is expired or about to expire"""
        if not token:
            return True

        # If it's an API key (starts with ptr_), it doesn't expire
        if token.startswith("ptr_"):
            return False

        try:
            # Decode without verification to check expiry
            decoded = jwt.decode(token, options={"verify_signature": False})
            exp = decoded.get('exp')

            if not exp:
                return True

            # Consider token expired if it expires in less than 5 minutes
            expiry_time = datetime.fromtimestamp(exp)
            buffer_time = datetime.utcnow() + timedelta(minutes=5)

            return expiry_time <= buffer_time

        except Exception as e:
            logger.error(f"Error checking token expiry: {e}")
            return True

    @staticmethod
    async def get_fresh_token(db: Session, integration: PortainerIntegration) -> Optional[str]:
        """Get a fresh token, refreshing if necessary"""

        # If we have a valid API key, return it
        if integration.api_token and integration.api_token.startswith("ptr_"):
            return integration.api_token

        # Check if current JWT token is still valid
        if integration.api_token and not PortainerAuthService.is_token_expired(integration.api_token):
            return integration.api_token

        # Token is expired or missing, try to refresh using stored credentials
        if not integration.username or not integration.password:
            logger.error("No credentials stored to refresh Portainer token")
            return None

        # Authenticate with Portainer
        new_token = await PortainerAuthService.authenticate(
            integration.url,
            integration.username,
            integration.password
        )

        if new_token:
            # Update the token in database
            integration.api_token = new_token
            integration.updated_at = datetime.utcnow()
            db.commit()
            logger.info("Successfully refreshed Portainer token")
            return new_token

        logger.error("Failed to refresh Portainer token")
        return None

    @staticmethod
    async def authenticate(url: str, username: str, password: str) -> Optional[str]:
        """Authenticate with Portainer and get JWT token"""
        auth_url = f"{url}/api/auth"
        data = {
            "username": username,
            "password": password
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(auth_url, json=data, ssl=False) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("jwt")
                    else:
                        error = await response.text()
                        logger.error(f"Portainer auth failed: {error}")
                        return None

        except Exception as e:
            logger.error(f"Error connecting to Portainer: {e}")
            return None

    @staticmethod
    async def validate_token(url: str, token: str, endpoint_id: int = 1) -> bool:
        """Validate if a token works with Portainer"""
        if not token:
            return False

        # Check if token is an API key or JWT
        if token.startswith("ptr_"):
            headers = {"X-API-Key": token}
        else:
            headers = {"Authorization": f"Bearer {token}"}

        try:
            test_url = f"{url}/api/endpoints/{endpoint_id}/docker/containers/json"
            async with aiohttp.ClientSession() as session:
                async with session.get(test_url, headers=headers, ssl=False) as response:
                    return response.status == 200

        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return False