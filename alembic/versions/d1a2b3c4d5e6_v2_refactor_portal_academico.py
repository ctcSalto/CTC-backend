"""v2_refactor_portal_academico

Revision ID: d1a2b3c4d5e6
Revises: c80c0cfd30d6
Create Date: 2026-04-29 12:00:00.000000

Refactor completo del portal académico v2:
- Tablas nuevas: alumno, profesor, administrativo_perfil, inscripcion_programa,
  instancia_cursado, instancia_examen, docente_instancia_examen
- Columnas nuevas en tablas existentes (id_rastreo, campos de usuario, etc.)
- Migración de FK: materia_id+anio_lectivo → instancia_cursado_id
- Eliminación de tabla periodo_examen
- Renombrado de FK: periodo_examen_id → instancia_examen_id en inscripcion_examen
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd1a2b3c4d5e6'
down_revision: Union[str, None] = 'c80c0cfd30d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Nuevas tablas ─────────────────────────────────────────────────────

    # Alumno
    op.create_table('alumno',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('fecha_ingreso', sa.DateTime(), nullable=True),
        sa.Column('id_rastreo', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('usuario_id'),
        sa.UniqueConstraint('id_rastreo'),
    )
    op.create_index('ix_alumno_usuario_id', 'alumno', ['usuario_id'])
    op.create_index('ix_alumno_id_rastreo', 'alumno', ['id_rastreo'])

    # Profesor
    op.create_table('profesor',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('cargo', sa.String(), nullable=True),
        sa.Column('dedicacion', sa.String(), nullable=True),
        sa.Column('especialidad', sa.String(length=200), nullable=True),
        sa.Column('id_rastreo', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('usuario_id'),
        sa.UniqueConstraint('id_rastreo'),
    )
    op.create_index('ix_profesor_usuario_id', 'profesor', ['usuario_id'])
    op.create_index('ix_profesor_id_rastreo', 'profesor', ['id_rastreo'])

    # Administrativo
    op.create_table('administrativo_perfil',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('departamento', sa.String(length=200), nullable=True),
        sa.Column('id_rastreo', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('usuario_id'),
        sa.UniqueConstraint('id_rastreo'),
    )
    op.create_index('ix_administrativo_perfil_usuario_id', 'administrativo_perfil', ['usuario_id'])
    op.create_index('ix_administrativo_perfil_id_rastreo', 'administrativo_perfil', ['id_rastreo'])

    # InscripcionPrograma
    op.create_table('inscripcion_programa',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alumno_id', sa.Integer(), nullable=False),
        sa.Column('programa_id', sa.Integer(), nullable=False),
        sa.Column('fecha_inscripcion', sa.DateTime(), nullable=False),
        sa.Column('estado', sa.String(), nullable=False),
        sa.Column('anio_ingreso', sa.Integer(), nullable=True),
        sa.Column('id_rastreo', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['alumno_id'], ['alumno.id']),
        sa.ForeignKeyConstraint(['programa_id'], ['programa.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id_rastreo'),
    )
    op.create_index('ix_inscripcion_programa_alumno_id', 'inscripcion_programa', ['alumno_id'])
    op.create_index('ix_inscripcion_programa_programa_id', 'inscripcion_programa', ['programa_id'])
    op.create_index('ix_inscripcion_programa_id_rastreo', 'inscripcion_programa', ['id_rastreo'])

    # InstanciaCursado
    op.create_table('instancia_cursado',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('materia_id', sa.Integer(), nullable=False),
        sa.Column('anio_lectivo', sa.Integer(), nullable=False),
        sa.Column('fecha_inicio', sa.DateTime(), nullable=True),
        sa.Column('fecha_fin', sa.DateTime(), nullable=True),
        sa.Column('salon', sa.String(length=100), nullable=True),
        sa.Column('horario', sa.String(length=200), nullable=True),
        sa.Column('cupo_maximo', sa.Integer(), nullable=True),
        sa.Column('estado', sa.String(), nullable=False),
        sa.Column('estadisticas', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('id_rastreo', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['materia_id'], ['materia.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id_rastreo'),
    )
    op.create_index('ix_instancia_cursado_materia_id', 'instancia_cursado', ['materia_id'])
    op.create_index('ix_instancia_cursado_id_rastreo', 'instancia_cursado', ['id_rastreo'])

    # InstanciaExamen
    op.create_table('instancia_examen',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('materia_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=150), nullable=False),
        sa.Column('fecha_inicio_inscripcion', sa.DateTime(), nullable=False),
        sa.Column('fecha_fin_inscripcion', sa.DateTime(), nullable=False),
        sa.Column('fecha_examen', sa.DateTime(), nullable=False),
        sa.Column('hora', sa.String(length=20), nullable=True),
        sa.Column('salon', sa.String(length=100), nullable=True),
        sa.Column('modalidad', sa.String(), nullable=False),
        sa.Column('tipo', sa.String(), nullable=False),
        sa.Column('estado', sa.String(), nullable=False),
        sa.Column('habilitado', sa.Boolean(), nullable=False),
        sa.Column('id_rastreo', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['materia_id'], ['materia.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id_rastreo'),
    )
    op.create_index('ix_instancia_examen_materia_id', 'instancia_examen', ['materia_id'])
    op.create_index('ix_instancia_examen_id_rastreo', 'instancia_examen', ['id_rastreo'])

    # DocenteInstanciaExamen
    op.create_table('docente_instancia_examen',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('docente_id', sa.Integer(), nullable=False),
        sa.Column('instancia_examen_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['docente_id'], ['usuario.id']),
        sa.ForeignKeyConstraint(['instancia_examen_id'], ['instancia_examen.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_docente_instancia_examen_docente_id', 'docente_instancia_examen', ['docente_id'])
    op.create_index('ix_docente_instancia_examen_instancia_examen_id', 'docente_instancia_examen', ['instancia_examen_id'])

    # ── 2. Columnas nuevas en tablas existentes ──────────────────────────────

    # Usuario: nuevos campos
    op.add_column('usuario', sa.Column('email_personal', sa.String(length=200), nullable=True))
    op.add_column('usuario', sa.Column('eliminado', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('usuario', sa.Column('fecha_eliminacion', sa.DateTime(), nullable=True))
    op.add_column('usuario', sa.Column('id_rastreo', sa.String(), nullable=True))
    op.create_index('ix_usuario_id_rastreo', 'usuario', ['id_rastreo'], unique=True)

    # Programa: nuevos campos
    op.add_column('programa', sa.Column('area', sa.String(), nullable=True))
    op.add_column('programa', sa.Column('coordinador_id', sa.Integer(), nullable=True))
    op.add_column('programa', sa.Column('profesor_externo_nombre', sa.String(length=200), nullable=True))
    op.add_column('programa', sa.Column('creditos_requeridos', sa.Integer(), nullable=True))
    op.add_column('programa', sa.Column('id_rastreo', sa.String(), nullable=True))
    op.create_foreign_key('fk_programa_coordinador', 'programa', 'profesor', ['coordinador_id'], ['id'])
    op.create_index('ix_programa_id_rastreo', 'programa', ['id_rastreo'], unique=True)

    # Materia: id_rastreo (ya debería tener si se creó en la migración anterior, pero agregar si no)
    # Si ya existe la columna, esta operación puede fallar — se maneja en el try

    # id_rastreo para modelos existentes
    for table_name in [
        'politica_calificacion', 'politica_examen', 'previatura',
        'calificacion', 'equipo', 'periodo_inscripcion_materia',
    ]:
        op.add_column(table_name, sa.Column('id_rastreo', sa.String(), nullable=True))
        op.create_index(f'ix_{table_name}_id_rastreo', table_name, ['id_rastreo'], unique=True)

    # ── 3. Migración de FK: materia_id+anio_lectivo → instancia_cursado_id ──

    # 3a. Crear instancias_cursado a partir de datos existentes
    # Para cada combinación única de (materia_id, anio_lectivo) en docente_materia,
    # inscripcion_materia, y materia_instancia_evaluacion, crear una instancia_cursado
    op.execute("""
        INSERT INTO instancia_cursado (materia_id, anio_lectivo, estado, id_rastreo)
        SELECT DISTINCT materia_id, anio_lectivo, 'FINALIZADA', gen_random_uuid()::text
        FROM (
            SELECT materia_id, anio_lectivo FROM docente_materia
            WHERE materia_id IS NOT NULL AND anio_lectivo IS NOT NULL
            UNION
            SELECT materia_id, anio_lectivo FROM inscripcion_materia
            WHERE materia_id IS NOT NULL AND anio_lectivo IS NOT NULL
            UNION
            SELECT materia_id, anio_lectivo FROM materia_instancia_evaluacion
            WHERE materia_id IS NOT NULL AND anio_lectivo IS NOT NULL
        ) AS combinaciones
    """)

    # 3b. Agregar columna instancia_cursado_id a las tablas afectadas
    for table_name in ['docente_materia', 'inscripcion_materia', 'materia_instancia_evaluacion']:
        op.add_column(table_name, sa.Column('instancia_cursado_id', sa.Integer(), nullable=True))
        op.create_index(f'ix_{table_name}_instancia_cursado_id', table_name, ['instancia_cursado_id'])

    # 3c. Poblar instancia_cursado_id desde materia_id + anio_lectivo
    for table_name in ['docente_materia', 'inscripcion_materia', 'materia_instancia_evaluacion']:
        op.execute(f"""
            UPDATE {table_name} t
            SET instancia_cursado_id = ic.id
            FROM instancia_cursado ic
            WHERE t.materia_id = ic.materia_id
              AND t.anio_lectivo = ic.anio_lectivo
              AND t.materia_id IS NOT NULL
              AND t.anio_lectivo IS NOT NULL
        """)

    # 3d. Agregar FK constraint
    for table_name in ['docente_materia', 'inscripcion_materia', 'materia_instancia_evaluacion']:
        op.create_foreign_key(
            f'fk_{table_name}_instancia_cursado',
            table_name, 'instancia_cursado',
            ['instancia_cursado_id'], ['id']
        )

    # 3e. Agregar id_rastreo a docente_materia e inscripcion_materia si no existe
    op.add_column('docente_materia', sa.Column('id_rastreo', sa.String(), nullable=True))
    op.create_index('ix_docente_materia_id_rastreo', 'docente_materia', ['id_rastreo'], unique=True)

    # inscripcion_materia: nota_final_directa + id_rastreo
    op.add_column('inscripcion_materia', sa.Column('nota_final_directa', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('inscripcion_materia', sa.Column('id_rastreo', sa.String(), nullable=True))
    op.create_index('ix_inscripcion_materia_id_rastreo', 'inscripcion_materia', ['id_rastreo'], unique=True)

    # materia_instancia_evaluacion: id_rastreo
    op.add_column('materia_instancia_evaluacion', sa.Column('id_rastreo', sa.String(), nullable=True))
    op.create_index('ix_materia_instancia_evaluacion_id_rastreo', 'materia_instancia_evaluacion', ['id_rastreo'], unique=True)

    # ── 4. Migración inscripcion_examen: periodo_examen_id → instancia_examen_id ─

    op.add_column('inscripcion_examen', sa.Column('instancia_examen_id', sa.Integer(), nullable=True))
    op.create_index('ix_inscripcion_examen_instancia_examen_id', 'inscripcion_examen', ['instancia_examen_id'])
    op.add_column('inscripcion_examen', sa.Column('notificacion_enviada', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('inscripcion_examen', sa.Column('id_rastreo', sa.String(), nullable=True))
    op.create_index('ix_inscripcion_examen_id_rastreo', 'inscripcion_examen', ['id_rastreo'], unique=True)

    # Nota: No se migran datos de periodo_examen → instancia_examen porque
    # son estructuras diferentes (periodo global vs instancia per-materia).
    # Las inscripciones existentes con periodo_examen_id quedarán sin instancia_examen_id.

    # 4b. Crear FK para instancia_examen_id
    op.create_foreign_key(
        'fk_inscripcion_examen_instancia_examen',
        'inscripcion_examen', 'instancia_examen',
        ['instancia_examen_id'], ['id']
    )

    # ── 5. Materia: id_rastreo (si no existe de migración anterior) ──────────
    # Se intenta agregar; si ya existe, el error se ignora con try/except
    try:
        op.add_column('materia', sa.Column('id_rastreo', sa.String(), nullable=True))
        op.create_index('ix_materia_id_rastreo', 'materia', ['id_rastreo'], unique=True)
    except Exception:
        pass  # Ya existe de la migración anterior

    # ── 6. DROP tabla periodo_examen ─────────────────────────────────────────
    # Nota: Las inscripciones existentes con periodo_examen_id quedarán como están.
    # Se debe limpiar la FK primero si existe.
    try:
        op.drop_constraint('inscripcion_examen_periodo_examen_id_fkey', 'inscripcion_examen', type_='foreignkey')
    except Exception:
        pass
    op.drop_table('periodo_examen')


def downgrade() -> None:
    """Downgrade — recrear periodo_examen y revertir cambios."""
    # Recrear periodo_examen
    op.create_table('periodo_examen',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nombre', sa.String(length=150), nullable=False),
        sa.Column('fecha_inicio_inscripcion', sa.DateTime(), nullable=False),
        sa.Column('fecha_fin_inscripcion', sa.DateTime(), nullable=False),
        sa.Column('habilitado', sa.Boolean(), nullable=False),
        sa.Column('fecha_creacion', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Revertir inscripcion_examen
    op.drop_constraint('fk_inscripcion_examen_instancia_examen', 'inscripcion_examen', type_='foreignkey')
    op.drop_index('ix_inscripcion_examen_id_rastreo', 'inscripcion_examen')
    op.drop_index('ix_inscripcion_examen_instancia_examen_id', 'inscripcion_examen')
    op.drop_column('inscripcion_examen', 'id_rastreo')
    op.drop_column('inscripcion_examen', 'notificacion_enviada')
    op.drop_column('inscripcion_examen', 'instancia_examen_id')

    # Revertir FK y columnas de migración
    for table_name in ['docente_materia', 'inscripcion_materia', 'materia_instancia_evaluacion']:
        try:
            op.drop_constraint(f'fk_{table_name}_instancia_cursado', table_name, type_='foreignkey')
        except Exception:
            pass
        op.drop_index(f'ix_{table_name}_instancia_cursado_id', table_name)
        op.drop_column(table_name, 'instancia_cursado_id')

    # Revertir id_rastreo de modelos existentes
    for table_name in [
        'politica_calificacion', 'politica_examen', 'previatura',
        'calificacion', 'equipo', 'periodo_inscripcion_materia',
        'docente_materia', 'inscripcion_materia', 'materia_instancia_evaluacion',
    ]:
        try:
            op.drop_index(f'ix_{table_name}_id_rastreo', table_name)
            op.drop_column(table_name, 'id_rastreo')
        except Exception:
            pass

    # Revertir inscripcion_materia extras
    op.drop_column('inscripcion_materia', 'nota_final_directa')

    # Revertir programa
    try:
        op.drop_constraint('fk_programa_coordinador', 'programa', type_='foreignkey')
    except Exception:
        pass
    op.drop_index('ix_programa_id_rastreo', 'programa')
    op.drop_column('programa', 'id_rastreo')
    op.drop_column('programa', 'creditos_requeridos')
    op.drop_column('programa', 'profesor_externo_nombre')
    op.drop_column('programa', 'coordinador_id')
    op.drop_column('programa', 'area')

    # Revertir usuario
    op.drop_index('ix_usuario_id_rastreo', 'usuario')
    op.drop_column('usuario', 'id_rastreo')
    op.drop_column('usuario', 'fecha_eliminacion')
    op.drop_column('usuario', 'eliminado')
    op.drop_column('usuario', 'email_personal')

    # Drop nuevas tablas
    op.drop_table('docente_instancia_examen')
    op.drop_table('instancia_examen')
    op.drop_table('instancia_cursado')
    op.drop_table('inscripcion_programa')
    op.drop_table('administrativo_perfil')
    op.drop_table('profesor')
    op.drop_table('alumno')
