from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    provider_media_id = Column(String, nullable=False)  # ID from the media server
    title = Column(String, nullable=False)
    type = Column(String, nullable=False)  # movie, episode, track, etc.
    runtime = Column(Integer, nullable=True)  # in seconds
    media_metadata = Column(JSON, nullable=True)  # Additional metadata from provider
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    server = relationship("Server", back_populates="media")
    sessions = relationship("Session", back_populates="media")