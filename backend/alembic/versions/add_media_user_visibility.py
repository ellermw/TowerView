"""Add media user visibility field to servers

Revision ID: add_media_user_visibility
Revises: 
Create Date: 2025-09-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_media_user_visibility'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add visible_to_media_users column to servers table
    op.add_column('servers', sa.Column('visible_to_media_users', sa.Boolean(), nullable=False, server_default='true'))


def downgrade():
    # Remove the column
    op.drop_column('servers', 'visible_to_media_users')
