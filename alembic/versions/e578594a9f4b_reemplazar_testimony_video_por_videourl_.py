"""reemplazar_testimony_video_por_videoUrl_en_testimony

Revision ID: e578594a9f4b
Revises: bad9dad1cc40
Create Date: 2026-07-05

- Agrega columna videoUrl (varchar 500, nullable) a la tabla testimony
- Elimina la tabla testimony_video (relacion 1-N reemplazada por campo directo)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'e578594a9f4b'
down_revision: Union[str, None] = 'bad9dad1cc40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('testimony', sa.Column('videoUrl', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True))
    op.drop_index('ix_testimony_video_testimonyId', table_name='testimony_video')
    op.drop_table('testimony_video')


def downgrade() -> None:
    op.create_table(
        'testimony_video',
        sa.Column('url', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('testimonyVideoId', sa.Integer(), nullable=False),
        sa.Column('testimonyId', sa.Integer(), nullable=False),
        sa.Column('creationDate', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['testimonyId'], ['testimony.testimonyId'],),
        sa.PrimaryKeyConstraint('testimonyVideoId'),
    )
    op.create_index('ix_testimony_video_testimonyId', 'testimony_video', ['testimonyId'], unique=False)
    op.drop_column('testimony', 'videoUrl')
