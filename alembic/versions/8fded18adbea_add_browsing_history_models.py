"""add browsing_history models

Revision ID: 8fded18adbea
Revises: fb350b058c2a
Create Date: 2025-06-23 12:19:39.373438

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8fded18adbea'
down_revision: Union[str, None] = 'fb350b058c2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('browsing_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('sku_id', sa.Integer(), nullable=False),
    sa.Column('browsed_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['sku_id'], ['skus.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_browsing_history_id'), 'browsing_history', ['id'], unique=False)
    op.create_index(op.f('ix_browsing_history_sku_id'), 'browsing_history', ['sku_id'], unique=False)
    op.create_index(op.f('ix_browsing_history_user_id'), 'browsing_history', ['user_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_browsing_history_user_id'), table_name='browsing_history')
    op.drop_index(op.f('ix_browsing_history_sku_id'), table_name='browsing_history')
    op.drop_index(op.f('ix_browsing_history_id'), table_name='browsing_history')
    op.drop_table('browsing_history')
    # ### end Alembic commands ###
