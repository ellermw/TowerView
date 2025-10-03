"""
Migration script to add new user role types (staff and support) to the database
Run this script before migrating existing local_user accounts
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
import sys
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings

# Configure logging for migration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_new_role_types():
    """Add staff and support roles to usertype enum"""

    # Create database connection
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            # First, check if the new values already exist
            result = conn.execute(
                text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'usertype'::regtype")
            )
            existing_values = [row[0] for row in result]

            # Add 'staff' if not exists
            if 'staff' not in existing_values:
                conn.execute(
                    text("ALTER TYPE usertype ADD VALUE 'staff'")
                )
                logger.info("Added 'staff' to usertype enum")
            else:
                logger.info("'staff' already exists in usertype enum")

            # Add 'support' if not exists
            if 'support' not in existing_values:
                conn.execute(
                    text("ALTER TYPE usertype ADD VALUE 'support'")
                )
                logger.info("Added 'support' to usertype enum")
            else:
                logger.info("'support' already exists in usertype enum")

            # Commit transaction
            trans.commit()
            logger.info("Enum update completed successfully")

        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    add_new_role_types()