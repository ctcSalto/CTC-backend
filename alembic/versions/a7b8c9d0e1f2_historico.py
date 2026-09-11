"""historico de escolaridades

Revision ID: a7b8c9d0e1f2
Revises: f4a5b6c7d8e9
Create Date: 2026-09-11 18:00:00.000000

Tres tablas nuevas para el historico que bedelia llevaba en la planilla
"Escolaridades ver 2023.xlsm": historico_plan, historico_alumno e
historico_resultado. Son de solo lectura y no tienen FK hacia ninguna tabla
existente: los planes de ahi ya no existen en el portal y ninguno tiene una
politica de calificacion vigente. El vinculo con usuario es por cedula, en
consulta.

Los codigos (tipo_evaluacion, resultado, credito) son VARCHAR y no enum, a
proposito: son los codigos historicos de bedelia y no se van a extender.

Solo tablas nuevas. Sin impacto en datos existentes. Los datos se cargan
despues con v2/scripts/importar_historico.py.

Nota para el merge de la rama Handy: esta revision y a6b7c8d9e0f1 (pagos)
salen las dos de f4a5b6c7d8e9. Al juntarlas hace falta una revision de merge
(`alembic merge -m "merge historico y pagos" a7b8c9d0e1f2 a6b7c8d9e0f1`).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'a7b8c9d0e1f2'
down_revision = 'f4a5b6c7d8e9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'historico_plan',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=30), nullable=False),
        sa.Column('carrera', sa.String(length=150), nullable=True),
        sa.Column('creditos_requeridos', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_historico_plan_codigo', 'historico_plan', ['codigo'], unique=True)

    op.create_table(
        'historico_alumno',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cedula', sa.String(length=20), nullable=False),
        sa.Column('nombre', sa.String(length=150), nullable=False),
        sa.Column('nombre_busqueda', sa.String(length=150), nullable=False),
        sa.Column('plan_declarado', sa.String(length=30), nullable=True),
        sa.Column('zona', sa.String(length=20), nullable=True),
        sa.Column('direccion', sa.String(length=200), nullable=True),
        sa.Column('localidad', sa.String(length=100), nullable=True),
        sa.Column('departamento', sa.String(length=10), nullable=True),
        sa.Column('telefono', sa.String(length=100), nullable=True),
        sa.Column('celular', sa.String(length=100), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('observaciones', sa.String(length=500), nullable=True),
        sa.Column('fila_origen', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_historico_alumno_cedula', 'historico_alumno', ['cedula'], unique=True)
    op.create_index('ix_historico_alumno_nombre_busqueda', 'historico_alumno', ['nombre_busqueda'])

    op.create_table(
        'historico_resultado',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alumno_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('materia', sa.String(length=120), nullable=False),
        sa.Column('docente', sa.String(length=120), nullable=True),
        sa.Column('fecha', sa.Date(), nullable=True),
        sa.Column('fecha_texto', sa.String(length=20), nullable=True),
        sa.Column('tipo_evaluacion', sa.String(length=10), nullable=False),
        sa.Column('resultado', sa.String(length=10), nullable=True),
        sa.Column('puntaje', sa.Integer(), nullable=True),
        sa.Column('puntaje_promedio', sa.Integer(), nullable=True),
        sa.Column('credito', sa.String(length=1), nullable=True),
        sa.Column('acta', sa.String(length=20), nullable=True),
        sa.Column('proyecto', sa.Integer(), nullable=True),
        sa.Column('observaciones', sa.String(length=200), nullable=True),
        sa.Column('operador', sa.String(length=10), nullable=True),
        sa.Column('fila_origen', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['alumno_id'], ['historico_alumno.id'], name='fk_historico_resultado_alumno_id'),
        sa.ForeignKeyConstraint(['plan_id'], ['historico_plan.id'], name='fk_historico_resultado_plan_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_historico_resultado_alumno_id', 'historico_resultado', ['alumno_id'])
    op.create_index('ix_historico_resultado_plan_id', 'historico_resultado', ['plan_id'])
    op.create_index('ix_historico_resultado_materia', 'historico_resultado', ['materia'])
    op.create_index('ix_historico_resultado_fecha', 'historico_resultado', ['fecha'])


def downgrade() -> None:
    op.drop_index('ix_historico_resultado_fecha', table_name='historico_resultado')
    op.drop_index('ix_historico_resultado_materia', table_name='historico_resultado')
    op.drop_index('ix_historico_resultado_plan_id', table_name='historico_resultado')
    op.drop_index('ix_historico_resultado_alumno_id', table_name='historico_resultado')
    op.drop_table('historico_resultado')
    op.drop_index('ix_historico_alumno_nombre_busqueda', table_name='historico_alumno')
    op.drop_index('ix_historico_alumno_cedula', table_name='historico_alumno')
    op.drop_table('historico_alumno')
    op.drop_index('ix_historico_plan_codigo', table_name='historico_plan')
    op.drop_table('historico_plan')
