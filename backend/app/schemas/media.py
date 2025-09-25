from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class MediaBase(BaseModel):
    provider_media_id: str
    title: str
    type: str
    runtime: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class MediaResponse(MediaBase):
    id: int
    server_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True