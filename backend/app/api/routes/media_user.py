from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_media_user
from ...models.user import User
from ...models.session import Session as MediaSession
from ...schemas.session import SessionResponse
from ...schemas.user import UserResponse

router = APIRouter()


@router.get("/profile", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_media_user)
):
    """Get current media user profile"""
    return UserResponse.from_orm(current_user)


@router.get("/sessions", response_model=List[SessionResponse])
async def get_my_sessions(
    current_user: User = Depends(get_current_media_user),
    db: Session = Depends(get_db)
):
    """Get current user's active sessions"""
    sessions = db.query(MediaSession).filter(
        MediaSession.user_id == current_user.id,
        MediaSession.ended_at.is_(None)
    ).all()

    return [SessionResponse.from_orm(session) for session in sessions]


@router.get("/history")
async def get_watch_history(
    current_user: User = Depends(get_current_media_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0
):
    """Get user's watch history"""
    sessions = db.query(MediaSession).filter(
        MediaSession.user_id == current_user.id,
        MediaSession.ended_at.is_not(None)
    ).order_by(MediaSession.ended_at.desc()).offset(offset).limit(limit).all()

    history = []
    for session in sessions:
        session_data = SessionResponse.from_orm(session)

        # Add media info if available
        if session.media:
            from ...schemas.media import MediaResponse
            session_data.media = MediaResponse.from_orm(session.media)

        # Add server info
        if session.server:
            session_data.server_name = session.server.name
            session_data.server_type = session.server.type.value

        history.append(session_data)

    return {
        "sessions": history,
        "total": len(history),
        "offset": offset,
        "limit": limit
    }


@router.get("/stats")
async def get_user_stats(
    current_user: User = Depends(get_current_media_user),
    db: Session = Depends(get_db)
):
    """Get user statistics"""
    from sqlalchemy import func, distinct
    from datetime import datetime, timedelta

    # Total watch time (in seconds)
    total_watch_time = db.query(
        func.sum(MediaSession.progress_seconds)
    ).filter(
        MediaSession.user_id == current_user.id,
        MediaSession.ended_at.is_not(None)
    ).scalar() or 0

    # Total sessions
    total_sessions = db.query(MediaSession).filter(
        MediaSession.user_id == current_user.id
    ).count()

    # Unique media watched
    unique_media = db.query(
        func.count(distinct(MediaSession.media_id))
    ).filter(
        MediaSession.user_id == current_user.id,
        MediaSession.media_id.is_not(None)
    ).scalar() or 0

    # Recent activity (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_sessions = db.query(MediaSession).filter(
        MediaSession.user_id == current_user.id,
        MediaSession.started_at >= week_ago
    ).count()

    # Most watched media types
    from ...models.media import Media
    media_types = db.query(
        Media.type,
        func.count(MediaSession.id).label("count")
    ).join(MediaSession).filter(
        MediaSession.user_id == current_user.id
    ).group_by(Media.type).all()

    return {
        "total_watch_time_seconds": total_watch_time,
        "total_watch_time_hours": round(total_watch_time / 3600, 1),
        "total_sessions": total_sessions,
        "unique_media_watched": unique_media,
        "recent_sessions_7_days": recent_sessions,
        "media_types": [{"type": mt[0], "count": mt[1]} for mt in media_types]
    }