from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class AnalyticsFilters(BaseModel):
    server_id: Optional[int] = None  # None means all servers
    days_back: int = 7
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class TopUserResponse(BaseModel):
    username: str
    provider_user_id: Optional[str] = None
    server_name: Optional[str] = None
    total_plays: int
    total_watch_time_minutes: int
    completion_rate: float  # percentage of content watched to completion


class TopMediaResponse(BaseModel):
    title: str
    media_type: str  # movie, episode, track
    provider_media_id: Optional[str] = None
    server_name: Optional[str] = None
    total_plays: int
    unique_users: int
    total_watch_time_minutes: int
    # For TV shows
    grandparent_title: Optional[str] = None  # Show name
    parent_title: Optional[str] = None  # Season
    year: Optional[str] = None


class TopLibraryResponse(BaseModel):
    library_name: str
    server_name: Optional[str] = None
    total_plays: int
    unique_users: int
    total_watch_time_minutes: int
    media_types: List[str]  # movies, episodes, tracks, etc.


class TopDeviceResponse(BaseModel):
    device_name: str
    platform: Optional[str] = None
    product: Optional[str] = None
    total_sessions: int
    unique_users: int
    total_watch_time_minutes: int
    transcode_percentage: float  # percentage of sessions that required transcoding


class DashboardAnalyticsResponse(BaseModel):
    filters: AnalyticsFilters
    top_users: List[TopUserResponse]
    top_movies: List[TopMediaResponse]
    top_tv_shows: List[TopMediaResponse]
    top_libraries: List[TopLibraryResponse]
    top_devices: List[TopDeviceResponse]

    # Summary stats
    total_sessions: int
    total_users: int
    total_watch_time_hours: int
    completion_rate: float  # overall completion rate
    transcode_rate: float  # overall transcode rate


class PlaybackEventCreate(BaseModel):
    provider_session_id: str
    provider_user_id: Optional[str] = None
    provider_media_id: Optional[str] = None

    # Media information
    media_title: Optional[str] = None
    media_type: Optional[str] = None
    grandparent_title: Optional[str] = None
    parent_title: Optional[str] = None
    library_section: Optional[str] = None
    year: Optional[str] = None

    # Playback details
    device: Optional[str] = None
    platform: Optional[str] = None
    product: Optional[str] = None
    username: Optional[str] = None

    # Session metrics
    duration_ms: int = 0
    progress_ms: int = 0
    progress_percent: float = 0.0

    # Streaming details
    video_decision: Optional[str] = None
    original_resolution: Optional[str] = None
    original_bitrate: Optional[str] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    container: Optional[str] = None

    # Quality flags
    is_4k: bool = False
    is_hdr: bool = False
    is_dolby_vision: bool = False

    # Analytics flags
    is_complete: bool = False
    is_watched: bool = False