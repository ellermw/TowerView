"""
Migration script to update user roles from local_user to staff
Run this script to migrate existing local_user accounts to staff role
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

def migrate_user_roles():
    """Migrate existing local_user roles to staff"""

    # Create database connection
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            # Update all local_user roles to staff
            result = conn.execute(
                text("UPDATE users SET type = 'staff' WHERE type = 'local_user'")
            )

            rows_updated = result.rowcount
            logger.info(f"Migrated {rows_updated} users from 'local_user' to 'staff' role")

            # Commit transaction
            trans.commit()
            logger.info("Migration completed successfully")

        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate_user_roles()