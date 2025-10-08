from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, text, case
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from ..models.playback_analytics import PlaybackEvent, DailyAnalytics
from ..models.server import Server
from ..schemas.analytics import (
    AnalyticsFilters, TopUserResponse, TopMediaResponse,
    TopLibraryResponse, TopDeviceResponse, TopClientResponse, DashboardAnalyticsResponse,
    PlaybackEventCreate
)


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def normalize_device_name(device: str) -> str:
        """Normalize device names to combine similar variants"""
        if not device:
            return "Unknown Device"

        device_lower = device.lower().strip()

        # Apple TV variants (including user-named ones)
        if "apple tv" in device_lower or device_lower == "appletv":
            return "Apple TV"

        # Roku TV variants (combine all Roku devices)
        if "roku" in device_lower:
            # If it's a specific TV brand, keep more detail
            if "tcl" in device_lower:
                return "TCL Roku TV"
            elif "hisense" in device_lower:
                return "Hisense Roku TV"
            elif "rca" in device_lower:
                return "RCA Roku TV"
            elif "sharp" in device_lower:
                return "Sharp Roku TV"
            else:
                return "Roku"

        # Fire TV variants (user-named Fire TVs)
        if "fire tv" in device_lower or "firetv" in device_lower:
            return "Fire TV"

        # Android TV generic (user-named Android TVs)
        if "android" in device_lower and ("tv" in device_lower or device_lower in ["aftka", "aftsss"]):
            return "Android TV"

        # Smart TV variants
        if "smart tv" in device_lower or "smarttv" in device_lower:
            return "Smart TV"

        # Chromecast variants
        if "chromecast" in device_lower:
            return "Chromecast"

        # iPhone/iPad
        if "iphone" in device_lower:
            return "iPhone"
        if "ipad" in device_lower:
            return "iPad"

        # Desktop/Web browsers
        if "chrome" in device_lower and "cast" not in device_lower:
            return "Chrome Browser"
        if "firefox" in device_lower:
            return "Firefox Browser"
        if "safari" in device_lower:
            return "Safari Browser"
        if "edge" in device_lower:
            return "Edge Browser"

        # Gaming consoles
        if "xbox" in device_lower:
            return "Xbox"
        if "playstation" in device_lower or "ps4" in device_lower or "ps5" in device_lower:
            return "PlayStation"

        # Keep original if no match (useful for user-named devices)
        return device.strip()

    @staticmethod
    def normalize_client_name(product: str) -> str:
        """Normalize client/product names to combine similar variants"""
        if not product:
            return "Unknown Client"

        product_lower = product.lower().strip()

        # Plex clients
        if "plex" in product_lower:
            if "android" in product_lower and "tv" in product_lower:
                return "Plex for Android TV"
            elif "android" in product_lower:
                return "Plex for Android"
            elif "apple tv" in product_lower or "appletv" in product_lower or "tvos" in product_lower:
                return "Plex for Apple TV"
            elif "roku" in product_lower:
                return "Plex for Roku"
            elif "ios" in product_lower or "iphone" in product_lower:
                return "Plex for iOS"
            elif "web" in product_lower or "chrome" in product_lower or "firefox" in product_lower or "safari" in product_lower:
                return "Plex Web"
            elif "xbox" in product_lower:
                return "Plex for Xbox"
            elif "playstation" in product_lower or "ps4" in product_lower or "ps5" in product_lower:
                return "Plex for PlayStation"
            else:
                return "Plex"

        # Emby clients
        if "emby" in product_lower:
            if "apple tv" in product_lower or "appletv" in product_lower:
                return "Emby for Apple TV"
            elif "android" in product_lower and "tv" in product_lower:
                return "Emby for Android TV"
            elif "android" in product_lower:
                return "Emby for Android"
            elif "roku" in product_lower:
                return "Emby for Roku"
            elif "ios" in product_lower:
                return "Emby for iOS"
            elif "web" in product_lower:
                return "Emby Web"
            else:
                return "Emby"

        # Jellyfin clients
        if "jellyfin" in product_lower:
            if "roku" in product_lower:
                return "Jellyfin for Roku"
            elif "android" in product_lower and "tv" in product_lower:
                return "Jellyfin for Android TV"
            elif "android" in product_lower:
                return "Jellyfin for Android"
            elif "apple tv" in product_lower or "appletv" in product_lower or "tvos" in product_lower:
                return "Jellyfin for Apple TV"
            elif "ios" in product_lower:
                return "Jellyfin for iOS"
            elif "media player" in product_lower:
                return "Jellyfin Media Player"
            elif "web" in product_lower:
                return "Jellyfin Web"
            else:
                return "Jellyfin"

        # Third-party clients
        if "infuse" in product_lower:
            return "Infuse"
        if "vidhub" in product_lower:
            return "VidHub"
        if "senplayer" in product_lower:
            return "SenPlayer"
        if "mrmc" in product_lower:
            return "MrMC"
        if "kodi" in product_lower:
            return "Kodi"

        # Android TV variants (standalone)
        if ("androidtv" in product_lower.replace(" ", "") or
            "android tv" in product_lower or
            "android_tv" in product_lower):
            return "Android TV"

        # Roku variants (standalone)
        if "roku" in product_lower:
            return "Roku"

        # Return original if no match found (capitalize first letter of each word)
        return " ".join(word.capitalize() for word in product.split())

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

    def get_top_clients(self, filters: AnalyticsFilters, limit: int = 5, allowed_server_ids: Optional[List[int]] = None) -> List[TopClientResponse]:
        """Get most used clients (products) with normalized names"""
        # Get all playback data
        query = self.db.query(
            PlaybackEvent.device,
            PlaybackEvent.platform,
            PlaybackEvent.product,
            PlaybackEvent.username,
            PlaybackEvent.progress_ms,
            PlaybackEvent.video_decision
        ).filter(and_(
             self.get_date_filter(filters),
             self.get_server_filter(filters, allowed_server_ids),
             PlaybackEvent.product.isnot(None)  # Filter by product
         ))

        # Aggregate by normalized client name (product)
        client_stats = defaultdict(lambda: {
            'total_plays': 0,
            'unique_users': set(),
            'total_watch_time_ms': 0,
            'transcode_count': 0,
            'platform': None,
            'devices': set()  # Track unique devices using this client
        })

        for row in query:
            normalized_client = self.normalize_client_name(row.product)
            stats = client_stats[normalized_client]

            stats['total_plays'] += 1
            if row.username:
                stats['unique_users'].add(row.username)
            if row.progress_ms and row.progress_ms > 0:
                stats['total_watch_time_ms'] += row.progress_ms
            if row.video_decision == 'transcode':
                stats['transcode_count'] += 1

            # Track devices and platform
            if row.device:
                stats['devices'].add(row.device)
            if not stats['platform'] and row.platform:
                stats['platform'] = row.platform

        # Convert to TopClientResponse objects
        results = []
        for client_name, stats in client_stats.items():
            transcode_percentage = (stats['transcode_count'] / stats['total_plays'] * 100) if stats['total_plays'] > 0 else 0

            # Use platform as the subtitle
            platform_text = stats['platform'] if stats['platform'] else f"{len(stats['devices'])} devices"

            results.append(TopClientResponse(
                client_name=client_name,  # Client name (e.g., "Plex for Roku")
                platform=platform_text,  # Platform or device count
                total_plays=stats['total_plays'],
                unique_users=len(stats['unique_users']),
                total_watch_time_minutes=int(stats['total_watch_time_ms'] / 60000),
                transcode_percentage=transcode_percentage
            ))

        # Sort by total_plays descending and limit
        results.sort(key=lambda x: x.total_plays, reverse=True)
        return results[:limit]

    def get_top_devices(self, filters: AnalyticsFilters, limit: int = 5, allowed_server_ids: Optional[List[int]] = None) -> List[TopDeviceResponse]:
        """Get most used devices with normalized names"""
        # Get all playback data
        query = self.db.query(
            PlaybackEvent.device,
            PlaybackEvent.platform,
            PlaybackEvent.product,
            PlaybackEvent.username,
            PlaybackEvent.progress_ms,
            PlaybackEvent.video_decision
        ).filter(and_(
             self.get_date_filter(filters),
             self.get_server_filter(filters, allowed_server_ids),
             PlaybackEvent.device.isnot(None)  # Filter by device
         ))

        # Aggregate by normalized device name
        device_stats = defaultdict(lambda: {
            'total_plays': 0,
            'unique_users': set(),
            'total_watch_time_ms': 0,
            'transcode_count': 0,
            'platform': None,
            'clients': set()  # Track unique clients used on this device
        })

        for row in query:
            normalized_device = self.normalize_device_name(row.device)
            stats = device_stats[normalized_device]

            stats['total_plays'] += 1
            if row.username:
                stats['unique_users'].add(row.username)
            if row.progress_ms and row.progress_ms > 0:
                stats['total_watch_time_ms'] += row.progress_ms
            if row.video_decision == 'transcode':
                stats['transcode_count'] += 1

            # Track clients and platform
            if row.product:
                stats['clients'].add(row.product)
            if not stats['platform'] and row.platform:
                stats['platform'] = row.platform

        # Convert to TopDeviceResponse objects
        results = []
        for device_name, stats in device_stats.items():
            transcode_percentage = (stats['transcode_count'] / stats['total_plays'] * 100) if stats['total_plays'] > 0 else 0

            # Show platform or client count as subtitle
            platform_text = stats['platform'] if stats['platform'] else f"{len(stats['clients'])} clients"

            results.append(TopDeviceResponse(
                device_name=device_name,  # Device name (e.g., "Apple TV", "TCL Roku TV")
                platform=platform_text,  # Platform or client count
                product=None,
                total_plays=stats['total_plays'],
                unique_users=len(stats['unique_users']),
                total_watch_time_minutes=int(stats['total_watch_time_ms'] / 60000),
                transcode_percentage=transcode_percentage
            ))

        # Sort by total_plays descending and limit
        results.sort(key=lambda x: x.total_plays, reverse=True)
        return results[:limit]

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
            top_clients=self.get_top_clients(filters, limit=100, allowed_server_ids=allowed_server_ids),
            total_sessions=total_sessions,
            total_users=total_users,
            total_watch_time_hours=total_watch_time_hours,
            completion_rate=completion_rate,
            transcode_rate=transcode_rate
        )