from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import Request
from ..models.audit_log import AuditLog
from ..models.user import User, UserType
import json
import logging

logger = logging.getLogger(__name__)


class AuditService:
    @staticmethod
    def log_action(
        db: Session,
        actor: Optional[User],
        action: str,
        target: Optional[str] = None,
        target_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ):
        """Log an action to the audit log"""
        try:
            # Determine actor information
            if actor:
                actor_id = actor.id
                actor_username = actor.username
                actor_type = actor.type.value if hasattr(actor.type, 'value') else str(actor.type)
            else:
                actor_id = None
                actor_username = "System"
                actor_type = "system"

            # Extract request information if provided
            ip_address = None
            user_agent = None
            if request:
                ip_address = request.client.host if request.client else None
                user_agent = request.headers.get("User-Agent")

            # Create audit log entry
            audit_log = AuditLog(
                actor_id=actor_id,
                actor_username=actor_username,
                actor_type=actor_type,
                action=action,
                target=target,
                target_name=target_name,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent
            )

            db.add(audit_log)
            db.commit()

        except Exception as e:
            # Don't let audit logging failures break the main operation
            logger.error(f"Failed to create audit log: {e}")
            db.rollback()

    @staticmethod
    def log_login(db: Session, user: User, request: Request):
        """Log a user login"""
        AuditService.log_action(
            db=db,
            actor=user,
            action="LOGIN",
            details={"user_type": user.type.value if hasattr(user.type, 'value') else str(user.type)},
            request=request
        )

    @staticmethod
    def log_logout(db: Session, user: User, request: Request):
        """Log a user logout"""
        AuditService.log_action(
            db=db,
            actor=user,
            action="LOGOUT",
            request=request
        )

    @staticmethod
    def log_session_terminated(db: Session, actor: User, session_id: str, username: str, server_name: str, request: Request):
        """Log a session termination"""
        AuditService.log_action(
            db=db,
            actor=actor,
            action="SESSION_TERMINATED",
            target=f"session:{session_id}",
            target_name=f"{username} on {server_name}",
            details={"username": username, "server": server_name},
            request=request
        )

    @staticmethod
    def log_container_action(db: Session, actor: User, action: str, server_id: int, server_name: str, container_name: str, request: Request):
        """Log a container action (start/stop/restart/update)"""
        action_map = {
            "start": "CONTAINER_START",
            "stop": "CONTAINER_STOP",
            "restart": "CONTAINER_RESTART",
            "update": "CONTAINER_UPDATE"
        }

        AuditService.log_action(
            db=db,
            actor=actor,
            action=action_map.get(action, f"CONTAINER_{action.upper()}"),
            target=f"server:{server_id}",
            target_name=server_name,
            details={"container": container_name, "action": action},
            request=request
        )

    @staticmethod
    def log_user_modified(db: Session, actor: User, target_user_id: int, target_username: str, changes: Dict[str, Any], request: Request):
        """Log a user modification"""
        AuditService.log_action(
            db=db,
            actor=actor,
            action="USER_MODIFIED",
            target=f"user:{target_user_id}",
            target_name=target_username,
            details={"changes": changes},
            request=request
        )

    @staticmethod
    def log_user_created(db: Session, actor: User, target_user_id: int, target_username: str, user_type: str, request: Request):
        """Log a user creation"""
        AuditService.log_action(
            db=db,
            actor=actor,
            action="USER_CREATED",
            target=f"user:{target_user_id}",
            target_name=target_username,
            details={"user_type": user_type},
            request=request
        )

    @staticmethod
    def log_user_deleted(db: Session, actor: User, target_username: str, user_type: str, request: Request):
        """Log a user deletion"""
        AuditService.log_action(
            db=db,
            actor=actor,
            action="USER_DELETED",
            target=None,
            target_name=target_username,
            details={"user_type": user_type},
            request=request
        )

    @staticmethod
    def log_server_action(db: Session, actor: User, action: str, server_id: Optional[int], server_name: str, server_type: str, request: Request):
        """Log a server action (add/edit/delete)"""
        action_map = {
            "add": "SERVER_ADDED",
            "edit": "SERVER_MODIFIED",
            "delete": "SERVER_DELETED"
        }

        AuditService.log_action(
            db=db,
            actor=actor,
            action=action_map.get(action, f"SERVER_{action.upper()}"),
            target=f"server:{server_id}" if server_id else None,
            target_name=server_name,
            details={"server_type": server_type},
            request=request
        )

    @staticmethod
    def log_settings_changed(db: Session, actor: User, setting_type: str, changes: Dict[str, Any], request: Request):
        """Log a settings change"""
        AuditService.log_action(
            db=db,
            actor=actor,
            action="SETTINGS_CHANGED",
            target=f"settings:{setting_type}",
            target_name=setting_type,
            details={"changes": changes},
            request=request
        )