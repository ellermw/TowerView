"""
Tautulli integration service for importing historical playback data
"""
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from ..models.playback_analytics import PlaybackEvent
from ..models.server import Server, ServerType
import logging

logger = logging.getLogger(__name__)


class TautulliService:
    def __init__(self, base_url: str, api_key: str):
        """
        Initialize Tautulli service

        Args:
            base_url: Tautulli base URL (e.g., http://localhost:8181)
            api_key: Tautulli API key
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def _make_request(self, cmd: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make API request to Tautulli"""
        url = f"{self.base_url}/api/v2"

        request_params = {
            'apikey': self.api_key,
            'cmd': cmd
        }

        if params:
            request_params.update(params)

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=request_params)
                response.raise_for_status()
                data = response.json()

                if data.get('response', {}).get('result') == 'success':
                    return data.get('response', {}).get('data', {})
                else:
                    error_msg = data.get('response', {}).get('message', 'Unknown error')
                    raise Exception(f"Tautulli API error: {error_msg}")

        except httpx.HTTPError as e:
            logger.error(f"Tautulli API request failed: {str(e)}")
            raise Exception(f"Failed to connect to Tautulli: {str(e)}")

    def get_history(
        self,
        start: int = 0,
        length: int = 100,
        after: Optional[str] = None,
        before: Optional[str] = None,
        section_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get playback history from Tautulli

        Args:
            start: Starting record number
            length: Number of records to return (max 1000)
            after: Get history after this date (YYYY-MM-DD)
            before: Get history before this date (YYYY-MM-DD)
            section_id: Filter by library section ID

        Returns:
            Dictionary with 'data' (list of history records) and 'recordsFiltered' (total count)
        """
        params = {
            'start': start,
            'length': min(length, 1000),  # Cap at 1000 per request
            'order_column': 'date',
            'order_dir': 'desc'
        }

        if after:
            params['after'] = after
        if before:
            params['before'] = before
        if section_id is not None:
            params['section_id'] = section_id

        return self._make_request('get_history', params)

    def test_connection(self) -> bool:
        """Test connection to Tautulli"""
        try:
            result = self._make_request('get_server_info')
            return bool(result)
        except Exception as e:
            logger.error(f"Tautulli connection test failed: {str(e)}")
            return False

    def import_history_to_database(
        self,
        db: Session,
        server: Server,
        after_date: Optional[str] = None,
        before_date: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, int]:
        """
        Import Tautulli history into TowerView database

        Args:
            db: Database session
            server: Server model instance (must be a Plex server)
            after_date: Import history after this date (YYYY-MM-DD)
            before_date: Import history before this date (YYYY-MM-DD)
            progress_callback: Optional callback function for progress updates

        Returns:
            Dictionary with stats: imported, skipped, errors
        """
        is_plex = server.type == ServerType.plex or (hasattr(server.type, 'value') and server.type.value == 'plex')
        if not is_plex:
            raise ValueError("Tautulli import only supports Plex servers")

        stats = {
            'imported': 0,
            'skipped': 0,
            'errors': 0,
            'total': 0
        }

        # First request to get total count
        initial_data = self.get_history(start=0, length=1, after=after_date, before=before_date)
        total_records = initial_data.get('recordsFiltered', 0)
        stats['total'] = total_records

        if total_records == 0:
            logger.info("No history records found in Tautulli")
            return stats

        logger.info(f"Starting import of {total_records} records from Tautulli")

        # Import in batches
        batch_size = 1000
        start = 0

        while start < total_records:
            try:
                # Get batch of history
                history_data = self.get_history(
                    start=start,
                    length=batch_size,
                    after=after_date,
                    before=before_date
                )

                records = history_data.get('data', [])

                for record in records:
                    try:
                        # Check if this session already exists
                        session_id = f"tautulli_{record.get('reference_id', record.get('id'))}"
                        existing = db.query(PlaybackEvent).filter(
                            PlaybackEvent.provider_session_id == session_id
                        ).first()

                        if existing:
                            stats['skipped'] += 1
                            continue

                        # Map Tautulli data to PlaybackEvent
                        event = self._map_tautulli_record(record, server.id, session_id)

                        db.add(event)
                        stats['imported'] += 1

                        # Commit in batches of 100
                        if stats['imported'] % 100 == 0:
                            db.commit()

                    except Exception as e:
                        logger.error(f"Error importing record: {str(e)}")
                        stats['errors'] += 1

                # Commit remaining records
                db.commit()

                # Update progress
                if progress_callback:
                    progress_callback(start + len(records), total_records, stats)

                start += batch_size
                logger.info(f"Imported {stats['imported']} of {total_records} records...")

            except Exception as e:
                logger.error(f"Error importing batch starting at {start}: {str(e)}")
                stats['errors'] += len(records) if 'records' in locals() else batch_size
                start += batch_size

        logger.info(f"Import complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats

    def _map_tautulli_record(self, record: Dict[str, Any], server_id: int, session_id: str) -> PlaybackEvent:
        """Map Tautulli history record to PlaybackEvent model"""

        # Parse timestamps
        started_at = datetime.fromtimestamp(record.get('started', 0)) if record.get('started') else None
        ended_at = datetime.fromtimestamp(record.get('stopped', 0)) if record.get('stopped') else None

        # Calculate progress
        duration_ms = (record.get('duration', 0) or 0) * 1000
        progress_ms = (record.get('play_duration', 0) or 0) * 1000
        progress_percent = float(record.get('percent_complete', 0) or 0)

        # Determine if complete (>= 90% watched)
        is_complete = progress_percent >= 90
        is_watched = progress_percent >= 10

        # Map media type
        media_type_map = {
            'movie': 'movie',
            'episode': 'episode',
            'track': 'track',
            'clip': 'clip'
        }
        media_type = media_type_map.get(record.get('media_type', '').lower(), record.get('media_type'))

        # Determine HDR flags
        video_full_resolution = record.get('video_full_resolution', '')
        is_4k = '4K' in video_full_resolution or 'UHD' in video_full_resolution or (record.get('video_resolution', '') or '').startswith('4k')
        is_hdr = 'HDR' in video_full_resolution.upper() or record.get('video_dynamic_range', '').upper() == 'HDR'
        is_dolby_vision = 'DV' in video_full_resolution.upper() or 'DOLBY' in video_full_resolution.upper()

        return PlaybackEvent(
            server_id=server_id,
            provider_session_id=session_id,
            provider_user_id=str(record.get('user_id', '')),
            provider_media_id=str(record.get('rating_key', '')),

            # Media information
            media_title=record.get('title') or record.get('full_title'),
            media_type=media_type,
            grandparent_title=record.get('grandparent_title'),
            parent_title=record.get('parent_title'),
            season_number=record.get('parent_media_index'),
            episode_number=record.get('media_index'),
            library_section=record.get('library_name'),
            year=str(record.get('year', '')) if record.get('year') else None,

            # Playback details
            device=record.get('player'),
            platform=record.get('platform'),
            product=record.get('product'),
            username=record.get('friendly_name') or record.get('user'),

            # Session metrics
            duration_ms=duration_ms,
            progress_ms=progress_ms,
            progress_percent=progress_percent,

            # Streaming details
            video_decision=record.get('transcode_decision', '').lower(),
            original_resolution=record.get('video_resolution') or video_full_resolution,
            original_bitrate=str(record.get('bitrate', '')),
            video_codec=record.get('video_codec'),
            audio_codec=record.get('audio_codec'),
            container=record.get('container'),

            # Quality flags
            is_4k=is_4k,
            is_hdr=is_hdr,
            is_dolby_vision=is_dolby_vision,

            # Analytics flags
            is_complete=is_complete,
            is_watched=is_watched,

            # Timestamps
            started_at=started_at,
            ended_at=ended_at
        )
