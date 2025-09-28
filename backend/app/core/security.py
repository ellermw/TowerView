from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from ..models.user import User, UserType

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")
    return encoded_jwt


def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise credentials_exception

    user_id: int = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    return user


async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.type != UserType.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def get_current_media_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.type != UserType.media_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Media user access required"
        )
    return current_user


async def get_current_local_user(current_user: User = Depends(get_current_user)) -> User:
    # Backward compatibility - treat local_user as staff
    if current_user.type not in [UserType.local_user, UserType.staff]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required"
        )
    return current_user


async def get_current_staff_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current staff user (can create support users, manage servers)"""
    if current_user.type not in [UserType.admin, UserType.staff, UserType.local_user]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required"
        )
    return current_user


async def get_current_staff_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Get current staff or admin user"""
    if current_user.type not in [UserType.admin, UserType.staff, UserType.local_user]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff or Admin access required"
        )
    return current_user


async def get_current_admin_or_local_user(current_user: User = Depends(get_current_user)) -> User:
    # Allow admin, staff (formerly local_user), and support users
    if current_user.type not in [UserType.admin, UserType.staff, UserType.local_user, UserType.support]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authorized user access required"
        )
    return current_user


async def get_user_creation_allowed(current_user: User = Depends(get_current_user)) -> User:
    """Check if user can create other users"""
    # Admin can create any user, Staff can create support users, Support cannot create users
    if current_user.type not in [UserType.admin, UserType.staff, UserType.local_user]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User creation privileges required"
        )
    return current_user


async def get_user_deletion_allowed(current_user: User = Depends(get_current_user)) -> User:
    """Check if user can delete other users - only admins"""
    if current_user.type != UserType.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete users"
        )
    return current_user


def get_current_user_from_token(token: str, db: Session) -> Optional[User]:
    """Get user from a raw token string (used for WebSocket auth)"""
    payload = verify_token(token)

    if payload is None:
        return None

    user_id: int = payload.get("sub")
    if user_id is None:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    return user