import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from celery import current_task
from sqlalchemy.orm import Session

from .celery_app import celery_app
from .database import get_db

# Import shared models from local simplified version
from .models import Server, ServerType, ProviderType, Session as MediaSession, Media, User, Credential

logger = logging.getLogger(__name__)

def create_provider(server: Server, db: Session):
    """Create a provider instance for the given server without circular imports"""
    # Import providers here to avoid circular import
    import sys
    sys.path.insert(0, '/backend')
    from app.providers.plex import PlexProvider
    from app.providers.emby import EmbyProvider
    from app.providers.jellyfin import JellyfinProvider
    from .encryption import credential_encryption

    # Get credentials for the server
    credentials_obj = db.query(Credential).filter(
        Credential.server_id == server.id
    ).first()

    credentials = {}
    if credentials_obj and credentials_obj.encrypted_payload:
        try:
            credentials = credential_encryption.decrypt_credentials(credentials_obj.encrypted_payload)
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for server {server.id}: {str(e)}")
            credentials = {}

    if server.type == ServerType.plex:
        return PlexProvider(server, credentials)
    elif server.type == ServerType.emby:
        return EmbyProvider(server, credentials)
    elif server.type == ServerType.jellyfin:
        return JellyfinProvider(server, credentials)
    else:
        raise ValueError(f"Unsupported server type: {server.type}")


@celery_app.task(bind=True)
def poll_all_servers(self):
    """Poll all enabled servers for active sessions"""
    logger.info("Starting server polling task")

    db = get_db()
    try:
        # Get all enabled servers
        servers = db.query(Server).filter(Server.enabled == True).all()
        logger.info(f"Found {len(servers)} enabled servers to poll")

        for server in servers:
            try:
                # Poll each server asynchronously
                asyncio.run(poll_server_sessions(server, db))
            except Exception as e:
                logger.error(f"Error polling server {server.id} ({server.name}): {str(e)}")

        logger.info("Completed server polling task")
        return {"status": "completed", "servers_polled": len(servers)}

    except Exception as e:
        logger.error(f"Error in poll_all_servers task: {str(e)}")
        raise self.retry(countdown=60, max_retries=3)
    finally:
        db.close()


async def poll_server_sessions(server: Server, db: Session):
    """Poll a single server for active sessions"""
    try:
        provider = create_provider(server, db)

        # Test connection first
        if not await provider.connect():
            logger.warning(f"Cannot connect to server {server.name}")
            return

        # Get active sessions from provider
        provider_sessions = await provider.list_active_sessions()
        logger.debug(f"Found {len(provider_sessions)} sessions on server {server.name}")

        # Update server last seen
        server.last_seen_at = datetime.utcnow()

        # Process each session
        for session_data in provider_sessions:
            await process_session(session_data, server, db)

        # Mark sessions as ended if they're no longer active
        await cleanup_inactive_sessions(server, provider_sessions, db)

        db.commit()

    except Exception as e:
        logger.error(f"Error polling server {server.name}: {str(e)}")
        db.rollback()


async def process_session(session_data: dict, server: Server, db: Session):
    """Process a single session from provider data"""
    provider_session_id = session_data.get('session_id')
    if not provider_session_id:
        return

    # Find or create session
    session = db.query(MediaSession).filter(
        MediaSession.server_id == server.id,
        MediaSession.provider_session_id == provider_session_id
    ).first()

    if not session:
        # Create new session
        session = MediaSession(
            server_id=server.id,
            provider_session_id=provider_session_id,
            state=session_data.get('state', 'unknown'),
            progress_seconds=session_data.get('progress', 0),
            session_metadata=session_data
        )
        db.add(session)
        logger.info(f"Created new session {provider_session_id} on server {server.name}")
    else:
        # Update existing session
        session.state = session_data.get('state', session.state)
        session.progress_seconds = session_data.get('progress', session.progress_seconds)
        session.updated_at = datetime.utcnow()
        session.session_metadata = session_data

    # Try to find/create associated user
    if session_data.get('user_id'):
        user = await find_or_create_user(session_data, server, db)
        if user:
            session.user_id = user.id

    # Try to find/create associated media
    if session_data.get('media_id'):
        media = await find_or_create_media(session_data, server, db)
        if media:
            session.media_id = media.id


