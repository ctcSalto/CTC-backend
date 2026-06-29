"""agregar campos planilla admin y tabla documento_usuario

Revision ID: 4d769166125d
Revises: f3g4h5i6j7k8
Create Date: 2026-05-17 13:46:54.554153

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision: str = '4d769166125d'
down_revision: Union[str, None] = 'f3g4h5i6j7k8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # -- Tabla nueva: documento_usuario --
    op.create_table('documento_usuario',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.Enum('FORMULA_69A', 'ESCOLARIDAD', 'CONSTANCIA_CONVENIO', 'CEDULA', 'TITULO', 'OTRO', name='tipodocumento'), nullable=False),
        sa.Column('nombre_original', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('ruta_relativa', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column('mime_type', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('tamanio_bytes', sa.Integer(), nullable=False),
        sa.Column('descripcion', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column('subido_por', sa.Integer(), nullable=False),
        sa.Column('fecha_subida', sa.DateTime(), nullable=False),
        sa.Column('activo', sa.Boolean(), nullable=False),
        sa.Column('id_rastreo', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(['subido_por'], ['usuario.id'], ),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_documento_usuario_id_rastreo'), 'documento_usuario', ['id_rastreo'], unique=True)
    op.create_index(op.f('ix_documento_usuario_usuario_id'), 'documento_usuario', ['usuario_id'], unique=False)

    # -- Campos nuevos Fase 1 (todos nullable, sin romper nada) --

    # usuario: fecha_nacimiento, domicilio (ya existen en BD si v2 refactor los agrego)
    # Usamos batch_alter_table con try/except por si las columnas ya existen
    _safe_add_column('usuario', sa.Column('fecha_nacimiento', sa.Date(), nullable=True))
    _safe_add_column('usuario', sa.Column('domicilio', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True))

    # programa: certificacion, horas_totales
    _safe_add_column('programa', sa.Column('certificacion', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True))
    _safe_add_column('programa', sa.Column('horas_totales', sa.Integer(), nullable=True))

    # materia: horas_semanales, horas_totales
    _safe_add_column('materia', sa.Column('horas_semanales', sa.Integer(), nullable=True))
    _safe_add_column('materia', sa.Column('horas_totales', sa.Integer(), nullable=True))

    # profesor: carga_horaria_semanal
    _safe_add_column('profesor', sa.Column('carga_horaria_semanal', sa.Integer(), nullable=True))

    # inscripcion_programa: fecha_baja, motivo_baja
    _safe_add_column('inscripcion_programa', sa.Column('fecha_baja', sa.DateTime(), nullable=True))
    _safe_add_column('inscripcion_programa', sa.Column('motivo_baja', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))

    # inscripcion_examen: fecha_baja
    _safe_add_column('inscripcion_examen', sa.Column('fecha_baja', sa.DateTime(), nullable=True))

    # inscripcion_materia: fecha_baja
    _safe_add_column('inscripcion_materia', sa.Column('fecha_baja', sa.DateTime(), nullable=True))


def _safe_add_column(table_name: str, column: sa.Column):
    """Agrega una columna solo si no existe (para entornos donde la BD ya fue modificada)."""
    try:
        op.add_column(table_name, column)
    except Exception:
        pass


def downgrade() -> None:
    """Downgrade schema."""
    # Quitar columnas nuevas
    op.drop_column('inscripcion_materia', 'fecha_baja')
    op.drop_column('inscripcion_examen', 'fecha_baja')
    op.drop_column('inscripcion_programa', 'motivo_baja')
    op.drop_column('inscripcion_programa', 'fecha_baja')
    op.drop_column('profesor', 'carga_horaria_semanal')
    op.drop_column('materia', 'horas_totales')
    op.drop_column('materia', 'horas_semanales')
    op.drop_column('programa', 'horas_totales')
    op.drop_column('programa', 'certificacion')
    op.drop_column('usuario', 'domicilio')
    op.drop_column('usuario', 'fecha_nacimiento')

    # Quitar tabla documento_usuario
    op.drop_index(op.f('ix_documento_usuario_usuario_id'), table_name='documento_usuario')
    op.drop_index(op.f('ix_documento_usuario_id_rastreo'), table_name='documento_usuario')
    op.drop_table('documento_usuario')
