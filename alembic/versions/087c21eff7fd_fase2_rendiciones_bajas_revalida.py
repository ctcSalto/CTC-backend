"""fase2 rendiciones bajas revalida

Revision ID: 087c21eff7fd
Revises: 4d769166125d
Create Date: 2026-05-17 18:46:26.415149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision: str = '087c21eff7fd'
down_revision: Union[str, None] = '4d769166125d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _safe_add_column(table_name: str, column: sa.Column):
    """Agrega una columna solo si no existe."""
    try:
        op.add_column(table_name, column)
    except Exception:
        pass


def upgrade() -> None:
    """Upgrade schema."""
    # politica_examen: max_oportunidades (default 5)
    _safe_add_column('politica_examen', sa.Column('max_oportunidades', sa.Integer(), nullable=False, server_default='5'))

    # inscripcion_examen: numero_rendicion (default 1)
    _safe_add_column('inscripcion_examen', sa.Column('numero_rendicion', sa.Integer(), nullable=False, server_default='1'))

    # inscripcion_materia: motivo_revalida
    _safe_add_column('inscripcion_materia', sa.Column('motivo_revalida', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('inscripcion_materia', 'motivo_revalida')
    op.drop_column('inscripcion_examen', 'numero_rendicion')
    op.drop_column('politica_examen', 'max_oportunidades')
