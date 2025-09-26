"""
Bandwidth caching service for real-time bandwidth tracking
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging
from collections import deque

logger = logging.getLogger(__name__)

# Global bandwidth history cache
bandwidth_history: deque = deque(maxlen=150)  # Keep last 150 data points (5 minutes at 2-second intervals)
cache_lock = asyncio.Lock()

# Global reference to background task
background_task = None


async def track_bandwidth_point(sessions: List[Dict[str, Any]]):
    """Track a single bandwidth data point from sessions"""
    async with cache_lock:
        try:
            # Calculate total bandwidth and per-server bandwidth
            total_bandwidth = 0
            server_bandwidths: Dict[str, int] = {}

            for session in sessions:
                # Extract bandwidth value
                bandwidth_value = 0
                if session.get('session_bandwidth'):
                    bandwidth_str = session['session_bandwidth']
                    if isinstance(bandwidth_str, (int, float)):
                        bandwidth_value = int(bandwidth_str)
                    elif isinstance(bandwidth_str, str):
                        try:
                            bandwidth_value = int(bandwidth_str)
                        except (ValueError, TypeError):
                            bandwidth_value = 0

                total_bandwidth += bandwidth_value

                # Group by server
                server_name = session.get('server_name') or f"Server {session.get('server_id', 'Unknown')}"
                server_bandwidths[server_name] = server_bandwidths.get(server_name, 0) + bandwidth_value

            # Add to history
            bandwidth_history.append({
                'timestamp': datetime.utcnow().isoformat(),
                'total_bandwidth': total_bandwidth,
                'server_bandwidths': server_bandwidths
            })

            logger.debug(f"Tracked bandwidth point: Total={total_bandwidth}, Servers={list(server_bandwidths.keys())}")

        except Exception as e:
            logger.error(f"Error tracking bandwidth point: {e}")


async def get_bandwidth_history() -> Dict[str, Any]:
    """Get cached bandwidth history"""
    async with cache_lock:
        # Convert deque to list for JSON serialization
        history_list = list(bandwidth_history)

        # Get current stats from latest point
        current_stats = {}
        if history_list:
            latest = history_list[-1]
            current_stats = {
                'current_total': latest.get('total_bandwidth', 0),
                'current_servers': latest.get('server_bandwidths', {})
            }

        return {
            'history': history_list,
            'stats': current_stats,
            'cache_size': len(history_list),
            'max_points': 150
        }


async def start_bandwidth_tracking(initial_db):
    """Start background bandwidth tracking task"""
    global background_task

    if background_task and not background_task.done():
        logger.info("Bandwidth tracking already running")
        return

    async def track_bandwidth_loop():
        """Background task to track bandwidth every 2 seconds"""
        logger.info("Started bandwidth tracking background task")

        while True:
            try:
                # For now, just track empty bandwidth data
                # The actual sessions will be fetched from the /admin/sessions endpoint
                sessions = []

                # Track bandwidth point (will be empty for now)
                await track_bandwidth_point(sessions)

                # Wait 2 seconds before next update
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error in bandwidth tracking loop: {e}")
                await asyncio.sleep(2)  # Continue after error

    background_task = asyncio.create_task(track_bandwidth_loop())
    logger.info("Bandwidth tracking task created")


def stop_bandwidth_tracking():
    """Stop the background bandwidth tracking task"""
    global background_task

    if background_task and not background_task.done():
        background_task.cancel()
        logger.info("Bandwidth tracking task cancelled")