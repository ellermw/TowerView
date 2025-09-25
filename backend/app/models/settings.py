"""
Settings model for system configurations and integrations
"""
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from ..core.database import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=True)
    category = Column(String(100), nullable=False, default="general")
    description = Column(String(500))
    is_sensitive = Column(Boolean, default=False)  # For passwords/tokens
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    updated_by = relationship("User", back_populates="settings_updates")


class NetdataIntegration(Base):
    """Store Netdata Cloud integration settings"""
    __tablename__ = "netdata_integrations"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    enabled = Column(Boolean, default=True)

    # Netdata Cloud credentials
    api_token = Column(String(500), nullable=True)  # Encrypted in production
    space_id = Column(String(255), nullable=True)

    # Selected nodes mapping to servers
    node_mappings = Column(JSON, default=dict)  # {server_id: node_id}

    # Cached node list
    cached_nodes = Column(JSON, default=list)
    nodes_updated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    created_by = relationship("User", back_populates="netdata_integrations")


class PortainerIntegration(Base):
    """Store Portainer integration settings"""
    __tablename__ = "portainer_integrations"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    enabled = Column(Boolean, default=True)

    # Portainer connection settings
    url = Column(String(500), nullable=True)
    api_token = Column(String(500), nullable=True)  # JWT or API key
    username = Column(String(255), nullable=True)  # For initial auth
    password = Column(String(500), nullable=True)  # Encrypted in production
    endpoint_id = Column(Integer, default=1)  # Docker endpoint ID

    # Container mappings to servers
    container_mappings = Column(JSON, default=dict)  # {server_id: container_id}

    # Cached container list
    cached_containers = Column(JSON, default=list)
    containers_updated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    created_by = relationship("User", back_populates="portainer_integrations")