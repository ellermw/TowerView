from sqlalchemy import Column, Integer, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from ..core.database import Base


class UserPermission(Base):
    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)

    # Permissions
    can_view_sessions = Column(Boolean, default=True, nullable=False)
    can_view_users = Column(Boolean, default=True, nullable=False)
    can_view_analytics = Column(Boolean, default=True, nullable=False)
    can_terminate_sessions = Column(Boolean, default=False, nullable=False)
    can_manage_server = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="permissions")
    server = relationship("Server", back_populates="user_permissions")

    # Unique constraint to prevent duplicate permissions
    __table_args__ = (
        UniqueConstraint('user_id', 'server_id', name='unique_user_server_permission'),
    )