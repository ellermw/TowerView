from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from ..models.server import ServerType


class ServerBase(BaseModel):
    name: str
    type: ServerType
    base_url: str
    group_id: Optional[int] = None
    enabled: bool = True


class ServerCreate(ServerBase):
    credentials: Dict[str, Any]  # Will be encrypted before storage


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[ServerType] = None
    base_url: Optional[str] = None
    group_id: Optional[int] = None
    enabled: Optional[bool] = None
    credentials: Optional[Dict[str, Any]] = None


class ServerResponse(ServerBase):
    id: int
    owner_id: int
    last_seen_at: Optional[datetime] = None
    server_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True