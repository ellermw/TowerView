"""
Tautulli import settings and endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ....core.database import get_db
from ....core.security import get_current_staff_or_admin
from ....models.user import User
from ....models.server import Server, ServerType
from ....services.tautulli_service import TautulliService
from ....services.audit_service import AuditService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory storage for import progress
import_progress = {}


class TautulliConfig(BaseModel):
    server_id: int
    tautulli_url: str
    tautulli_api_key: str


class TautulliTestRequest(BaseModel):
    tautulli_url: str
    tautulli_api_key: str


class TautulliImportRequest(BaseModel):
    server_id: int
    tautulli_url: str
    tautulli_api_key: str
    after_date: Optional[str] = None  # YYYY-MM-DD format
    before_date: Optional[str] = None  # YYYY-MM-DD format


class ImportProgressResponse(BaseModel):
    status: str  # 'running', 'completed', 'failed', 'not_found'
    current: int
    total: int
    stats: dict


@router.post("/test")
async def test_tautulli_connection(
    request: TautulliTestRequest,
    current_user: User = Depends(get_current_staff_or_admin)
):
    """Test connection to Tautulli"""
    try:
        service = TautulliService(request.tautulli_url, request.tautulli_api_key)
        if service.test_connection():
            return {"success": True, "message": "Successfully connected to Tautulli"}
        else:
            raise HTTPException(status_code=400, detail="Failed to connect to Tautulli")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import")
async def start_tautulli_import(
    request: TautulliImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_or_admin)
):
    """Start importing historical data from Tautulli"""

    # Get server
    server = db.query(Server).filter(Server.id == request.server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    logger.info(f"Import request for server: id={server.id}, name={server.name}, type={server.type}, type.value={server.type.value if hasattr(server.type, 'value') else 'N/A'}")

    # Compare using enum or string value
    is_plex = server.type == ServerType.plex or (hasattr(server.type, 'value') and server.type.value == 'plex')

    if not is_plex:
        raise HTTPException(status_code=400, detail=f"Tautulli import only works with Plex servers. Server '{server.name}' is type '{server.type}'")

    # Create import task ID
    import_id = f"{server.id}_{datetime.utcnow().timestamp()}"

    # Initialize progress tracking
    import_progress[import_id] = {
        'status': 'running',
        'current': 0,
        'total': 0,
        'stats': {
            'imported': 0,
            'skipped': 0,
            'errors': 0
        }
    }

    # Start import in background
    background_tasks.add_task(
        _run_import,
        import_id,
        request.server_id,
        request.tautulli_url,
        request.tautulli_api_key,
        request.after_date,
        request.before_date,
        current_user.id
    )

    # Log audit event
    AuditService.log_action(
        db=db,
        actor=current_user,
        action="tautulli_import_started",
        target="server",
        target_name=server.name,
        details={
            "server_id": server.id,
            "after_date": request.after_date,
            "before_date": request.before_date
        }
    )

    return {
        "success": True,
        "import_id": import_id,
        "message": "Import started in background"
    }


@router.get("/import/{import_id}/progress")
async def get_import_progress(
    import_id: str,
    current_user: User = Depends(get_current_staff_or_admin)
):
    """Get progress of a Tautulli import"""
    if import_id not in import_progress:
        return ImportProgressResponse(
            status='not_found',
            current=0,
            total=0,
            stats={}
        )

    progress_data = import_progress[import_id]
    return ImportProgressResponse(
        status=progress_data['status'],
        current=progress_data['current'],
        total=progress_data['total'],
        stats=progress_data['stats']
    )


def _run_import(
    import_id: str,
    server_id: int,
    tautulli_url: str,
    tautulli_api_key: str,
    after_date: Optional[str],
    before_date: Optional[str],
    user_id: int
):
    """Background task to run the import"""
    from ....core.database import SessionLocal

    db = SessionLocal()

    try:
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            import_progress[import_id]['status'] = 'failed'
            import_progress[import_id]['error'] = 'Server not found'
            return

        service = TautulliService(tautulli_url, tautulli_api_key)

        def progress_callback(current, total, stats):
            import_progress[import_id].update({
                'current': current,
                'total': total,
                'stats': stats
            })

        stats = service.import_history_to_database(
            db=db,
            server=server,
            after_date=after_date,
            before_date=before_date,
            progress_callback=progress_callback
        )

        import_progress[import_id]['status'] = 'completed'
        import_progress[import_id]['stats'] = stats

        # Log completion
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            AuditService.log_action(
                db=db,
                actor=user,
                action="tautulli_import_completed",
                target="server",
                target_name=server.name,
                details={
                    "server_id": server_id,
                    "stats": stats
                }
            )

        logger.info(f"Tautulli import completed for server {server.name}: {stats}")

    except Exception as e:
        logger.error(f"Tautulli import failed: {str(e)}")
        import_progress[import_id]['status'] = 'failed'
        import_progress[import_id]['error'] = str(e)

    finally:
        db.close()
