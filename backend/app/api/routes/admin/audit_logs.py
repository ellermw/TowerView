"""
Audit log endpoints
"""
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from pydantic import BaseModel

from ....core.database import get_db
from ....core.security import get_current_staff_or_admin
from ....models.user import User
from ....models.audit_log import AuditLog

router = APIRouter()


class AuditLogResponse(BaseModel):
    id: int
    actor_id: Optional[int]
    actor_username: str
    actor_type: str
    action: str
    target: Optional[str]
    target_name: Optional[str]
    details: Optional[dict]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedAuditLogResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    per_page: int
    pages: int


@router.get("/audit-logs", response_model=PaginatedAuditLogResponse)
async def get_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    action: Optional[str] = None,
    actor: Optional[str] = None,
    actor_type: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """Get audit logs with optional filtering and pagination"""
    query = db.query(AuditLog)

    # Apply filters
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))

    if actor:
        query = query.filter(AuditLog.actor_username.ilike(f"%{actor}%"))

    if actor_type:
        query = query.filter(AuditLog.actor_type == actor_type)

    if search:
        query = query.filter(
            or_(
                AuditLog.actor_username.ilike(f"%{search}%"),
                AuditLog.action.ilike(f"%{search}%"),
                AuditLog.target_name.ilike(f"%{search}%")
            )
        )

    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)

    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)

    # Order by most recent first
    query = query.order_by(desc(AuditLog.created_at))

    # Get total count
    total = query.count()

    # Calculate pagination
    offset = (page - 1) * per_page
    pages = (total + per_page - 1) // per_page  # Ceiling division

    # Apply pagination
    logs = query.offset(offset).limit(per_page).all()

    return PaginatedAuditLogResponse(
        items=logs,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )


@router.get("/audit-logs/actions")
async def get_audit_log_actions(
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """Get list of unique audit log actions for filtering"""
    from sqlalchemy import distinct

    actions = db.query(distinct(AuditLog.action)).all()
    return [action[0] for action in actions if action[0]]


@router.get("/audit-logs/stats")
async def get_audit_stats(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """Get audit log statistics"""
    start_date = datetime.utcnow() - timedelta(days=days)

    # Get total count
    total_count = db.query(AuditLog).filter(
        AuditLog.created_at >= start_date
    ).count()

    # Get count by action
    from sqlalchemy import func
    action_counts = db.query(
        AuditLog.action,
        func.count(AuditLog.id).label('count')
    ).filter(
        AuditLog.created_at >= start_date
    ).group_by(AuditLog.action).all()

    # Get count by actor
    actor_counts = db.query(
        AuditLog.actor_username,
        func.count(AuditLog.id).label('count')
    ).filter(
        AuditLog.created_at >= start_date
    ).group_by(AuditLog.actor_username).limit(10).all()

    return {
        "total_events": total_count,
        "by_action": {action: count for action, count in action_counts},
        "top_actors": {actor: count for actor, count in actor_counts},
        "period_days": days
    }


@router.delete("/audit-logs")
async def clear_old_audit_logs(
    days_to_keep: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """Clear audit logs older than specified days (admin only)"""
    # Additional check - only admins can clear logs
    if current_user.type.value != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can clear audit logs"
        )

    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

    deleted_count = db.query(AuditLog).filter(
        AuditLog.created_at < cutoff_date
    ).delete()

    db.commit()

    # Log this action
    from ....services.audit_service import AuditService
    AuditService.log_audit_action(
        db,
        current_user,
        "AUDIT_LOGS_CLEARED",
        details={"deleted_count": deleted_count, "older_than_days": days_to_keep}
    )

    return {
        "deleted": deleted_count,
        "message": f"Deleted {deleted_count} audit logs older than {days_to_keep} days"
    }