"""Add Proxmox integration table

Revision ID: add_proxmox_integration
Revises: add_media_user_visibility
Create Date: 2025-10-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_proxmox_integration'
down_revision = 'add_media_user_visibility'
branch_labels = None
depends_on = None


def upgrade():
    # Create proxmox_integrations table
    op.create_table(
        'proxmox_integrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False, server_default='Proxmox'),
        sa.Column('enabled', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('host', sa.String(length=500), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True, server_default='8006'),
        sa.Column('node', sa.String(length=255), nullable=True),
        sa.Column('api_token', sa.String(length=500), nullable=True),
        sa.Column('verify_ssl', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('container_mappings', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('cached_containers', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('containers_updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('proxmox_integrations')
