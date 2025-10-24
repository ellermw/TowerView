from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..core.database import Base


class UserType(enum.Enum):
    admin = "admin"  # Full access to all servers and all permissions
    staff = "staff"  # Can manage specific servers, create support users (formerly local_user)
    support = "support"  # Limited to view sessions, users, analytics only
    local_user = "local_user"  # Deprecated, kept for migration compatibility
    media_user = "media_user"  # Users from media servers


class ProviderType(enum.Enum):
    plex = "plex"
    emby = "emby"
    jellyfin = "jellyfin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(UserType), nullable=False)
    provider = Column(Enum(ProviderType), nullable=True)  # null for admin users
    provider_user_id = Column(String, nullable=True)  # null for admin users
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=True)  # null for admin users
    username = Column(String, nullable=False)
    email = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)  # only for admin users
    must_change_password = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    server = relationship("Server", foreign_keys=[server_id], back_populates="users")
    sessions = relationship("Session", back_populates="user")
    audit_logs_actor = relationship("AuditLog", foreign_keys="AuditLog.actor_id", back_populates="actor")
    playback_events = relationship("PlaybackEvent", back_populates="user")
    permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan")
    settings_updates = relationship("SystemSettings", back_populates="updated_by")
    netdata_integrations = relationship("NetdataIntegration", back_populates="created_by")
    portainer_integrations = relationship("PortainerIntegration", back_populates="created_by")
    proxmox_integrations = relationship("ProxmoxIntegration", back_populates="created_by")