from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    provider_session_id = Column(String, nullable=False)  # Session ID from the media server
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Can be null if user not in our system
    media_id = Column(Integer, ForeignKey("media.id"), nullable=True)
    state = Column(String, nullable=False)  # playing, paused, stopped, buffering
    progress_seconds = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    session_metadata = Column(JSON, nullable=True)  # Player info, device, etc.

    # Relationships
    server = relationship("Server", back_populates="sessions")
    user = relationship("User", back_populates="sessions")
    media = relationship("Media", back_populates="sessions")