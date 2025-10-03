"""
Library management endpoints
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import logging

from ....core.database import get_db
from ....core.security import get_current_admin_user, get_current_admin_or_local_user
from ....models.user import User, UserType
from ....services.server_service import ServerService
from ....services.user_service import UserService
from ....services.audit_service import AuditService
from ....providers.factory import ProviderFactory
from ....models.permissions import UserPermission

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/servers/{server_id}/libraries")
async def get_server_libraries(
    server_id: int,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get all libraries from a server"""
    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Check permissions
    if current_user.type.value in ["admin", "staff", "support"]:
        # Admin/staff must own the server
        if server.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this server"
            )
    else:
        # Local users need permission
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()

        if not permission or not permission.can_view_servers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this server"
            )

    try:
        provider = ProviderFactory.create_provider(server, db)
        await provider.initialize()

        # Check if the provider has the list_libraries method
        if hasattr(provider, 'list_libraries'):
            libraries = await provider.list_libraries()
            return libraries
        else:
            # Fallback for providers that don't have this method yet
            return []

    except Exception as e:
        logger.error(f"Failed to get libraries from server {server.name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch libraries: {str(e)}"
        )


@router.get("/servers/{server_id}/users/{user_id}/libraries")
async def get_user_library_access(
    server_id: int,
    user_id: str,  # Provider user ID
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get a user's library access on a server"""
    server_service = ServerService(db)
    user_service = UserService(db)
    server = server_service.get_server_by_id(server_id)

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Check permissions
    if current_user.type == UserType.admin:
        # Admin must own the server
        if server.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    elif current_user.type == UserType.local_user:
        # Local user needs permission to manage servers
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()

        if not permission or not permission.can_manage_servers:
            raise HTTPException(status_code=403, detail="No permission to manage this server")

    # Initialize provider and get user's library access
    try:
        logger.info(f"========== ADMIN ROUTE: Getting library access for user {user_id} on server {server.name} (type: {server.type}) ==========")

        provider = ProviderFactory.create_provider(server, db)
        await provider.initialize()

        # Check if the provider has the get_user_library_access method
        if hasattr(provider, 'get_user_library_access'):
            logger.info(f"Provider {provider.__class__.__name__} has get_user_library_access method")
            library_access = await provider.get_user_library_access(user_id)
            logger.info(f"Library access for user {user_id}: {library_access}")
            return library_access
        else:
            # Fallback for providers that don't have this method yet
            logger.warning(f"Provider {provider.__class__.__name__} doesn't have get_user_library_access method")
            return {"library_ids": [], "all_libraries": False}
    except Exception as e:
        logger.error(f"Failed to get library access for user {user_id} on server {server.name}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {"library_ids": [], "all_libraries": False}


@router.post("/servers/{server_id}/users/{user_id}/libraries")
async def set_user_library_access(
    server_id: int,
    user_id: str,  # Provider user ID
    library_data: Dict[str, Any],
    request: Request,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Set a user's library access on a server"""
    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Check permissions (same as get_user_library_access)
    if current_user.type == UserType.admin:
        if server.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    elif current_user.type == UserType.local_user:
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()

        if not permission or not permission.can_manage_servers:
            raise HTTPException(status_code=403, detail="No permission to manage this server")

    try:
        provider = ProviderFactory.create_provider(server, db)
        await provider.initialize()

        # Check if the provider has the set_user_library_access method
        if hasattr(provider, 'set_user_library_access'):
            all_libraries = library_data.get("all_libraries", False)
            library_ids = library_data.get("library_ids", [])

            success = await provider.set_user_library_access(user_id, library_ids, all_libraries)

            if success:
                # Log the action
                AuditService.log_user_library_access_changed(
                    db, current_user, user_id, server.name,
                    "all" if all_libraries else f"{len(library_ids)} libraries",
                    request
                )
                return {"success": True, "message": "Library access updated successfully"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update library access"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Library management not supported for {server.type.value} servers"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set library access for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update library access: {str(e)}"
        )


@router.get("/libraries/stats")
async def get_library_statistics(
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get statistics about library usage across all servers"""
    from ....models.playback_analytics import PlaybackEvent
    from sqlalchemy import func

    # Get allowed servers for local users
    allowed_server_ids = None
    if current_user.type == UserType.local_user:
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.can_view_servers == True
        ).all()

        if not permissions:
            return {"libraries": [], "total_plays": 0}

        allowed_server_ids = [p.server_id for p in permissions]

    # Build query
    query = db.query(
        PlaybackEvent.library,
        func.count(PlaybackEvent.id).label("play_count"),
        func.count(func.distinct(PlaybackEvent.username)).label("unique_users")
    )

    if allowed_server_ids:
        query = query.filter(PlaybackEvent.server_id.in_(allowed_server_ids))

    # Group by library
    results = query.group_by(PlaybackEvent.library).order_by(
        func.count(PlaybackEvent.id).desc()
    ).limit(10).all()

    libraries = []
    total_plays = 0

    for result in results:
        libraries.append({
            "name": result.library,
            "play_count": result.play_count,
            "unique_users": result.unique_users
        })
        total_plays += result.play_count

    return {
        "libraries": libraries,
        "total_plays": total_plays
    }