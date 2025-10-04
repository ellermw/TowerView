"""
Analytics and bandwidth endpoints
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from ....core.database import get_db
from ....core.security import get_current_admin_or_local_user
from ....models.user import User, UserType
from ....schemas.analytics import DashboardAnalyticsResponse, AnalyticsFilters
from pydantic import BaseModel
from typing import Optional

# Define request models here since they're not in schemas
class AnalyticsRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    server_ids: Optional[List[int]] = None
    user_ids: Optional[List[str]] = None

class BandwidthHistory(BaseModel):
    history: List[Dict[str, Any]]

# Use DashboardAnalyticsResponse as AnalyticsResponse
AnalyticsResponse = DashboardAnalyticsResponse
from ....services.analytics_service import AnalyticsService
from ....models.user_permission import UserPermission

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/bandwidth")
async def get_bandwidth_history(
    hours: int = 24,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
) -> BandwidthHistory:
    """Get bandwidth history for the last N hours"""
    # TODO: Implement bandwidth cache properly
    # For now, return empty history
    history = []

    # Filter based on user permissions if not admin
    if current_user.type == UserType.local_user:
        # Get servers the user has permission to view
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.can_view_servers == True
        ).all()

        allowed_server_ids = [p.server_id for p in permissions]

        # Filter history to only include allowed servers
        filtered_history = []
        for entry in history:
            filtered_entry = {
                "timestamp": entry["timestamp"],
                "servers": {}
            }
            for server_id, data in entry.get("servers", {}).items():
                if int(server_id) in allowed_server_ids:
                    filtered_entry["servers"][server_id] = data

            if filtered_entry["servers"]:
                filtered_history.append(filtered_entry)

        history = filtered_history

    return {"history": history}


@router.post("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    filters: AnalyticsRequest,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
):
    """Get analytics data with optional filters"""
    analytics_service = AnalyticsService(db)

    # Convert AnalyticsRequest to AnalyticsFilters
    analytics_filters = AnalyticsFilters(
        server_id=filters.server_ids[0] if filters.server_ids and len(filters.server_ids) == 1 else None,
        start_date=datetime.fromisoformat(filters.start_date) if filters.start_date else None,
        end_date=datetime.fromisoformat(filters.end_date) if filters.end_date else None,
        days_back=7  # Default value
    )

    # Determine allowed servers based on user type
    allowed_server_ids = None
    if current_user.type == UserType.local_user:
        # Get servers the user has permission to view
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.can_view_servers == True
        ).all()

        if not permissions:
            # No permissions, return empty analytics
            return {
                "filters": analytics_filters,
                "top_users": [],
                "top_movies": [],
                "top_tv_shows": [],
                "top_libraries": [],
                "top_devices": [],
                "total_sessions": 0,
                "total_users": 0,
                "total_watch_time_hours": 0,
                "peak_concurrent_sessions": 0,
                "unique_users": 0,
                "daily_sessions": [],
                "hourly_distribution": [],
                "quality_distribution": [],
                "transcode_vs_direct": {"direct_play": 0, "transcode": 0},
                "completion_rate": 0,
                "transcode_rate": 0
            }

        allowed_server_ids = [p.server_id for p in permissions]

    try:
        # Pass allowed_server_ids for local users
        analytics_data = analytics_service.get_dashboard_analytics(
            analytics_filters,
            allowed_server_ids=allowed_server_ids
        )
        return analytics_data
    except Exception as e:
        # If analytics fails, return empty data to prevent dashboard crash
        logger.error(f"Analytics query failed: {e}")
        return {
            "filters": analytics_filters,
            "top_users": [],
            "top_movies": [],
            "top_tv_shows": [],
            "top_libraries": [],
            "top_devices": [],
            "total_sessions": 0,
            "total_users": 0,
            "total_watch_time_hours": 0,
            "peak_concurrent_sessions": 0,
            "unique_users": 0,
            "daily_sessions": [],
            "hourly_distribution": [],
            "quality_distribution": [],
            "transcode_vs_direct": {"direct_play": 0, "transcode": 0},
            "completion_rate": 0,
            "transcode_rate": 0
        }


@router.get("/analytics/summary")
async def get_analytics_summary(
    days: int = 7,
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get a summary of analytics for the last N days"""
    analytics_service = AnalyticsService(db)

    # Create filters for the time period - use AnalyticsFilters instead of AnalyticsRequest
    filters = AnalyticsFilters(
        start_date=datetime.utcnow() - timedelta(days=days),
        end_date=datetime.utcnow(),
        days_back=days
    )

    # Determine allowed servers
    allowed_server_ids = None
    if current_user.type == UserType.local_user:
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.can_view_servers == True
        ).all()

        if not permissions:
            return {
                "period_days": days,
                "total_sessions": 0,
                "unique_users": 0,
                "total_watch_time_hours": 0,
                "most_active_day": None,
                "peak_hour": None
            }

        allowed_server_ids = [p.server_id for p in permissions]

    # Get analytics data
    data = analytics_service.get_dashboard_analytics(filters, allowed_server_ids)

    # Find most active day
    most_active_day = None
    # Note: daily_sessions and hourly_distribution aren't in DashboardAnalyticsResponse currently
    # We would need to add these fields to the response model
    # For now, we'll return None for these fields

    # Find peak hour
    peak_hour = None

    # Combine top movies and TV shows for top content
    top_content = []
    for movie in data.top_movies[:3]:
        top_content.append({"title": movie.title, "count": movie.total_plays})
    for show in data.top_tv_shows[:3]:
        top_content.append({"title": show.title, "count": show.total_plays})

    return {
        "period_days": days,
        "total_sessions": data.total_sessions,
        "unique_users": data.total_users,
        "total_watch_time_hours": data.total_watch_time_hours,
        "most_active_day": most_active_day,
        "peak_hour": peak_hour,
        "top_content": top_content
    }


