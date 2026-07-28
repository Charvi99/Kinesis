"""add ledger (paper accounts/positions/fills/snapshots)

Revision ID: c4a2b7d3e6f8
Revises: b3f1a9c2d4e5
Create Date: 2026-07-28 00:00:00.000000

Creates the paper-trading ledger tables. Live trading is OPT-IN: no account is seeded
here — `/api/v1/paper-trading/enable` creates a PaperAccount (bridged from the backtest)
when the user chooses to paper-trade an engine.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4a2b7d3e6f8'
down_revision: Union[str, Sequence[str], None] = 'b3f1a9c2d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('paper_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('engine_id', sa.Integer(), nullable=False),
        sa.Column('starting_cash', sa.DECIMAL(precision=16, scale=2), nullable=False),
        sa.Column('cash', sa.DECIMAL(precision=16, scale=2), nullable=False),
        sa.Column('is_live', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('go_live_at', sa.Date(), nullable=True),
        sa.Column('config_snapshot', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['engine_id'], ['engines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('engine_id', name='uq_paper_account_engine'),
    )
    op.create_index(op.f('ix_paper_accounts_id'), 'paper_accounts', ['id'], unique=False)
    op.create_index(op.f('ix_paper_accounts_engine_id'), 'paper_accounts', ['engine_id'], unique=True)

    op.create_table('paper_positions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.DECIMAL(precision=18, scale=6), nullable=False),
        sa.Column('avg_cost', sa.DECIMAL(precision=14, scale=4), nullable=True),
        sa.Column('opened_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['paper_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'stock_id', name='uq_paper_position_account_stock'),
    )
    op.create_index(op.f('ix_paper_positions_id'), 'paper_positions', ['id'], unique=False)
    op.create_index(op.f('ix_paper_positions_account_id'), 'paper_positions', ['account_id'], unique=False)
    op.create_index(op.f('ix_paper_positions_stock_id'), 'paper_positions', ['stock_id'], unique=False)

    op.create_table('paper_fills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('cycle_id', sa.Date(), nullable=False),
        sa.Column('side', sa.String(length=4), nullable=False),
        sa.Column('quantity', sa.DECIMAL(precision=18, scale=6), nullable=False),
        sa.Column('price', sa.DECIMAL(precision=14, scale=4), nullable=False),
        sa.Column('value', sa.DECIMAL(precision=16, scale=2), nullable=False),
        sa.Column('cost', sa.DECIMAL(precision=16, scale=2), nullable=False, server_default='0'),
        sa.Column('reason', sa.String(length=16), nullable=False, server_default='rebalance'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['paper_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'stock_id', 'cycle_id', name='uq_paper_fill_account_stock_cycle'),
    )
    op.create_index(op.f('ix_paper_fills_id'), 'paper_fills', ['id'], unique=False)
    op.create_index(op.f('ix_paper_fills_account_id'), 'paper_fills', ['account_id'], unique=False)
    op.create_index(op.f('ix_paper_fills_cycle_id'), 'paper_fills', ['cycle_id'], unique=False)

    op.create_table('paper_equity_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('cash', sa.DECIMAL(precision=16, scale=2), nullable=False),
        sa.Column('positions_value', sa.DECIMAL(precision=16, scale=2), nullable=False),
        sa.Column('equity', sa.DECIMAL(precision=16, scale=2), nullable=False),
        sa.Column('gross_exposure', sa.DECIMAL(precision=8, scale=4), nullable=True),
        sa.Column('realized_pnl_cumulative', sa.DECIMAL(precision=16, scale=2), nullable=False, server_default='0'),
        sa.Column('open_positions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_live', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['paper_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'date', name='uq_paper_equity_account_date'),
    )
    op.create_index(op.f('ix_paper_equity_snapshots_id'), 'paper_equity_snapshots', ['id'], unique=False)
    op.create_index(op.f('ix_paper_equity_snapshots_account_id'), 'paper_equity_snapshots', ['account_id'], unique=False)
    op.create_index(op.f('ix_paper_equity_snapshots_date'), 'paper_equity_snapshots', ['date'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_paper_equity_snapshots_date'), table_name='paper_equity_snapshots')
    op.drop_index(op.f('ix_paper_equity_snapshots_account_id'), table_name='paper_equity_snapshots')
    op.drop_index(op.f('ix_paper_equity_snapshots_id'), table_name='paper_equity_snapshots')
    op.drop_table('paper_equity_snapshots')
    op.drop_index(op.f('ix_paper_fills_cycle_id'), table_name='paper_fills')
    op.drop_index(op.f('ix_paper_fills_account_id'), table_name='paper_fills')
    op.drop_index(op.f('ix_paper_fills_id'), table_name='paper_fills')
    op.drop_table('paper_fills')
    op.drop_index(op.f('ix_paper_positions_stock_id'), table_name='paper_positions')
    op.drop_index(op.f('ix_paper_positions_account_id'), table_name='paper_positions')
    op.drop_index(op.f('ix_paper_positions_id'), table_name='paper_positions')
    op.drop_table('paper_positions')
    op.drop_index(op.f('ix_paper_accounts_engine_id'), table_name='paper_accounts')
    op.drop_index(op.f('ix_paper_accounts_id'), table_name='paper_accounts')
    op.drop_table('paper_accounts')
