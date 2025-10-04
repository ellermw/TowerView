from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import httpx
import uuid
from datetime import datetime

from ...core.database import get_db
from ...core.security import verify_token, get_current_user
from ...core.rate_limiter import auth_limiter
from ...schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest, ChangePasswordRequest
from ...services.auth_service import AuthService
from ...services.audit_service import AuditService
from ...models.server import Server, ServerType
from ...models.user import User, UserType

router = APIRouter()

# OAuth response models
class PlexOAuthInitResponse(BaseModel):
    pin_id: str
    pin_code: str
    auth_url: str
    expires_at: str
    client_id: str  # Need to preserve this for checking

class PlexOAuthCompleteRequest(BaseModel):
    pin_id: str
    client_id: str  # Need this to check the PIN

class MediaAuthRequest(BaseModel):
    provider: str  # plex, emby, jellyfin
    username: Optional[str] = None
    password: Optional[str] = None
    auth_token: Optional[str] = None  # For Plex OAuth
    server_url: Optional[str] = None  # For Emby/Jellyfin direct connection


@router.post("/media/oauth/plex/init")
async def initiate_plex_oauth(request: Request):
    """Initiate Plex OAuth flow"""
    import os

    client_id = str(uuid.uuid4())

    # Get the frontend URL from environment variable or request headers
    frontend_url = os.getenv("FRONTEND_URL")

    if not frontend_url:
        # Try to get from Origin header
        origin = request.headers.get("origin")
        if origin:
            frontend_url = origin
        else:
            # Try to get from Referer header
            referer = request.headers.get("referer")
            if referer:
                # Extract the origin from referer
                from urllib.parse import urlparse
                parsed = urlparse(referer)
                frontend_url = f"{parsed.scheme}://{parsed.netloc}"
            else:
                # Fallback to localhost
                frontend_url = "http://localhost:8080"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://plex.tv/api/v2/pins",
            headers={
                "X-Plex-Client-Identifier": client_id,
                "X-Plex-Product": "TowerView",
                "X-Plex-Device": "TowerView",
                "X-Plex-Device-Name": "TowerView",
                "X-Plex-Version": "1.0.0",
                "X-Plex-Platform": "Web",
                "Accept": "application/json"
            },
            json={
                "strong": True,  # Request a strong PIN
                "trusted": True  # Mark as trusted application for better performance
            }
        )

        if response.status_code != 201:
            raise HTTPException(status_code=400, detail="Failed to initiate OAuth flow")

        data = response.json()

        # Create the auth URL - use the correct OAuth format without hash
        # The forwardUrl parameter helps Plex know this is an OAuth flow
        auth_app_url = f"https://app.plex.tv/auth?clientID={client_id}&code={data['code']}&context%5Bdevice%5D%5Bproduct%5D=TowerView&forwardUrl={frontend_url}"

        return PlexOAuthInitResponse(
            pin_id=str(data["id"]),
            pin_code=data["code"],
            auth_url=auth_app_url,
            expires_at=data["expiresAt"],
            client_id=client_id  # Return the client ID so we can use it for checking
        )


@router.post("/media/oauth/plex/check")
async def check_plex_oauth(request: PlexOAuthCompleteRequest):
    """Check if Plex OAuth is complete"""
    import logging
    from datetime import datetime, timezone
    logger = logging.getLogger(__name__)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://plex.tv/api/v2/pins/{request.pin_id}",
            headers={
                "X-Plex-Client-Identifier": request.client_id,  # Must use same client ID
                "Accept": "application/json"
            }
        )

        if response.status_code == 404:
            logger.error(f"PIN not found or expired: {request.pin_id}")
            raise HTTPException(status_code=404, detail="PIN not found or expired. Please restart the authentication process.")

        if response.status_code != 200:
            logger.error(f"Failed to check PIN: {response.status_code} - {response.text}")
            raise HTTPException(status_code=400, detail="Failed to check authentication status")

        data = response.json()
        auth_token = data.get("authToken")
        expires_at = data.get("expiresAt")
        errors = data.get("errors", [])

        # Check if PIN has expired
        if expires_at:
            try:
                expiry_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if datetime.now(timezone.utc) > expiry_time:
                    logger.error(f"PIN has expired: {request.pin_id}")
                    raise HTTPException(status_code=410, detail="Authentication PIN has expired. Please restart the authentication process.")
            except ValueError:
                logger.warning(f"Could not parse expiry time: {expires_at}")

        # Check for any errors from Plex
        if errors:
            logger.error(f"Plex PIN errors: {errors}")
            raise HTTPException(status_code=400, detail=f"Authentication error: {', '.join(str(e) for e in errors)}")

        # Log the response for debugging
        logger.info(f"Plex PIN check response - PIN: {request.pin_id}, Has token: {bool(auth_token)}, Errors: {errors}, Full response: {data}")

        if auth_token:
            # Get user's accessible servers
            servers_response = await client.get(
                "https://plex.tv/api/v2/resources",
                headers={
                    "X-Plex-Token": auth_token,
                    "Accept": "application/json"
                },
                params={
                    "includeHttps": "1",
                    "includeRelay": "1"
                }
            )

            servers = []
            if servers_response.status_code == 200:
                resources = servers_response.json()
                servers = [
                    {
                        "name": r["name"],
                        "machine_id": r["clientIdentifier"],
                        "connections": r.get("connections", [])
                    }
                    for r in resources
                    if r.get("product") == "Plex Media Server"
                ]

            return {
                "authenticated": True,
                "auth_token": auth_token,
                "servers": servers
            }

        return {"authenticated": False}


