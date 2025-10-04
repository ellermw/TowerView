"""
User management endpoints
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from ....core.database import get_db
from ....core.security import (
    get_current_admin_user,
    get_current_admin_or_local_user,
    get_user_creation_allowed,
    get_user_deletion_allowed,
    get_password_hash
)
from ....models.user import User, UserType
from ....models.server import Server, ServerType
from ....models.user_permission import UserPermission
from ....schemas.user import (
    UserResponse,
    ServerUserResponse,
    LocalUserCreate,
    LocalUserUpdate,
    LocalUserResponse,
    UserPermissionSchema,
    UserPermissionUpdate,
    UserRoleUpdate
)
from ....services.user_service import UserService
from ....services.audit_service import AuditService
from ....providers.factory import ProviderFactory

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/users", response_model=List[ServerUserResponse])
async def get_all_users(
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get users from all servers (from cache)"""
    from ....services.users_cache_service import users_cache_service

    # Get users from cache instead of hitting servers directly
    cached_users = await users_cache_service.get_cached_users(
        user_id=current_user.id,
        user_type=current_user.type.value,
        db=db
    )

    return cached_users


@router.get("/servers/{server_id}/users", response_model=List[UserResponse])
async def get_server_users(
    server_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get users for a server"""
    from ....services.server_service import ServerService

    server_service = ServerService(db)
    server = server_service.get_server_by_id(server_id)

    if not server or server.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    user_service = UserService(db)
    users = user_service.get_users_by_server(server_id)
    return [UserResponse.from_orm(user) for user in users]


@router.get("/users/cache-status")
async def get_users_cache_status(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get the current status of the users cache"""
    from ....services.users_cache_service import users_cache_service

    return users_cache_service.get_cache_status()


@router.post("/users/refresh-cache")
async def refresh_users_cache(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Manually trigger a refresh of the users cache"""
    from ....services.users_cache_service import users_cache_service

    # Force a cache refresh
    await users_cache_service._collect_all_users()

    return {
        "message": "Users cache refresh triggered",
        "status": users_cache_service.get_cache_status()
    }


@router.post("/servers/{server_id}/users/{user_id}/password")
async def change_user_password(
    server_id: int,
    user_id: str,  # Provider user ID
    password_data: Dict[str, str],
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Change password for a media server user (Emby/Jellyfin only)"""
    # Get server
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Check if server supports password changes
    if server.type == ServerType.plex:
        raise HTTPException(status_code=400, detail="Password changes not supported for Plex servers")

    # Check permissions
    if current_user.type != UserType.admin:
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()

        if not permission or not permission.can_manage_servers:
            raise HTTPException(status_code=403, detail="No permission to manage this server")

    # Get password from request
    new_password = password_data.get("new_password")
    if not new_password:
        raise HTTPException(status_code=400, detail="New password is required")

    # Get provider and change password
    provider = ProviderFactory.create_provider(server, db)

    # Admin changing another user's password (no current password needed)
    success = await provider.change_user_password(user_id, new_password)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to change password")

    # Log the action
    AuditService.log_custom(
        db, current_user, "change_user_password",
        details=f"Changed password for user {user_id} on server {server.name}",
        request=None
    )

    return {"success": True, "message": "Password changed successfully"}


# Local User Management Endpoints

@router.get("/local-users", response_model=List[LocalUserResponse])
async def get_local_users(
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get all system users (non-media server users)"""
    # Get all non-media users (admin, staff, support, and legacy local_user)
    users = db.query(User).filter(
        User.type.in_([UserType.admin, UserType.staff, UserType.support, UserType.local_user])
    ).all()
    return users


@router.post("/local-users", response_model=LocalUserResponse)
async def create_local_user(
    user_data: LocalUserCreate,
    request: Request,
    current_user: User = Depends(get_user_creation_allowed),
    db: Session = Depends(get_db)
):
    """Create a new user (role based on creator's permissions)"""
    # Check if username already exists among local/staff users only (case-insensitive)
    # Media users are completely separate and can have the same username
    existing_user = db.query(User).filter(
        func.lower(User.username) == user_data.username.lower(),
        User.type.in_([UserType.admin, UserType.staff, UserType.support, UserType.local_user])
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists among system users"
        )

    # Determine what role the new user should have based on creator
    new_user_type = UserType.support  # Default to support

    if current_user.type == UserType.admin:
        # Admin can create any role
        if hasattr(user_data, 'role'):
            if user_data.role == 'admin':
                new_user_type = UserType.admin
            elif user_data.role == 'staff':
                new_user_type = UserType.staff
            else:
                new_user_type = UserType.support
        else:
            # Default to staff for backward compatibility
            new_user_type = UserType.staff
    elif current_user.type in [UserType.staff, UserType.local_user]:
        # Staff can only create support users
        new_user_type = UserType.support

    # Create new user
    new_user = User(
        type=new_user_type,
        username=user_data.username,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        must_change_password=user_data.must_change_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Log user creation
    AuditService.log_user_created(
        db, current_user, new_user.id, new_user.username, "local_user", request
    )

    return new_user


@router.get("/local-users/{user_id}", response_model=LocalUserResponse)
async def get_local_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get a specific local user"""
    user = db.query(User).filter(
        User.id == user_id,
        User.type == UserType.local_user
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@router.patch("/local-users/{user_id}", response_model=LocalUserResponse)
async def update_local_user(
    user_id: int,
    user_data: LocalUserUpdate,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update a local user"""
    user = db.query(User).filter(
        User.id == user_id,
        User.type == UserType.local_user
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Track changes for audit log
    changes = {}
    if user_data.email is not None and user_data.email != user.email:
        changes["email"] = {"old": user.email, "new": user_data.email}
        user.email = user_data.email
    if user_data.password is not None:
        changes["password"] = "changed"
        user.password_hash = get_password_hash(user_data.password)
    if user_data.must_change_password is not None and user_data.must_change_password != user.must_change_password:
        changes["must_change_password"] = {"old": user.must_change_password, "new": user_data.must_change_password}
        user.must_change_password = user_data.must_change_password

    db.commit()
    db.refresh(user)

    # Log user modification if there were changes
    if changes:
        AuditService.log_user_modified(
            db, current_user, user.id, user.username, changes, request
        )

    return user


@router.patch("/local-users/{user_id}/role", response_model=LocalUserResponse)
async def update_user_role(
    user_id: int,
    role_data: UserRoleUpdate,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update a user's role (admin only)"""
    # Find the user
    user = db.query(User).filter(
        User.id == user_id,
        User.type.in_([UserType.admin, UserType.staff, UserType.support, UserType.local_user])
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Map role string to UserType
    role_map = {
        'admin': UserType.admin,
        'staff': UserType.staff,
        'support': UserType.support
    }

    new_role = role_map.get(role_data.role)
    if not new_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role"
        )

    # Store old role for audit log
    old_role = user.type.value

    # Update the role
    user.type = new_role
    db.commit()
    db.refresh(user)

    # Log the action
    audit_service = AuditService(db)
    await audit_service.log_action(
        actor_id=current_user.id,
        action="update_user_role",
        target_type="user",
        target_id=user.id,
        details={
            "user_id": user.id,
            "old_role": old_role,
            "new_role": new_role.value
        },
        ip_address=request.client.host if request else None
    )

    return user


@router.delete("/local-users/{user_id}")
async def delete_local_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_user_deletion_allowed),
    db: Session = Depends(get_db)
):
    """Delete a user (admin only)"""
    from ....models.session import Session as SessionModel
    from ....models.playback_analytics import PlaybackEvent

    user = db.query(User).filter(
        User.id == user_id,
        User.type.in_([UserType.staff, UserType.support, UserType.local_user])
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Store username before deletion
    username = user.username
    user_type = user.type.value if hasattr(user.type, 'value') else str(user.type)

    # Delete related records first to avoid foreign key constraints
    # Delete user permissions
    db.query(UserPermission).filter(UserPermission.user_id == user_id).delete()

    # Delete or update sessions
    db.query(SessionModel).filter(SessionModel.user_id == user_id).update({"user_id": None})

    # Delete or update playback events
    db.query(PlaybackEvent).filter(PlaybackEvent.user_id == user_id).update({"user_id": None})

    # Now delete the user
    db.delete(user)
    db.commit()

    # Log user deletion
    AuditService.log_user_deleted(
        db, current_user, username, user_type, request
    )

    return {"message": "User deleted successfully"}


# User Permission Endpoints

@router.get("/local-users/{user_id}/permissions", response_model=List[UserPermissionSchema])
async def get_user_permissions(
    user_id: int,
    current_user: User = Depends(get_current_admin_or_local_user),  # Allow local users to fetch their own
    db: Session = Depends(get_db)
):
    """Get permissions for a local user"""
    # Check authorization: users can fetch their own permissions, admins can fetch anyone's
    if current_user.id != user_id and current_user.type != UserType.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view these permissions"
        )

    permissions = db.query(UserPermission).filter(
        UserPermission.user_id == user_id
    ).all()

    return permissions


@router.post("/local-users/{user_id}/permissions", response_model=UserPermissionSchema)
async def grant_user_permission(
    user_id: int,
    permission_data: UserPermissionSchema,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Grant permissions to a local user for a server"""
    # Check if user exists and is a local user
    user = db.query(User).filter(
        User.id == user_id,
        User.type == UserType.local_user
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or not a local user"
        )

    # Check if server exists
    server = db.query(Server).filter(Server.id == permission_data.server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Check if permission already exists
    existing = db.query(UserPermission).filter(
        UserPermission.user_id == user_id,
        UserPermission.server_id == permission_data.server_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permission already exists for this user and server"
        )

    # Create new permission
    permission = UserPermission(
        user_id=user_id,
        server_id=permission_data.server_id,
        can_view_sessions=permission_data.can_view_sessions,
        can_view_users=permission_data.can_view_users,
        can_view_analytics=permission_data.can_view_analytics,
        can_terminate_sessions=permission_data.can_terminate_sessions,
        can_manage_server=permission_data.can_manage_server
    )

    db.add(permission)
    db.commit()
    db.refresh(permission)

    return permission


@router.patch("/local-users/{user_id}/permissions/{server_id}", response_model=UserPermissionSchema)
async def update_user_permission(
    user_id: int,
    server_id: int,
    permission_data: UserPermissionUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update user permissions for a server"""
    permission = db.query(UserPermission).filter(
        UserPermission.user_id == user_id,
        UserPermission.server_id == server_id
    ).first()

    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )

    # Update fields if provided
    if permission_data.can_view_sessions is not None:
        permission.can_view_sessions = permission_data.can_view_sessions
    if permission_data.can_view_users is not None:
        permission.can_view_users = permission_data.can_view_users
    if permission_data.can_view_analytics is not None:
        permission.can_view_analytics = permission_data.can_view_analytics
    if permission_data.can_terminate_sessions is not None:
        permission.can_terminate_sessions = permission_data.can_terminate_sessions
    if permission_data.can_manage_server is not None:
        permission.can_manage_server = permission_data.can_manage_server

    db.commit()
    db.refresh(permission)

    return permission


@router.delete("/local-users/{user_id}/permissions/{server_id}")
async def revoke_user_permission(
    user_id: int,
    server_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Revoke user permissions for a server"""
    permission = db.query(UserPermission).filter(
        UserPermission.user_id == user_id,
        UserPermission.server_id == server_id
    ).first()

    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )

    db.delete(permission)
    db.commit()

    return {"message": "Permission revoked successfully"}


# User Library Access Endpoints

@router.get("/servers/{server_id}/users/{user_id}/libraries")
async def get_user_library_access(
    server_id: int,
    user_id: str,  # Provider user ID
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get current library access for a user"""
    # Get server
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Check permissions
    if current_user.type != UserType.admin:
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()

        if not permission or not permission.can_manage_servers:
            raise HTTPException(status_code=403, detail="No permission to manage this server")

    # Initialize provider and get user's library access
    try:
        logger.info(f"Getting library access for user {user_id} on server {server.name} (type: {server.type})")

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
    library_ids: List[str],
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Set library access for a user"""
    # Get server
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Check permissions
    if current_user.type != UserType.admin:
        permission = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.server_id == server_id
        ).first()

        if not permission or not permission.can_manage_servers:
            raise HTTPException(status_code=403, detail="No permission to manage this server")

    # Get provider and set library access
    provider = ProviderFactory.create_provider(server, db)

    success = await provider.set_library_access(user_id, library_ids)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to set library access")

    # Log the action
    AuditService.log_custom(
        db, current_user, "set_library_access",
        details=f"Set library access for user {user_id} on server {server.name}",
        request=None
    )

    return {"success": True, "message": "Library access updated"}
