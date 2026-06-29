"""merge_heads_usuario_v2_y_notificaciones

Revision ID: 4fd4c9f395dd
Revises: a1b2c3d4e5f6, b2c3d4e5f6g7
Create Date: 2026-06-27 23:19:28.740634

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4fd4c9f395dd'
down_revision: Union[str, None] = ('a1b2c3d4e5f6', 'b2c3d4e5f6g7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
