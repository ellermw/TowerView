from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str
    jwt_secret_key: Optional[str] = None
    admin_username: str = "admin"
    admin_password: str = "admin"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Security
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Provider settings
    plex_client_id: Optional[str] = None
    emby_api_key: Optional[str] = None
    jellyfin_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False

    def model_post_init(self, __context):
        if not self.jwt_secret_key:
            self.jwt_secret_key = self.secret_key


settings = Settings()