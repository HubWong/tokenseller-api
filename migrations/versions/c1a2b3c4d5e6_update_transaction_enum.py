"""update transaction enum

Revision ID: c1a2b3c4d5e6
Revises: be6de204ff49
Create Date: 2026-04-26 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3c4d5e6'
down_revision: Union[str, None] = 'be6de204ff49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new values to the transactiontype enum
    op.execute("ALTER TYPE transactiontype ADD VALUE 'sysincome'")
    op.execute("ALTER TYPE transactiontype ADD VALUE 'refund'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL doesn't support removing values from enum types
    # To downgrade, you would need to:
    # 1. Create a new enum without the values
    # 2. Update all rows to use only valid values
    # 3. Alter the column to use the new enum
    # 4. Drop the old enum
    # For now, we'll skip the downgrade for enum removal
    pass