@router.post("/media/authenticate")
async def authenticate_media_user(
    auth_data: MediaAuthRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticate user with their media server"""

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Media authentication request: provider={auth_data.provider}, username={auth_data.username}, has_token={bool(auth_data.auth_token)}")

    # Find matching servers in our database
    if auth_data.provider == "plex" and auth_data.auth_token:
        # Plex OAuth authentication
        logger.info("Processing Plex OAuth authentication")
        # Get user's Plex servers
        async with httpx.AsyncClient() as client:
            servers_response = await client.get(
                "https://plex.tv/api/v2/resources",
                headers={
                    "X-Plex-Token": auth_data.auth_token,
                    "Accept": "application/json"
                },
                params={
                    "includeHttps": "1",
                    "includeRelay": "1"
                }
            )

            if servers_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Plex token")

            resources = servers_response.json()
            plex_servers = [r for r in resources if r.get("product") == "Plex Media Server"]

            if not plex_servers:
                raise HTTPException(status_code=404, detail="No Plex servers found for this account")

            # Match with servers in our database
            for plex_server in plex_servers:
                # Try to find by machine ID or URL
                for connection in plex_server.get("connections", []):
                    uri = connection.get("uri", "")
                    # Check if this server exists in our database
                    server = db.query(Server).filter(
                        Server.type == ServerType.plex,
                        Server.enabled == True,
                        Server.base_url.contains(uri.replace("http://", "").replace("https://", "").split(":")[0])
                    ).first()

                    if server:
                        # Found a matching server - authenticate user
                        # Get user info from Plex
                        user_response = await client.get(
                            "https://plex.tv/api/v2/user",
                            headers={
                                "X-Plex-Token": auth_data.auth_token,
                                "Accept": "application/json"
                            }
                        )

                        user_data = user_response.json() if user_response.status_code == 200 else {}

                        # Create or update user
                        user = db.query(User).filter(
                            User.provider_user_id == str(user_data.get("id", "")),
                            User.server_id == server.id,
                            User.type == UserType.media_user
                        ).first()

                        if not user:
                            user = User(
                                type=UserType.media_user,
                                provider=auth_data.provider,
                                provider_user_id=str(user_data.get("id", "")),
                                server_id=server.id,
                                username=user_data.get("username", "plex_user"),
                                email=user_data.get("email")
                            )
                            db.add(user)
                        else:
                            user.username = user_data.get("username", user.username)
                            user.email = user_data.get("email", user.email)

                        user.last_login_at = datetime.utcnow()
                        db.commit()
                        db.refresh(user)

                        # Log successful login
                        AuditService.log_login(db, user, request)

                        # Create tokens
                        auth_service = AuthService(db)
                        return auth_service.create_tokens(user)

            raise HTTPException(
                status_code=404,
                detail="Your Plex account is not associated with any servers in this system"
            )

    elif auth_data.provider == "plex" and auth_data.username and auth_data.password:
        # Plex direct username/password authentication (fallback from OAuth)
        logger.info("Processing Plex direct authentication")

        # Use smart server selection for Plex too
        from ...services.users_cache_service import users_cache_service
        cached_users = users_cache_service.get_cached_users()

        matching_servers = []
        if cached_users and isinstance(cached_users, dict):
            for server_id, users_list in cached_users.items():
                for user in users_list:
                    if user.get('username', '').lower() == auth_data.username.lower():
                        server = db.query(Server).filter(
                            Server.id == server_id,
                            Server.type == ServerType.plex,
                            Server.enabled == True
                        ).first()
                        if server and server not in matching_servers:
                            logger.info(f"Smart match: Found Plex user '{auth_data.username}' on server '{server.name}'")
                            matching_servers.insert(0, server)
                        break

        # Add all other Plex servers as fallback
        all_plex_servers = db.query(Server).filter(
            Server.type == ServerType.plex,
            Server.enabled == True
        ).all()
        for server in all_plex_servers:
            if server not in matching_servers:
                matching_servers.append(server)

        if not matching_servers:
            raise HTTPException(status_code=404, detail="No Plex servers are configured")

        # Try authentication against each server
        for server in matching_servers:
            try:
                from ...providers.factory import ProviderFactory
                provider = ProviderFactory.create_provider(server, db)
                logger.info(f"Trying Plex authentication on server: {server.name}")

                auth_result = await provider.authenticate_user(
                    auth_data.username,
                    auth_data.password
                )

                if auth_result:
                    # Similar user creation/update logic as above
                    provider_user_id = auth_result.get("user_id")
                    user_email = auth_result.get("email")

                    user = db.query(User).filter(
                        User.provider_user_id == provider_user_id,
                        User.server_id == server.id,
                        User.type == UserType.media_user
                    ).first()

                    if not user:
                        user = User(
                            type=UserType.media_user,
                            provider="plex",
                            provider_user_id=provider_user_id,
                            server_id=server.id,
                            username=auth_data.username,
                            email=user_email
                        )
                        db.add(user)
                    else:
                        user.username = auth_data.username
                        user.email = user_email

                    user.last_login_at = datetime.utcnow()
                    db.commit()
                    db.refresh(user)

                    AuditService.log_login(db, user, request)
                    auth_service = AuthService(db)
                    logger.info(f"Plex authentication successful for user '{auth_data.username}'")
                    return auth_service.create_tokens(user)
            except Exception as e:
                logger.warning(f"Plex authentication failed on server '{server.name}': {str(e)}")
                continue

        raise HTTPException(
            status_code=401,
            detail="Authentication failed. Please check your Plex username and password."
        )

    elif auth_data.provider in ["emby", "jellyfin"]:
        # Smart server selection - check users cache first

        from ...services.users_cache_service import users_cache_service
        cached_users = users_cache_service.get_cached_users()

        # Find servers where this username exists
        matching_servers = []
        if cached_users and isinstance(cached_users, dict):
            for server_id, users_list in cached_users.items():
                # Check if username exists in this server's user list
                for user in users_list:
                    if user.get('username', '').lower() == auth_data.username.lower():
                        # Found a match - prioritize this server
                        server = db.query(Server).filter(
                            Server.id == server_id,
                            Server.type == (ServerType.emby if auth_data.provider == "emby" else ServerType.jellyfin),
                            Server.enabled == True
                        ).first()
                        if server and server not in matching_servers:
                            logger.info(f"Smart match: Found user '{auth_data.username}' on server '{server.name}' (ID: {server.id})")
                            matching_servers.insert(0, server)  # Priority server
                        break

        # Get all servers of this type as fallback
        all_servers = db.query(Server).filter(
            Server.type == (ServerType.emby if auth_data.provider == "emby" else ServerType.jellyfin),
            Server.enabled == True
        ).all()

        # Add remaining servers that weren't in the priority list
        for server in all_servers:
            if server not in matching_servers:
                matching_servers.append(server)

        if not matching_servers:
            raise HTTPException(
                status_code=404,
                detail=f"No {auth_data.provider.title()} servers are configured"
            )

        logger.info(f"Attempting authentication for '{auth_data.username}' against {len(matching_servers)} servers (prioritized)")

        for server in matching_servers:
            try:
                # Try to authenticate with this server
                from ...providers.factory import ProviderFactory
                provider = ProviderFactory.create_provider(server, db)
                logger.info(f"Trying authentication on server: {server.name} (ID: {server.id})")

                auth_result = await provider.authenticate_user(
                    auth_data.username,
                    auth_data.password
                )

                if auth_result:
                    # Authentication successful
                    provider_user_id = auth_result.get("user_id")
                    user_email = auth_result.get("email")

                    # Find or create user
                    user = db.query(User).filter(
                        User.provider_user_id == provider_user_id,
                        User.server_id == server.id,
                        User.type == UserType.media_user
                    ).first()

                    if not user:
                        user = User(
                            type=UserType.media_user,
                            provider=auth_data.provider,
                            provider_user_id=provider_user_id,
                            server_id=server.id,
                            username=auth_data.username,
                            email=user_email
                        )
                        db.add(user)
                    else:
                        user.username = auth_data.username
                        user.email = user_email

                    user.last_login_at = datetime.utcnow()
                    db.commit()
                    db.refresh(user)

                    # Log successful login
                    AuditService.log_login(db, user, request)

                    # Create tokens
                    auth_service = AuthService(db)
                    logger.info(f"Authentication successful for user '{auth_data.username}' on server '{server.name}'")
                    return auth_service.create_tokens(user)
            except Exception as e:
                # Log the error and try next server
                logger.warning(f"Authentication failed on server '{server.name}': {str(e)}")
                continue

        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed. Please check your {auth_data.provider.title()} username and password."
        )

    else:
        raise HTTPException(status_code=400, detail="Invalid authentication method")


@router.get("/servers/available")
async def get_available_servers(db: Session = Depends(get_db)):
    """Get list of enabled servers available for authentication"""
    from ...models.server import Server, ServerType

    servers = db.query(Server).filter(
        Server.enabled == True,
        Server.type.in_([ServerType.plex, ServerType.emby, ServerType.jellyfin])
    ).all()

    return [
        {
            "id": server.id,
            "name": server.name,
            "type": server.type.value,
            "base_url": server.base_url
        }
        for server in servers
    ]


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Login with either admin credentials or media user credentials"""
    import logging
    logger = logging.getLogger(__name__)

    # Extract username for rate limiting
    username = None
    if login_data.admin_login:
        username = login_data.admin_login.username
    elif login_data.local_login:
        username = login_data.local_login.username
    elif login_data.media_login:
        username = login_data.media_login.username

    # Check rate limit before processing
    auth_limiter.check_rate_limit(request, username)

    logger.info(f"Login request received: admin={bool(login_data.admin_login)}, media={bool(login_data.media_login)}, local={bool(login_data.local_login)}")
    if login_data.admin_login:
        logger.info(f"Admin login attempt: {login_data.admin_login.username}")
    if login_data.local_login:
        logger.info(f"Local login attempt: {login_data.local_login.username}")

    auth_service = AuthService(db)

    user = None
    try:
        if login_data.admin_login:
            user = await auth_service.authenticate_admin(login_data.admin_login)
            if not user:
                # Record failed attempt
                auth_limiter.record_attempt(request, username)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )

        elif login_data.media_login:
            user = await auth_service.authenticate_media_user(login_data.media_login)
            if not user:
                # Record failed attempt
                auth_limiter.record_attempt(request, username)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid media user credentials"
                )

        elif login_data.local_login:
            # Local user login
            from ...models.user import UserType
            user = auth_service.authenticate_local_user(
                login_data.local_login.username,
                login_data.local_login.password
            )

            if not user:
                # Record failed attempt
                auth_limiter.record_attempt(request, username)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid local user credentials"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either admin_login, media_login, or local_login"
            )

        # Reset rate limit on successful login
        auth_limiter.reset_client(request, username)

        # Log successful login
        AuditService.log_login(db, user, request)

        return auth_service.create_tokens(user)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed due to an internal error"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    payload = verify_token(refresh_data.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Get user and create new tokens
    from ...services.user_service import UserService
    user_service = UserService(db)
    user = user_service.get_user_by_id(int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    auth_service = AuthService(db)
    return auth_service.create_tokens(user)


@router.post("/logout")
async def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Logout (client should discard tokens)"""
    # Log logout if user is authenticated
    if current_user:
        AuditService.log_logout(db, current_user, request)
    return {"message": "Logout successful"}


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Change password for the current user"""
    from ...core.security import verify_password, get_password_hash, verify_token
    from ...models.user import UserType

    # Get token from header
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )

    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    # Get user
    from ...services.user_service import UserService
    user_service = UserService(db)
    user = user_service.get_user_by_id(int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Validate new passwords match
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match"
        )

    # Verify current password
    if not verify_password(password_data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )

    # Update password
    user.password_hash = get_password_hash(password_data.new_password)
    user.must_change_password = False
    db.commit()

    return {"message": "Password changed successfully"}


@router.get("/me")
async def get_current_user_info(
    current_user = Depends(lambda: None)  # This will be implemented properly later
):
    """Get current user information"""
    from ...core.security import get_current_user
    from ...schemas.user import UserResponse
    # TODO: Implement properly with dependency injection
    return {"message": "User info endpoint - to be implemented"}