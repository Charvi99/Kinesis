"""add engine.metrics

Revision ID: b3f1a9c2d4e5
Revises: a1e9c4f02b70
Create Date: 2026-07-27 02:00:00.000000

Adds a nullable JSON `metrics` column to `engines` for cached Sharpe/DD/etc.
Existing rows stay NULL and are backfilled lazily on first read (services/
momentum/engines.py::metrics_for_engine) — no fragile in-migration backtest.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b3f1a9c2d4e5'
down_revision: Union[str, Sequence[str], None] = 'a1e9c4f02b70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('engines', sa.Column('metrics', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('engines', 'metrics')
