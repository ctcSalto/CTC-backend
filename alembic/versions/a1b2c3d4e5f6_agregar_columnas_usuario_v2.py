"""agregar columnas faltantes tabla usuario v2

Revision ID: a1b2c3d4e5f6
Revises: 087c21eff7fd
Create Date: 2026-06-07 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '087c21eff7fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table, column):
    """Chequea si una columna ya existe en la tabla."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    """Agrega columnas faltantes a la tabla usuario (v2), saltea las que ya existen."""
    if not _column_exists('usuario', 'email_personal'):
        op.add_column('usuario', sa.Column('email_personal', sa.String(length=255), nullable=True))
    if not _column_exists('usuario', 'fecha_nacimiento'):
        op.add_column('usuario', sa.Column('fecha_nacimiento', sa.Date(), nullable=True))
    if not _column_exists('usuario', 'domicilio'):
        op.add_column('usuario', sa.Column('domicilio', sa.String(length=200), nullable=True))
    if not _column_exists('usuario', 'eliminado'):
        op.add_column('usuario', sa.Column('eliminado', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    if not _column_exists('usuario', 'fecha_eliminacion'):
        op.add_column('usuario', sa.Column('fecha_eliminacion', sa.DateTime(), nullable=True))
    if not _column_exists('usuario', 'id_rastreo'):
        op.add_column('usuario', sa.Column('id_rastreo', sa.String(), nullable=True))
        op.create_index(op.f('ix_usuario_id_rastreo'), 'usuario', ['id_rastreo'], unique=True)


def downgrade() -> None:
    """Remueve las columnas agregadas."""
    op.drop_index(op.f('ix_usuario_id_rastreo'), table_name='usuario')
    op.drop_column('usuario', 'id_rastreo')
    op.drop_column('usuario', 'fecha_eliminacion')
    op.drop_column('usuario', 'eliminado')
    op.drop_column('usuario', 'domicilio')
    op.drop_column('usuario', 'fecha_nacimiento')
    op.drop_column('usuario', 'email_personal')