@router.get("/analytics/trends")
async def get_analytics_trends(
    current_user: User = Depends(get_current_admin_or_local_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get trends comparing this week to last week"""
    analytics_service = AnalyticsService(db)

    # This week
    this_week_start = datetime.utcnow() - timedelta(days=7)
    this_week_filters = AnalyticsFilters(
        start_date=this_week_start,
        end_date=datetime.utcnow(),
        days_back=7
    )

    # Last week
    last_week_start = datetime.utcnow() - timedelta(days=14)
    last_week_end = datetime.utcnow() - timedelta(days=7)
    last_week_filters = AnalyticsFilters(
        start_date=last_week_start,
        end_date=last_week_end,
        days_back=7
    )

    # Get allowed servers for local users
    allowed_server_ids = None
    if current_user.type == UserType.local_user:
        permissions = db.query(UserPermission).filter(
            UserPermission.user_id == current_user.id,
            UserPermission.can_view_servers == True
        ).all()

        if not permissions:
            return {
                "sessions_change": 0,
                "users_change": 0,
                "watch_time_change": 0,
                "trending_up": [],
                "trending_down": []
            }

        allowed_server_ids = [p.server_id for p in permissions]

    # Get data for both periods
    this_week_data = analytics_service.get_dashboard_analytics(this_week_filters, allowed_server_ids)
    last_week_data = analytics_service.get_dashboard_analytics(last_week_filters, allowed_server_ids)

    # Calculate changes
    def calculate_change(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 1)

    sessions_change = calculate_change(
        this_week_data.total_sessions,
        last_week_data.total_sessions
    )

    users_change = calculate_change(
        this_week_data.total_users,
        last_week_data.total_users
    )

    watch_time_change = calculate_change(
        this_week_data.total_watch_time_hours,
        last_week_data.total_watch_time_hours
    )

    # Find trending content
    this_week_content = {}
    last_week_content = {}

    for item in this_week_data.top_movies + this_week_data.top_tv_shows:
        this_week_content[item.title] = item.total_plays

    for item in last_week_data.top_movies + last_week_data.top_tv_shows:
        last_week_content[item.title] = item.total_plays

    trending_up = []
    trending_down = []

    for title, count in this_week_content.items():
        last_count = last_week_content.get(title, 0)
        change = count - last_count
        if change > 0:
            trending_up.append({"title": title, "change": change})
        elif change < 0:
            trending_down.append({"title": title, "change": abs(change)})

    # Sort by change
    trending_up.sort(key=lambda x: x["change"], reverse=True)
    trending_down.sort(key=lambda x: x["change"], reverse=True)

    return {
        "sessions_change": sessions_change,
        "users_change": users_change,
        "watch_time_change": watch_time_change,
        "trending_up": trending_up[:5],
        "trending_down": trending_down[:5]
    }