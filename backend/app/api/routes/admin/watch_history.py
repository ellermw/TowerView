"""
Watch history endpoints for media users
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from datetime import datetime, timedelta
import math

from ....core.database import get_db
from ....core.security import get_current_admin_or_local_user
from ....models.user import User
from ....models.playback_analytics import PlaybackEvent
from ....models.server import Server
from ....schemas.analytics import WatchHistoryResponse, WatchHistoryItemResponse

router = APIRouter()


@router.get("/users/{provider_user_id}/watch-history", response_model=WatchHistoryResponse)
async def get_user_watch_history(
    provider_user_id: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for title, device, etc."),
    server_id: Optional[int] = Query(None, description="Filter by server"),
    days_back: int = Query(365, ge=1, le=365, description="Number of days to look back"),
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """
    Get watch history for a specific media user.

    Displays playback events up to 365 days ago with pagination, search, and filtering.
    Shows title, season/episode info, resolution, HDR, bitrate, play state, completion %, and device.
    """
    # Calculate date cutoff
    cutoff_date = datetime.utcnow() - timedelta(days=days_back)

    # Build base query
    query = db.query(
        PlaybackEvent,
        Server.name.label('server_name')
    ).join(
        Server, PlaybackEvent.server_id == Server.id
    ).filter(
        and_(
            PlaybackEvent.provider_user_id == provider_user_id,
            PlaybackEvent.started_at >= cutoff_date
        )
    )

    # Apply server filter if provided
    if server_id:
        query = query.filter(PlaybackEvent.server_id == server_id)

    # Apply search filter if provided
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                PlaybackEvent.media_title.ilike(search_term),
                PlaybackEvent.grandparent_title.ilike(search_term),
                PlaybackEvent.parent_title.ilike(search_term),
                PlaybackEvent.device.ilike(search_term),
                PlaybackEvent.platform.ilike(search_term),
                PlaybackEvent.original_resolution.ilike(search_term),
                PlaybackEvent.video_decision.ilike(search_term)
            )
        )

    # Order by most recent first
    query = query.order_by(desc(PlaybackEvent.started_at))

    # Get total count before pagination
    total = query.count()

    # Calculate pagination
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    # Apply pagination
    results = query.limit(page_size).offset(offset).all()

    # Transform results to response schema
    items = []
    for playback_event, server_name in results:
        items.append(WatchHistoryItemResponse(
            id=playback_event.id,
            server_name=server_name,
            media_title=playback_event.media_title or "Unknown",
            media_type=playback_event.media_type or "unknown",
            grandparent_title=playback_event.grandparent_title,
            parent_title=playback_event.parent_title,
            season_number=playback_event.season_number,
            episode_number=playback_event.episode_number,
            year=playback_event.year,
            device=playback_event.device,
            platform=playback_event.platform,
            product=playback_event.product,
            video_decision=playback_event.video_decision,
            original_resolution=playback_event.original_resolution,
            original_bitrate=playback_event.original_bitrate,
            video_codec=playback_event.video_codec,
            is_4k=playback_event.is_4k or False,
            is_hdr=playback_event.is_hdr or False,
            is_dolby_vision=playback_event.is_dolby_vision or False,
            progress_percent=playback_event.progress_percent or 0.0,
            duration_ms=playback_event.duration_ms or 0,
            progress_ms=playback_event.progress_ms or 0,
            started_at=playback_event.started_at,
            ended_at=playback_event.ended_at
        ))

    return WatchHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )
