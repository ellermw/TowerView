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
    progress: Optional[int] = None  # Legacy field

    # Server info (added by API)
    server_name: Optional[str] = None
    server_id: Optional[int] = None
    server_type: Optional[str] = None

    # User info
    user_id: Optional[str] = None
    username: Optional[str] = None

    # Media details
    media_title: Optional[str] = None
    title: Optional[str] = None
    full_title: Optional[str] = None
    year: Optional[str] = None
    summary: Optional[str] = None
    runtime: Optional[int] = None
    library_section: Optional[str] = None
    grandparent_title: Optional[str] = None
    parent_title: Optional[str] = None

    # Device/Player info
    device: Optional[str] = None
    platform: Optional[str] = None
    product: Optional[str] = None

    # Streaming details
    video_decision: Optional[str] = None
    original_resolution: Optional[str] = None
    original_bitrate: Optional[str] = None
    stream_bitrate: Optional[str] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    container: Optional[str] = None
    session_bandwidth: Optional[str] = None
    quality_profile: Optional[str] = None

    # Video quality and HDR fields
    is_4k: Optional[bool] = None
    is_hdr: Optional[bool] = None
    is_dolby_vision: Optional[bool] = None
    video_profile: Optional[str] = None

    # Hardware transcoding fields (Plex)
    transcode_hw_requested: Optional[bool] = None
    transcode_hw_full_pipeline: Optional[bool] = None
    transcode_hw_decode: Optional[bool] = None
    transcode_hw_encode: Optional[bool] = None
    transcode_hw_decode_title: Optional[str] = None
    transcode_hw_encode_title: Optional[str] = None
    transcode_speed: Optional[float] = None
    transcode_throttled: Optional[bool] = None