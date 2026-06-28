"""agregar_tabla_testimony_video

Revision ID: bad9dad1cc40
Revises: 4fd4c9f395dd
Create Date: 2026-06-27 23:29:55.681275

Agrega la tabla testimony_video para soportar N videos por testimonio
(ej: ponentes/charlas), con URL libre (YouTube o Supabase, a definir) y
orden de reproduccion.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'bad9dad1cc40'
down_revision: Union[str, None] = '4fd4c9f395dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'testimony_video',
        sa.Column('url', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('testimonyVideoId', sa.Integer(), nullable=False),
        sa.Column('testimonyId', sa.Integer(), nullable=False),
        sa.Column('creationDate', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['testimonyId'], ['testimony.testimonyId'], ),
        sa.PrimaryKeyConstraint('testimonyVideoId'),
    )
    op.create_index(
        op.f('ix_testimony_video_testimonyId'), 'testimony_video', ['testimonyId'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_testimony_video_testimonyId'), table_name='testimony_video')
    op.drop_table('testimony_video')
