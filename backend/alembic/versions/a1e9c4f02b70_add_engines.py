"""add engines

Revision ID: a1e9c4f02b70
Revises: 3bc9a791e1ad
Create Date: 2026-07-27 00:00:00.000000

Adds the `engines` table (named, persisted engine_3 configs — one is `is_deployed`)
and seeds the `prod` engine from the validated config (RESULTS.md). The backtester
stays kwargs-driven; an Engine row is mapped to those kwargs by
app/services/momentum/engines.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1e9c4f02b70'
down_revision: Union[str, Sequence[str], None] = '3bc9a791e1ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('engines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('lookback', sa.Integer(), nullable=False),
        sa.Column('top_n', sa.Integer(), nullable=False),
        sa.Column('target_vol', sa.Float(), nullable=False),
        sa.Column('max_weight', sa.Float(), nullable=False),
        sa.Column('regime_gate', sa.Boolean(), nullable=False),
        sa.Column('defended', sa.Boolean(), nullable=False),
        sa.Column('target_port_vol', sa.Float(), nullable=False),
        sa.Column('dd_threshold', sa.Float(), nullable=False),
        sa.Column('de_gross', sa.Float(), nullable=False),
        sa.Column('leverage_cap', sa.Float(), nullable=False),
        sa.Column('cost_bps', sa.Float(), nullable=False),
        sa.Column('starting_cash', sa.Float(), nullable=False),
        sa.Column('is_deployed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_engines_name'),
    )
    op.create_index(op.f('ix_engines_id'), 'engines', ['id'], unique=False)
    op.create_index(op.f('ix_engines_name'), 'engines', ['name'], unique=True)
    op.create_index('ix_engines_is_deployed', 'engines', ['is_deployed'], unique=False)

    # Seed the production engine. Literals frozen here (a migration is a snapshot);
    # they mirror app/services/momentum/defaults.py at the time of writing.
    engines_tbl = sa.table('engines',
        sa.column('name', sa.String), sa.column('description', sa.Text),
        sa.column('lookback', sa.Integer), sa.column('top_n', sa.Integer),
        sa.column('target_vol', sa.Float), sa.column('max_weight', sa.Float),
        sa.column('regime_gate', sa.Boolean), sa.column('defended', sa.Boolean),
        sa.column('target_port_vol', sa.Float), sa.column('dd_threshold', sa.Float),
        sa.column('de_gross', sa.Float), sa.column('leverage_cap', sa.Float),
        sa.column('cost_bps', sa.Float), sa.column('starting_cash', sa.Float),
        sa.column('is_deployed', sa.Boolean),
    )
    op.bulk_insert(engines_tbl, [{
        'name': 'prod',
        'description': 'engine_3 production config (validated — see RESULTS.md)',
        'lookback': 252, 'top_n': 10, 'target_vol': 0.10, 'max_weight': 0.10,
        'regime_gate': True, 'defended': True,
        'target_port_vol': 0.22, 'dd_threshold': 0.12, 'de_gross': 0.50,
        'leverage_cap': 1.0, 'cost_bps': 5.0, 'starting_cash': 100000.0,
        'is_deployed': True,
    }])


def downgrade() -> None:
    op.drop_index('ix_engines_is_deployed', table_name='engines')
    op.drop_index(op.f('ix_engines_name'), table_name='engines')
    op.drop_index(op.f('ix_engines_id'), table_name='engines')
    op.drop_table('engines')
