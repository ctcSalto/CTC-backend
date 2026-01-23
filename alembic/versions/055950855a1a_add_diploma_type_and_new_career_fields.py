"""add_diploma_type_and_new_career_fields

Revision ID: 055950855a1a
Revises: a736aaa18a0f
Create Date: 2025-11-19 22:58:36.048466

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '055950855a1a'
down_revision: Union[str, None] = 'a736aaa18a0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agregar el nuevo valor al enum PRIMERO (en minúsculas)
    op.execute("ALTER TYPE careertype ADD VALUE IF NOT EXISTS 'DIPLOMA'")
    
    # Luego agregar las columnas
    op.add_column('career', sa.Column('duration', sa.String(), nullable=True))
    op.add_column('career', sa.Column('hourlyLoad', sa.String(), nullable=True))
    op.add_column('career', sa.Column('cost', sa.String(), nullable=True))
    op.add_column('career', sa.Column('startClasses', sa.Date(), nullable=True))
    op.add_column('career', sa.Column('certificationType', sa.String(), nullable=True))


def downgrade() -> None:
    # Eliminar las columnas (el enum no se puede revertir fácilmente)
    op.drop_column('career', 'certificationType')
    op.drop_column('career', 'startClasses')
    op.drop_column('career', 'cost')
    op.drop_column('career', 'hourlyLoad')
    op.drop_column('career', 'duration')
    # Nota: No podemos eliminar 'DIPLOMA' del enum sin recrear el tipo completo