async def find_or_create_user(session_data: dict, server: Server, db: Session):
    """Find or create a user from session data"""
    provider_user_id = session_data.get('user_id')
    if not provider_user_id:
        return None

    # Check if user already exists
    user = db.query(User).filter(
        User.provider_user_id == provider_user_id,
        User.server_id == server.id
    ).first()

    if not user:
        # Create new media user
        # Convert ServerType to ProviderType (they have the same values)
        provider_type = ProviderType[server.type.name]
        user = User(
            type='media_user',
            provider=provider_type,
            provider_user_id=provider_user_id,
            server_id=server.id,
            username=session_data.get('username', f'user_{provider_user_id}')
        )
        db.add(user)
        logger.info(f"Created new user {user.username} for server {server.name}")

    return user


async def find_or_create_media(session_data: dict, server: Server, db: Session):
    """Find or create media from session data"""
    provider_media_id = session_data.get('media_id')
    if not provider_media_id:
        return None

    # Check if media already exists
    media = db.query(Media).filter(
        Media.provider_media_id == provider_media_id,
        Media.server_id == server.id
    ).first()

    if not media:
        # Create new media entry
        media = Media(
            server_id=server.id,
            provider_media_id=provider_media_id,
            title=session_data.get('media_title', 'Unknown'),
            type=session_data.get('media_type', 'unknown'),
            media_metadata=session_data
        )
        db.add(media)
        logger.info(f"Created new media '{media.title}' for server {server.name}")

    return media


async def cleanup_inactive_sessions(server: Server, active_sessions: List[dict], db: Session):
    """Mark sessions as ended if they're no longer active"""
    active_session_ids = {s.get('session_id') for s in active_sessions if s.get('session_id')}

    # Find sessions that are no longer active
    inactive_sessions = db.query(MediaSession).filter(
        MediaSession.server_id == server.id,
        MediaSession.ended_at.is_(None),
        ~MediaSession.provider_session_id.in_(active_session_ids)
    ).all()

    for session in inactive_sessions:
        session.ended_at = datetime.utcnow()
        logger.debug(f"Marked session {session.provider_session_id} as ended")


@celery_app.task
def cleanup_old_sessions():
    """Clean up old ended sessions"""
    logger.info("Starting session cleanup task")

    db = get_db()
    try:
        # Remove sessions older than 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        deleted_count = db.query(MediaSession).filter(
            MediaSession.ended_at < cutoff_date
        ).delete()

        db.commit()
        logger.info(f"Cleaned up {deleted_count} old sessions")

        return {"status": "completed", "sessions_cleaned": deleted_count}

    except Exception as e:
        logger.error(f"Error in cleanup_old_sessions task: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task
def update_server_status():
    """Update server connection status"""
    logger.info("Starting server status update task")

    db = get_db()
    try:
        servers = db.query(Server).all()
        updated_count = 0

        for server in servers:
            try:
                provider = create_provider(server, db)
                is_online = asyncio.run(provider.connect())

                if is_online != server.enabled:
                    server.enabled = is_online
                    updated_count += 1

                if is_online:
                    server.last_seen_at = datetime.utcnow()

            except Exception as e:
                logger.error(f"Error checking server {server.name}: {str(e)}")
                server.enabled = False
                updated_count += 1

        db.commit()
        logger.info(f"Updated status for {updated_count} servers")

        return {"status": "completed", "servers_updated": updated_count}

    except Exception as e:
        logger.error(f"Error in update_server_status task: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task
def test_connection(server_id: int):
    """Test connection to a specific server"""
    db = get_db()
    try:
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            return {"status": "error", "message": "Server not found"}

        provider = create_provider(server, db)
        is_connected = asyncio.run(provider.connect())

        return {
            "status": "success",
            "server_id": server_id,
            "connected": is_connected
        }

    except Exception as e:
        logger.error(f"Error testing connection to server {server_id}: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()