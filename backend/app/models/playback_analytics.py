from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..core.database import Base


class PlaybackEvent(Base):
    """Track individual playback events for analytics"""
    __tablename__ = "playback_events"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Provider-specific IDs
    provider_session_id = Column(String, nullable=True)
    provider_user_id = Column(String, nullable=True)
    provider_media_id = Column(String, nullable=True)

    # Media information
    media_title = Column(String, nullable=True)
    media_type = Column(String, nullable=True)  # movie, episode, track, etc.
    grandparent_title = Column(String, nullable=True)  # Show name
    parent_title = Column(String, nullable=True)  # Season
    season_number = Column(Integer, nullable=True)  # Season number for TV episodes
    episode_number = Column(Integer, nullable=True)  # Episode number for TV episodes
    library_section = Column(String, nullable=True)
    year = Column(String, nullable=True)

    # Playback details
    device = Column(String, nullable=True)
    platform = Column(String, nullable=True)
    product = Column(String, nullable=True)
    username = Column(String, nullable=True)

    # Session metrics
    duration_ms = Column(Integer, default=0)
    progress_ms = Column(Integer, default=0)
    progress_percent = Column(Float, default=0.0)

    # Streaming details
    video_decision = Column(String, nullable=True)  # directplay, copy, transcode
    original_resolution = Column(String, nullable=True)
    original_bitrate = Column(String, nullable=True)
    video_codec = Column(String, nullable=True)
    audio_codec = Column(String, nullable=True)
    container = Column(String, nullable=True)

    # Quality flags
    is_4k = Column(Boolean, default=False)
    is_hdr = Column(Boolean, default=False)
    is_dolby_vision = Column(Boolean, default=False)

    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Analytics flags
    is_complete = Column(Boolean, default=False)  # 90%+ watched or marked as watched
    is_watched = Column(Boolean, default=False)  # Marked as watched by server

    # Relationships
    server = relationship("Server", back_populates="playback_events")
    user = relationship("User", back_populates="playback_events")


class DailyAnalytics(Base):
    """Aggregated daily analytics for faster queries"""
    __tablename__ = "daily_analytics"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)

    # User analytics
    active_users = Column(Integer, default=0)
    total_sessions = Column(Integer, default=0)
    total_watch_time_minutes = Column(Integer, default=0)

    # Media analytics
    movies_watched = Column(Integer, default=0)
    episodes_watched = Column(Integer, default=0)
    music_tracks_played = Column(Integer, default=0)

    # Device analytics
    device_stats = Column(Text, nullable=True)  # JSON of device usage
    platform_stats = Column(Text, nullable=True)  # JSON of platform usage

    # Quality analytics
    direct_play_count = Column(Integer, default=0)
    direct_stream_count = Column(Integer, default=0)
    transcode_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    server = relationship("Server")