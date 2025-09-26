from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_username = Column(String, nullable=False)  # Store username in case user is deleted
    actor_type = Column(String, nullable=False)  # 'admin', 'local_user', 'system'
    action = Column(String, nullable=False)  # e.g., "LOGIN", "LOGOUT", "SESSION_TERMINATED", "USER_MODIFIED", "SERVER_ADDED", "CONTAINER_START", etc.
    target = Column(String, nullable=True)  # e.g., "session:123", "user:456", "server:789"
    target_name = Column(String, nullable=True)  # Human-readable name of the target
    details = Column(JSON, nullable=True)  # Additional context
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    actor = relationship("User", foreign_keys=[actor_id], back_populates="audit_logs_actor")