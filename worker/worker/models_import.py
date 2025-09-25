"""
Direct model imports for worker to avoid circular dependencies
"""
import sys
sys.path.insert(0, '/backend')

# Import SQLAlchemy base and models directly
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean, JSON, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class ServerType(enum.Enum):
    plex = "plex"
    emby = "emby"
    jellyfin = "jellyfin"

class UserType(enum.Enum):
    admin = "admin"
    media_user = "media_user"

class ProviderType(enum.Enum):
    plex = "plex"
    emby = "emby"
    jellyfin = "jellyfin"

# Import the actual models
exec(open('/backend/app/models/server.py').read())
exec(open('/backend/app/models/user.py').read())
exec(open('/backend/app/models/session.py').read())
exec(open('/backend/app/models/media.py').read())
exec(open('/backend/app/models/credential.py').read())