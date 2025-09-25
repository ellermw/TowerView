import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()