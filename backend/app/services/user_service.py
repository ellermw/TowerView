from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.user import User, UserType
from ..schemas.user import UserCreate


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_user_by_username(self, username: str, user_type: UserType = None) -> Optional[User]:
        query = self.db.query(User).filter(User.username == username)
        if user_type:
            query = query.filter(User.type == user_type)
        return query.first()

    def get_media_user_by_provider_id(self, provider_user_id: str, server_id: int) -> Optional[User]:
        return self.db.query(User).filter(
            User.provider_user_id == provider_user_id,
            User.server_id == server_id,
            User.type == UserType.media_user
        ).first()

    def get_users_by_server(self, server_id: int) -> List[User]:
        return self.db.query(User).filter(
            User.server_id == server_id,
            User.type == UserType.media_user
        ).all()

    def create_user(self, user_data: UserCreate) -> User:
        user = User(**user_data.dict())
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user