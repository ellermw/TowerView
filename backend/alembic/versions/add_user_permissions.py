"""Add user permissions table

Revision ID: add_user_permissions
Revises:
Create Date: 2025-09-25

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_user_permissions'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create user_permissions table
    op.create_table(
        'user_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('server_id', sa.Integer(), nullable=False),
        sa.Column('can_view_sessions', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_view_users', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_view_analytics', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_terminate_sessions', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_manage_server', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'server_id', name='unique_user_server_permission')
    )
    op.create_index('ix_user_permissions_id', 'user_permissions', ['id'])
    op.create_index('ix_user_permissions_user_id', 'user_permissions', ['user_id'])
    op.create_index('ix_user_permissions_server_id', 'user_permissions', ['server_id'])

    # Add new user type 'local_user' to the enum
    # Note: PostgreSQL requires special handling for enum updates
    op.execute("ALTER TYPE usertype ADD VALUE IF NOT EXISTS 'local_user'")


def downgrade():
    op.drop_index('ix_user_permissions_server_id', 'user_permissions')
    op.drop_index('ix_user_permissions_user_id', 'user_permissions')
    op.drop_index('ix_user_permissions_id', 'user_permissions')
    op.drop_table('user_permissions')
    # Note: Cannot easily remove enum value in PostgreSQL