"""Add watermark ui settings

Revision ID: 653c8fa81322
Revises: add_secondary_embedding
Create Date: 2026-09-11 08:05:35.605212

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '653c8fa81322'
down_revision: Union[str, None] = 'add_secondary_embedding'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('photographers', sa.Column('watermark_scale', sa.Float(), nullable=True, server_default='0.2'))
    op.add_column('photographers', sa.Column('watermark_x', sa.Float(), nullable=True, server_default='0.98'))
    op.add_column('photographers', sa.Column('watermark_y', sa.Float(), nullable=True, server_default='0.98'))
    op.add_column('photographers', sa.Column('watermark_opacity', sa.Float(), nullable=True, server_default='0.7'))


def downgrade() -> None:
    op.drop_column('photographers', 'watermark_opacity')
    op.drop_column('photographers', 'watermark_y')
    op.drop_column('photographers', 'watermark_x')
    op.drop_column('photographers', 'watermark_scale')
