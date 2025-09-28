from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..core.database import Base


class ServerType(enum.Enum):
    plex = "plex"
    emby = "emby"
    jellyfin = "jellyfin"


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(Enum(ServerType), nullable=False)
    base_url = Column(String, nullable=False)
    group_id = Column(Integer, nullable=True)  # Keep column for backward compatibility but remove FK
    enabled = Column(Boolean, default=True)
    visible_to_media_users = Column(Boolean, default=True)  # Control visibility for media users
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    server_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    credentials = relationship("Credential", back_populates="server", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="server")
    users = relationship("User", foreign_keys="User.server_id", back_populates="server")
    playback_events = relationship("PlaybackEvent", back_populates="server", cascade="all, delete-orphan")
    user_permissions = relationship("UserPermission", back_populates="server", cascade="all, delete-orphan")