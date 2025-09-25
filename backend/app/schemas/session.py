from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class SessionBase(BaseModel):
    provider_session_id: str
    state: str
    progress_seconds: int = 0
    metadata: Optional[Dict[str, Any]] = None


class SessionResponse(SessionBase):
    id: int
    server_id: int
    user_id: Optional[int] = None
    media_id: Optional[int] = None
    started_at: datetime
    updated_at: datetime
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LiveSessionResponse(BaseModel):
    """Schema for live sessions from providers (not stored in database)"""
    session_id: str
    media_id: Optional[str] = None
    media_type: Optional[str] = None
    state: str
    progress_ms: int = 0
    duration_ms: int = 0
    progress_seconds: int = 0
    duration_seconds: int = 0
    progress_percent: float = 0.0

    # Server info (added by API)
    server_name: Optional[str] = None
    server_id: Optional[int] = None
    server_type: Optional[str] = None

    # Media details
    title: Optional[str] = None
    full_title: Optional[str] = None
    grandparent_title: Optional[str] = None  # Show name
    parent_title: Optional[str] = None  # Season
    year: Optional[str] = None
    summary: Optional[str] = None
    content_rating: Optional[str] = None
    library_section: Optional[str] = None

    # User info
    user_id: Optional[str] = None
    username: Optional[str] = None
    user_thumb: Optional[str] = None

    # Player info
    device: Optional[str] = None
    platform: Optional[str] = None
    product: Optional[str] = None
    version: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None

    # Streaming details
    video_decision: Optional[str] = None
    original_resolution: Optional[str] = None
    original_bitrate: Optional[str] = None
    stream_bitrate: Optional[str] = None
    session_bandwidth: Optional[str] = None
    session_location: Optional[str] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    audio_channels: Optional[str] = None
    container: Optional[str] = None
    video_profile: Optional[str] = None
    quality_profile: Optional[str] = None
    is_4k: bool = False
    is_hdr: bool = False
    is_dolby_vision: bool = False