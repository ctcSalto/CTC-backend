"""excepciones_de_previatura

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-08-02 10:00:00.000000

Tabla `excepcion_previatura`: permiso de bedelia para que un alumno curse una
materia sin tener aprobada una previatura puntual.

La excepcion habilita la INSCRIPCION y nada mas. Que la aprobacion conseguida
bajo excepcion no habilite la materia siguiente no se guarda: sale de la regla
de cumplimiento pleno, que exige que toda la cadena de previaturas este
cumplida. Por eso no hay ninguna columna en inscripcion_materia.

Alcance por anio lectivo: la excepcion vale solo para el anio en que se otorgo,
no se traslada al siguiente.

Tabla nueva, sin impacto en datos existentes.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'd2e3f4a5b6c7'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'excepcion_previatura',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alumno_id', sa.Integer(), nullable=False),
        sa.Column('previatura_id', sa.Integer(), nullable=False),
        sa.Column('anio_lectivo', sa.Integer(), nullable=False),
        sa.Column('motivo', sa.String(length=255), nullable=False),
        sa.Column('otorgada_por_id', sa.Integer(), nullable=False),
        sa.Column('fecha_otorgamiento', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revocada', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('fecha_revocacion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('motivo_revocacion', sa.String(length=255), nullable=True),
        sa.Column('revocada_por_id', sa.Integer(), nullable=True),
        sa.Column('id_rastreo', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['alumno_id'], ['alumno.id'], name='fk_excepcion_previatura_alumno_id'),
        sa.ForeignKeyConstraint(['previatura_id'], ['previatura.id'], name='fk_excepcion_previatura_previatura_id'),
        sa.ForeignKeyConstraint(['otorgada_por_id'], ['usuario.id'], name='fk_excepcion_previatura_otorgada_por_id'),
        sa.ForeignKeyConstraint(['revocada_por_id'], ['usuario.id'], name='fk_excepcion_previatura_revocada_por_id'),
    )
    op.create_index('ix_excepcion_previatura_alumno_id', 'excepcion_previatura', ['alumno_id'])
    op.create_index('ix_excepcion_previatura_previatura_id', 'excepcion_previatura', ['previatura_id'])
    op.create_index('ix_excepcion_previatura_anio_lectivo', 'excepcion_previatura', ['anio_lectivo'])
    op.create_index('ix_excepcion_previatura_id_rastreo', 'excepcion_previatura', ['id_rastreo'], unique=True)

    # La consulta caliente es "excepciones vigentes de este alumno en este anio",
    # que corre en cada carga de la pantalla de inscripcion.
    op.create_index(
        'ix_excepcion_previatura_vigentes',
        'excepcion_previatura',
        ['alumno_id', 'anio_lectivo', 'revocada'],
    )


def downgrade() -> None:
    op.drop_index('ix_excepcion_previatura_vigentes', table_name='excepcion_previatura')
    op.drop_index('ix_excepcion_previatura_id_rastreo', table_name='excepcion_previatura')
    op.drop_index('ix_excepcion_previatura_anio_lectivo', table_name='excepcion_previatura')
    op.drop_index('ix_excepcion_previatura_previatura_id', table_name='excepcion_previatura')
    op.drop_index('ix_excepcion_previatura_alumno_id', table_name='excepcion_previatura')
    op.drop_table('excepcion_previatura')
