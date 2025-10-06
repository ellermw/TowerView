from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, text, case
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from ..models.playback_analytics import PlaybackEvent, DailyAnalytics
from ..models.server import Server
from ..schemas.analytics import (
    AnalyticsFilters, TopUserResponse, TopMediaResponse,
    TopLibraryResponse, TopDeviceResponse, DashboardAnalyticsResponse,
    PlaybackEventCreate
)


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def create_playback_event(self, server_id: int, event_data: PlaybackEventCreate) -> PlaybackEvent:
        """Create a new playback event for analytics tracking"""
        event = PlaybackEvent(
            server_id=server_id,
            **event_data.dict()
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def update_playback_event(self, event_id: int, **updates) -> Optional[PlaybackEvent]:
        """Update an existing playback event"""
        event = self.db.query(PlaybackEvent).filter(PlaybackEvent.id == event_id).first()
        if event:
            for key, value in updates.items():
                if hasattr(event, key):
                    setattr(event, key, value)
            self.db.commit()
            self.db.refresh(event)
        return event

    def get_date_filter(self, filters: AnalyticsFilters):
        """Generate date filter conditions"""
        if filters.start_date and filters.end_date:
            return and_(
                PlaybackEvent.started_at >= filters.start_date,
                PlaybackEvent.started_at <= filters.end_date
            )
        else:
            # Use days_back
            cutoff_date = datetime.utcnow() - timedelta(days=filters.days_back)
            return PlaybackEvent.started_at >= cutoff_date

    def get_server_filter(self, filters: AnalyticsFilters, allowed_server_ids: Optional[List[int]] = None):
        """Generate server filter conditions"""
        if filters.server_id:
            return PlaybackEvent.server_id == filters.server_id
        elif allowed_server_ids is not None:
            # Filter by allowed servers for local users
            if allowed_server_ids:
                return PlaybackEvent.server_id.in_(allowed_server_ids)
            else:
                # User has no permissions, return false to match nothing
                return False
        return True

    def get_top_users(self, filters: AnalyticsFilters, limit: int = 5, allowed_server_ids: Optional[List[int]] = None) -> List[TopUserResponse]:
        """Get most active users based on completed plays"""
        query = self.db.query(
            PlaybackEvent.username,
            PlaybackEvent.provider_user_id,
            Server.name.label('server_name'),
            func.count(PlaybackEvent.id).label('total_plays'),
            func.sum(
                case(
                    (PlaybackEvent.progress_ms > 0, PlaybackEvent.progress_ms),
                    else_=0
                ) / 60000  # Convert to minutes
            ).label('total_watch_time_minutes'),
            func.avg(
                case(
                    (PlaybackEvent.progress_percent >= 10, PlaybackEvent.progress_percent),
                    else_=None
                )
            ).label('avg_completion')
        ).join(Server, PlaybackEvent.server_id == Server.id)\
         .filter(and_(
             self.get_date_filter(filters),
             self.get_server_filter(filters, allowed_server_ids),
             PlaybackEvent.username.isnot(None),
             PlaybackEvent.is_complete == True  # Only count completed plays
         ))\
         .group_by(PlaybackEvent.username, PlaybackEvent.provider_user_id, Server.name)\
         .order_by(desc('total_plays'))\
         .limit(limit)

        results = []
        for row in query:
            results.append(TopUserResponse(
                username=row.username,
                provider_user_id=row.provider_user_id,
                server_name=row.server_name,
                total_plays=row.total_plays,
                total_watch_time_minutes=int(row.total_watch_time_minutes or 0),
                completion_rate=float(row.avg_completion or 0)
            ))
        return results

    def get_top_movies(self, filters: AnalyticsFilters, limit: int = 5, allowed_server_ids: Optional[List[int]] = None) -> List[TopMediaResponse]:
        """Get most watched movies - grouped across all servers and years"""
        query = self.db.query(
            PlaybackEvent.media_title,
            func.min(PlaybackEvent.provider_media_id).label('provider_media_id'),
            func.min(PlaybackEvent.year).label('year'),  # Take the earliest year
            func.string_agg(func.distinct(Server.name), ', ').label('server_names'),
            func.count(PlaybackEvent.id).label('total_plays'),
            func.count(func.distinct(PlaybackEvent.username)).label('unique_users'),
            func.sum(
                case(
                    (PlaybackEvent.progress_ms > 0, PlaybackEvent.progress_ms),
                    else_=0
                ) / 60000
            ).label('total_watch_time_minutes')
        ).join(Server, PlaybackEvent.server_id == Server.id)\
         .filter(and_(
             self.get_date_filter(filters),
             self.get_server_filter(filters, allowed_server_ids),
             PlaybackEvent.media_type == 'movie',
             PlaybackEvent.media_title.isnot(None)
         ))\
         .group_by(PlaybackEvent.media_title)\
         .order_by(desc('total_plays'))\
         .limit(limit)

        results = []
        for row in query:
            results.append(TopMediaResponse(
                title=row.media_title,
                media_type='movie',
                provider_media_id=row.provider_media_id,
                server_name=row.server_names,  # Now shows all servers
                year=row.year,
                total_plays=row.total_plays,
                unique_users=row.unique_users,
                total_watch_time_minutes=int(row.total_watch_time_minutes or 0)
            ))
        return results

    def get_top_tv_shows(self, filters: AnalyticsFilters, limit: int = 5, allowed_server_ids: Optional[List[int]] = None) -> List[TopMediaResponse]:
        """Get most watched TV shows - grouped across all servers and years"""
        query = self.db.query(
            PlaybackEvent.grandparent_title,
            func.min(PlaybackEvent.year).label('year'),  # Take the earliest year
            func.string_agg(func.distinct(Server.name), ', ').label('server_names'),
            func.count(PlaybackEvent.id).label('total_plays'),
            func.count(func.distinct(PlaybackEvent.username)).label('unique_users'),
            func.sum(
                case(
                    (PlaybackEvent.progress_ms > 0, PlaybackEvent.progress_ms),
                    else_=0
                ) / 60000
            ).label('total_watch_time_minutes')
        ).join(Server, PlaybackEvent.server_id == Server.id)\
         .filter(and_(
             self.get_date_filter(filters),
             self.get_server_filter(filters, allowed_server_ids),
             PlaybackEvent.media_type == 'episode',
             PlaybackEvent.grandparent_title.isnot(None)
         ))\
         .group_by(PlaybackEvent.grandparent_title)\
         .order_by(desc('total_plays'))\
         .limit(limit)

        results = []
        for row in query:
            results.append(TopMediaResponse(
                title=row.grandparent_title,
                media_type='tv_show',
                server_name=row.server_names,  # Now shows all servers
                year=row.year,
                total_plays=row.total_plays,
                unique_users=row.unique_users,
                total_watch_time_minutes=int(row.total_watch_time_minutes or 0),
                grandparent_title=row.grandparent_title
            ))
        return results

    def get_top_libraries(self, filters: AnalyticsFilters, limit: int = 5, allowed_server_ids: Optional[List[int]] = None) -> List[TopLibraryResponse]:
        """Get most used libraries - combines libraries with the same name across servers"""
        query = self.db.query(
            PlaybackEvent.library_section,
            func.string_agg(func.distinct(Server.name), ', ').label('server_names'),
            func.count(PlaybackEvent.id).label('total_plays'),
            func.count(func.distinct(PlaybackEvent.username)).label('unique_users'),
            func.sum(
                case(
                    (PlaybackEvent.progress_ms > 0, PlaybackEvent.progress_ms),
                    else_=0
                ) / 60000
            ).label('total_watch_time_minutes'),
            func.array_agg(func.distinct(PlaybackEvent.media_type)).label('media_types')
        ).join(Server, PlaybackEvent.server_id == Server.id)\
         .filter(and_(
             self.get_date_filter(filters),
             self.get_server_filter(filters, allowed_server_ids),
             PlaybackEvent.library_section.isnot(None),
             PlaybackEvent.library_section != 'Unknown Library'  # Exclude Unknown Library
         ))\
         .group_by(PlaybackEvent.library_section)\
         .order_by(desc('total_plays'))\
         .limit(limit)

        results = []
        for row in query:
            results.append(TopLibraryResponse(
                library_name=row.library_section,
                server_name=row.server_names,  # Now shows all servers with this library
                total_plays=row.total_plays,
                unique_users=row.unique_users,
                total_watch_time_minutes=int(row.total_watch_time_minutes or 0),
                media_types=[t for t in (row.media_types or []) if t]
            ))
        return results

    def get_top_devices(self, filters: AnalyticsFilters, limit: int = 5, allowed_server_ids: Optional[List[int]] = None) -> List[TopDeviceResponse]:
        """Get most used devices"""
        query = self.db.query(
            PlaybackEvent.device,
            PlaybackEvent.platform,
            PlaybackEvent.product,
            func.count(PlaybackEvent.id).label('total_sessions'),
            func.count(func.distinct(PlaybackEvent.username)).label('unique_users'),
            func.sum(
                case(
                    (PlaybackEvent.progress_ms > 0, PlaybackEvent.progress_ms),
                    else_=0
                ) / 60000
            ).label('total_watch_time_minutes'),
            func.avg(
                case(
                    (PlaybackEvent.video_decision == 'transcode', 1.0),
                    else_=0.0
                )
            ).label('transcode_percentage')
        ).filter(and_(
             self.get_date_filter(filters),
             self.get_server_filter(filters, allowed_server_ids),
             PlaybackEvent.device.isnot(None)
         ))\
         .group_by(PlaybackEvent.device, PlaybackEvent.platform, PlaybackEvent.product)\
         .order_by(desc('total_sessions'))\
         .limit(limit)

        results = []
        for row in query:
            results.append(TopDeviceResponse(
                device_name=row.device,
                platform=row.platform,
                product=row.product,
                total_sessions=row.total_sessions,
                unique_users=row.unique_users,
                total_watch_time_minutes=int(row.total_watch_time_minutes or 0),
                transcode_percentage=float((row.transcode_percentage or 0) * 100)
            ))
        return results

    def get_dashboard_analytics(self, filters: AnalyticsFilters, allowed_server_ids: Optional[List[int]] = None) -> DashboardAnalyticsResponse:
        """Get comprehensive analytics for dashboard"""

        # Get summary stats
        base_query = self.db.query(PlaybackEvent).filter(and_(
            self.get_date_filter(filters),
            self.get_server_filter(filters, allowed_server_ids)
        ))

        total_sessions = base_query.count()
        total_users = base_query.filter(PlaybackEvent.username.isnot(None))\
                                .distinct(PlaybackEvent.username).count()

        # Total watch time in hours
        total_watch_time_result = base_query.with_entities(
            func.sum(
                case(
                    (PlaybackEvent.progress_ms > 0, PlaybackEvent.progress_ms),
                    else_=0
                ) / 3600000  # Convert to hours
            )
        ).scalar()
        total_watch_time_hours = int(total_watch_time_result or 0)

        # Completion rate (only count sessions with at least 10% progress)
        sessions_with_min_progress = base_query.filter(PlaybackEvent.progress_percent >= 10).count()
        completed_plays = base_query.filter(
            and_(
                PlaybackEvent.is_complete == True,
                PlaybackEvent.progress_percent >= 10
            )
        ).count()
        completion_rate = (completed_plays / sessions_with_min_progress * 100) if sessions_with_min_progress > 0 else 0

        # Transcode rate
        transcoded_sessions = base_query.filter(PlaybackEvent.video_decision == 'transcode').count()
        transcode_rate = (transcoded_sessions / total_sessions * 100) if total_sessions > 0 else 0

        return DashboardAnalyticsResponse(
            filters=filters,
            top_users=self.get_top_users(filters, limit=100, allowed_server_ids=allowed_server_ids),
            top_movies=self.get_top_movies(filters, limit=100, allowed_server_ids=allowed_server_ids),
            top_tv_shows=self.get_top_tv_shows(filters, limit=100, allowed_server_ids=allowed_server_ids),
            top_libraries=self.get_top_libraries(filters, limit=100, allowed_server_ids=allowed_server_ids),
            top_devices=self.get_top_devices(filters, limit=100, allowed_server_ids=allowed_server_ids),
            total_sessions=total_sessions,
            total_users=total_users,
            total_watch_time_hours=total_watch_time_hours,
            completion_rate=completion_rate,
            transcode_rate=transcode_rate
        )