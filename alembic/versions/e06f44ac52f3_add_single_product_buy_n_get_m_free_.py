"""Add single_product_buy_n_get_m_free promotion type

Revision ID: e06f44ac52f3
Revises: a446ac974531
Create Date: 2025-06-18 11:55:09.970243

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e06f44ac52f3'
down_revision: Union[str, None] = 'a446ac974531'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('promotion', 'action_type',
                    existing_type=sa.Enum('FIXED', 'PERCENTAGE', name='promotionactiontype'),
                    type_=sa.Enum('FIXED', 'PERCENTAGE', 'SINGLE_PRODUCT_BUY_N_GET_M_FREE', name='promotionactiontype'),
                    existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('promotion', 'action_type',
                    existing_type=sa.Enum('FIXED', 'PERCENTAGE', 'SINGLE_PRODUCT_BUY_N_GET_M_FREE',
                                          name='promotionactiontype'),
                    type_=sa.Enum('FIXED', 'PERCENTAGE', name='promotionactiontype'),
                    existing_nullable=False)
