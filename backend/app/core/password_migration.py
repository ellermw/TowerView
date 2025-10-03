"""
Password hash migration utility to fix incompatible bcrypt hashes
after container rebuilds or bcrypt version changes.
"""
import logging
from typing import List, Tuple
from sqlalchemy.orm import Session
from .security import pwd_context, get_password_hash
from ..models.user import User, UserType

logger = logging.getLogger(__name__)


def is_hash_compatible(password_hash: str) -> bool:
    """
    Check if a password hash is compatible with the current bcrypt configuration.
    Returns True if the hash can be verified, False otherwise.
    """
    if not password_hash:
        return False

    try:
        # Try to verify with a test password - if it doesn't raise an error,
        # the hash format is compatible (even if password is wrong)
        pwd_context.verify("test_password_that_wont_match", password_hash)
        return True
    except (ValueError, TypeError) as e:
        # Hash format is incompatible
        logger.warning(f"Incompatible hash format detected: {str(e)}")
        return False
    except Exception:
        # Other exceptions (like wrong password) mean the hash IS compatible
        return True


def get_users_with_incompatible_hashes(db: Session) -> List[Tuple[int, str, str]]:
    """
    Find all staff users (admin, staff, support) with incompatible password hashes.
    Returns list of (user_id, username, user_type) tuples.
    """
    incompatible_users = []

    staff_users = db.query(User).filter(
        User.type.in_([UserType.admin, UserType.staff, UserType.support, UserType.local_user]),
        User.password_hash.isnot(None)
    ).all()

    for user in staff_users:
        if not is_hash_compatible(user.password_hash):
            incompatible_users.append((user.id, user.username, user.type.value))
            logger.warning(f"User {user.username} has incompatible password hash")

    return incompatible_users


def reset_user_password(db: Session, user_id: int, new_password: str,
                        must_change: bool = True) -> bool:
    """
    Reset a user's password with a new compatible hash.

    Args:
        db: Database session
        user_id: User ID to reset
        new_password: New password (plaintext)
        must_change: Whether user must change password on next login

    Returns:
        True if successful, False otherwise
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User ID {user_id} not found")
            return False

        user.password_hash = get_password_hash(new_password)
        user.must_change_password = must_change
        db.commit()

        logger.info(f"Successfully reset password for user {user.username} (ID: {user_id})")
        return True
    except Exception as e:
        logger.error(f"Failed to reset password for user ID {user_id}: {e}")
        db.rollback()
        return False


def migrate_incompatible_hashes(db: Session, default_password: str = "admin") -> dict:
    """
    Automatically migrate all incompatible password hashes.
    Resets passwords to a default value for affected users.

    Args:
        db: Database session
        default_password: Default password to set for migrated users

    Returns:
        Dictionary with migration results
    """
    results = {
        "total_checked": 0,
        "incompatible_found": 0,
        "successfully_migrated": 0,
        "failed": 0,
        "migrated_users": []
    }

    # Get all staff users
    staff_users = db.query(User).filter(
        User.type.in_([UserType.admin, UserType.staff, UserType.support, UserType.local_user]),
        User.password_hash.isnot(None)
    ).all()

    results["total_checked"] = len(staff_users)

    for user in staff_users:
        if not is_hash_compatible(user.password_hash):
            results["incompatible_found"] += 1
            logger.warning(f"Migrating incompatible hash for user: {user.username}")

            # Reset to default password
            if reset_user_password(db, user.id, default_password, must_change=True):
                results["successfully_migrated"] += 1
                results["migrated_users"].append({
                    "id": user.id,
                    "username": user.username,
                    "type": user.type.value
                })
            else:
                results["failed"] += 1

    if results["incompatible_found"] > 0:
        logger.warning(
            f"Password migration complete: {results['successfully_migrated']} users migrated, "
            f"{results['failed']} failed. Default password: {default_password}"
        )

    return results


def startup_password_check(db: Session) -> None:
    """
    Run at application startup to detect and fix incompatible password hashes.
    This prevents login failures after container rebuilds.
    """
    logger.info("Running startup password hash compatibility check...")

    try:
        results = migrate_incompatible_hashes(db)

        if results["incompatible_found"] == 0:
            logger.info(f"✓ All {results['total_checked']} staff user password hashes are compatible")
        else:
            logger.warning(
                f"⚠ Password hash migration completed:\n"
                f"  - Total users checked: {results['total_checked']}\n"
                f"  - Incompatible hashes found: {results['incompatible_found']}\n"
                f"  - Successfully migrated: {results['successfully_migrated']}\n"
                f"  - Failed: {results['failed']}\n"
                f"  - Affected users: {', '.join([u['username'] for u in results['migrated_users']])}\n"
                f"  - Default password set to: 'admin' (must change on login)"
            )
    except Exception as e:
        logger.error(f"Error during startup password check: {e}")
