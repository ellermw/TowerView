"""
Simplified model imports for worker to avoid circular dependencies
"""
import sys
import os

# Add backend to path for imports
sys.path.insert(0, '/backend')
sys.path.insert(0, '/backend/app')

# Import SQLAlchemy base and essentials
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean, JSON, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from datetime import datetime

Base = declarative_base()

class ServerType(enum.Enum):
    plex = "plex"
    emby = "emby"
    jellyfin = "jellyfin"

class UserType(enum.Enum):
    admin = "admin"
    media_user = "media_user"

# Define models directly to avoid import issues
class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    type = Column(Enum(ServerType), nullable=False)
    base_url = Column(String, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    group_id = Column(Integer, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    credentials = relationship("Credential", back_populates="server", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="server", cascade="all, delete-orphan")
    users = relationship("User", back_populates="server", cascade="all, delete-orphan")
    media = relationship("Media", back_populates="server", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(UserType), nullable=False, default=UserType.media_user)
    provider = Column(Enum(ServerType), nullable=True)
    provider_user_id = Column(String, nullable=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=True)
    username = Column(String, nullable=False, index=True)
    email = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    must_change_password = Column(Boolean, default=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())

    server = relationship("Server", back_populates="users")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    media_id = Column(Integer, ForeignKey("media.id", ondelete="SET NULL"), nullable=True)
    provider_session_id = Column(String, nullable=False)
    state = Column(String, nullable=False, default='unknown')
    progress_seconds = Column(Integer, default=0)
    session_metadata = Column(JSON, nullable=True)
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    ended_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, onupdate=func.now())

    server = relationship("Server", back_populates="sessions")
    user = relationship("User", back_populates="sessions")
    media = relationship("Media", back_populates="sessions")

class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    provider_media_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    type = Column(String, nullable=False, default='unknown')
    runtime = Column(Integer, nullable=True)
    media_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())

    server = relationship("Server", back_populates="media")
    sessions = relationship("Session", back_populates="media")

from sqlalchemy import LargeBinary

class Credential(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    encrypted_payload = Column(LargeBinary, nullable=False)  # Encrypted JSON with credentials
    auth_type = Column(String, nullable=False)  # "token", "password", "api_key"
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())

    server = relationship("Server", back_populates="credentials")