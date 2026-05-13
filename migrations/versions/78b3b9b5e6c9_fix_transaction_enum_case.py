"""fix_transaction_enum_case

Revision ID: 78b3b9b5e6c9
Revises: c1a2b3c4d5e6
Create Date: 2026-04-26 13:22:07.295124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78b3b9b5e6c9'
down_revision: Union[str, None] = 'c1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # First convert column to VARCHAR to allow any value
    op.execute("ALTER TABLE transactions ALTER COLUMN type TYPE VARCHAR(50)")
    
    # Update existing data to use lowercase enum values
    op.execute("UPDATE transactions SET type = 'consume' WHERE type = 'CONSUME'")
    op.execute("UPDATE transactions SET type = 'recharge' WHERE type = 'RECHARGE'")
    op.execute("UPDATE transactions SET type = 'commission' WHERE type = 'COMMISSION'")
    
    # Drop the old enum type
    op.execute("DROP TYPE transactiontype")
    
    # Create new enum type with all lowercase values
    op.execute("CREATE TYPE transactiontype AS ENUM ('consume', 'recharge', 'commission', 'sysincome', 'refund')")
    
    # Alter column back to enum type
    op.execute("ALTER TABLE transactions ALTER COLUMN type TYPE transactiontype USING type::transactiontype")


def downgrade() -> None:
    """Downgrade schema."""
    # Update existing data to use uppercase enum values
    op.execute("UPDATE transactions SET type = 'CONSUME' WHERE type = 'consume'")
    op.execute("UPDATE transactions SET type = 'RECHARGE' WHERE type = 'recharge'")
    op.execute("UPDATE transactions SET type = 'COMMISSION' WHERE type = 'commission'")
    op.execute("UPDATE transactions SET type = 'SYSINCOME' WHERE type = 'sysincome'")
    op.execute("UPDATE transactions SET type = 'REFUND' WHERE type = 'refund'")
    
    # Drop the lowercase enum type
    op.execute("ALTER TABLE transactions ALTER COLUMN type TYPE VARCHAR(50)")
    op.execute("DROP TYPE transactiontype")
    
    # Create old enum type with uppercase values
    op.execute("CREATE TYPE transactiontype AS ENUM ('CONSUME', 'RECHARGE', 'COMMISSION')")
    
    # Alter column back to enum type
    op.execute("ALTER TABLE transactions ALTER COLUMN type TYPE transactiontype USING type::transactiontype")
