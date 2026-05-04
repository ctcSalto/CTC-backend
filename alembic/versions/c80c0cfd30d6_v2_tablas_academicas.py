"""v2_tablas_academicas

Revision ID: c80c0cfd30d6
Revises: 055950855a1a
Create Date: 2026-04-18 15:12:17.585832

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision: str = 'c80c0cfd30d6'
down_revision: Union[str, None] = '055950855a1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Crear tablas del portal academico v2."""
    # Tablas sin dependencias (base)
    op.create_table('periodo_examen',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('fecha_inicio_inscripcion', sa.DateTime(), nullable=False),
    sa.Column('fecha_fin_inscripcion', sa.DateTime(), nullable=False),
    sa.Column('fecha_consulta', sa.DateTime(), nullable=True),
    sa.Column('fecha_examen', sa.DateTime(), nullable=False),
    sa.Column('habilitado', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('politica_calificacion',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('descripcion', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('nota_maxima', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('tipo_nota', sa.Enum('NUMERICA', 'LETRA', 'ESCALA_CUSTOM', name='tiponota'), nullable=False),
    sa.Column('umbral_aprobacion', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('umbral_examen', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('umbral_exoneracion', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('fecha_creacion', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('politica_examen',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('nota_maxima', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('umbral_aprobacion', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('fecha_creacion', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('programa',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sqlmodel.sql.sqltypes.AutoString(length=150), nullable=False),
    sa.Column('tipo', sa.Enum('CARRERA', 'CURSO_CORTO', 'TALLER', 'DIPLOMA', name='tipoprograma'), nullable=False),
    sa.Column('moodle_category_id', sa.Integer(), nullable=True),
    sa.Column('duracion_semestres', sa.Integer(), nullable=True),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('fecha_creacion', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('usuario',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('google_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('moodle_id', sa.Integer(), nullable=True),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('nombre', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('apellido', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('documento', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
    sa.Column('telefono', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
    sa.Column('foto_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('ou_google', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
    sa.Column('rol', sa.Enum('ESTUDIANTE', 'DOCENTE', 'ADMINISTRATIVO', name='rolusuario'), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('google_activo', sa.Boolean(), nullable=False),
    sa.Column('moodle_activo', sa.Boolean(), nullable=False),
    sa.Column('fecha_creacion', sa.DateTime(), nullable=False),
    sa.Column('ultimo_acceso', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('moodle_id')
    )
    op.create_index(op.f('ix_usuario_email'), 'usuario', ['email'], unique=True)
    op.create_index(op.f('ix_usuario_google_id'), 'usuario', ['google_id'], unique=True)

    # Tablas con FK a tablas base
    op.create_table('materia',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('programa_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sqlmodel.sql.sqltypes.AutoString(length=150), nullable=False),
    sa.Column('codigo', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
    sa.Column('moodle_course_id', sa.Integer(), nullable=True),
    sa.Column('semestre', sa.Integer(), nullable=False),
    sa.Column('creditos', sa.Integer(), nullable=False),
    sa.Column('politica_id', sa.Integer(), nullable=False),
    sa.Column('politica_examen_id', sa.Integer(), nullable=True),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('fecha_creacion', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['politica_examen_id'], ['politica_examen.id'], ),
    sa.ForeignKeyConstraint(['politica_id'], ['politica_calificacion.id'], ),
    sa.ForeignKeyConstraint(['programa_id'], ['programa.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo')
    )
    op.create_table('periodo_inscripcion_materia',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('programa_id', sa.Integer(), nullable=False),
    sa.Column('anio_lectivo', sa.Integer(), nullable=False),
    sa.Column('semestre', sa.Integer(), nullable=True),
    sa.Column('fecha_inicio', sa.DateTime(), nullable=False),
    sa.Column('fecha_fin', sa.DateTime(), nullable=False),
    sa.Column('habilitado', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['programa_id'], ['programa.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Tablas con FK a materia y usuario
    op.create_table('docente_materia',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('docente_id', sa.Integer(), nullable=False),
    sa.Column('materia_id', sa.Integer(), nullable=False),
    sa.Column('anio_lectivo', sa.Integer(), nullable=False),
    sa.Column('rol_docente', sa.Enum('TITULAR', 'ADJUNTO', 'ASISTENTE', name='roldocente'), nullable=False),
    sa.ForeignKeyConstraint(['docente_id'], ['usuario.id'], ),
    sa.ForeignKeyConstraint(['materia_id'], ['materia.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('inscripcion_materia',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('materia_id', sa.Integer(), nullable=False),
    sa.Column('anio_lectivo', sa.Integer(), nullable=False),
    sa.Column('estado', sa.Enum('CURSANDO', 'EXONERADO', 'A_EXAMEN', 'APROBADO', 'REPROBADO', 'PERDIDO_INASISTENCIA', 'ABANDONO', name='estadoinscripcionmateria'), nullable=False),
    sa.Column('nota_curso', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('nota_final', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('creditos_obtenidos', sa.Integer(), nullable=False),
    sa.Column('snapshot_politica', sa.JSON(), nullable=True),
    sa.Column('snapshot_instancias', sa.JSON(), nullable=True),
    sa.Column('fecha_inscripcion', sa.DateTime(), nullable=False),
    sa.Column('fecha_cierre', sa.DateTime(), nullable=True),
    sa.Column('motivo_cierre', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.ForeignKeyConstraint(['materia_id'], ['materia.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('materia_instancia_evaluacion',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('materia_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('peso_maximo', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.Column('es_grupal', sa.Boolean(), nullable=False),
    sa.Column('anio_lectivo', sa.Integer(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['materia_id'], ['materia.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('previatura',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('materia_id', sa.Integer(), nullable=False),
    sa.Column('materia_previa_id', sa.Integer(), nullable=False),
    sa.Column('tipo_requerido', sa.Enum('APROBADA', 'EXONERADA', name='tipopreviatura'), nullable=False),
    sa.ForeignKeyConstraint(['materia_id'], ['materia.id'], ),
    sa.ForeignKeyConstraint(['materia_previa_id'], ['materia.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Tablas con FK a instancia_evaluacion
    op.create_table('equipo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('instancia_evaluacion_id', sa.Integer(), nullable=False),
    sa.Column('nombre', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.ForeignKeyConstraint(['instancia_evaluacion_id'], ['materia_instancia_evaluacion.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('inscripcion_examen',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('inscripcion_materia_id', sa.Integer(), nullable=False),
    sa.Column('periodo_examen_id', sa.Integer(), nullable=False),
    sa.Column('fecha_inscripcion', sa.DateTime(), nullable=False),
    sa.Column('nota_examen', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('estado', sa.Enum('INSCRIPTO', 'APROBADO', 'REPROBADO', 'AUSENTE', name='estadoinscripcionexamen'), nullable=False),
    sa.Column('snapshot_politica_examen', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['inscripcion_materia_id'], ['inscripcion_materia.id'], ),
    sa.ForeignKeyConstraint(['periodo_examen_id'], ['periodo_examen.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Tablas con FK a equipo e inscripcion
    op.create_table('calificacion',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('inscripcion_id', sa.Integer(), nullable=False),
    sa.Column('instancia_evaluacion_id', sa.Integer(), nullable=False),
    sa.Column('nota', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('equipo_id', sa.Integer(), nullable=True),
    sa.Column('docente_id', sa.Integer(), nullable=False),
    sa.Column('fecha', sa.DateTime(), nullable=False),
    sa.Column('observaciones', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.ForeignKeyConstraint(['docente_id'], ['usuario.id'], ),
    sa.ForeignKeyConstraint(['equipo_id'], ['equipo.id'], ),
    sa.ForeignKeyConstraint(['inscripcion_id'], ['inscripcion_materia.id'], ),
    sa.ForeignKeyConstraint(['instancia_evaluacion_id'], ['materia_instancia_evaluacion.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('equipo_miembro',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('equipo_id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['equipo_id'], ['equipo.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema - Eliminar tablas del portal academico v2."""
    # Orden inverso: primero tablas con FK dependientes
    op.drop_table('equipo_miembro')
    op.drop_table('calificacion')
    op.drop_table('inscripcion_examen')
    op.drop_table('equipo')
    op.drop_table('previatura')
    op.drop_table('materia_instancia_evaluacion')
    op.drop_table('inscripcion_materia')
    op.drop_table('docente_materia')
    op.drop_table('periodo_inscripcion_materia')
    op.drop_table('materia')
    op.drop_index(op.f('ix_usuario_google_id'), table_name='usuario')
    op.drop_index(op.f('ix_usuario_email'), table_name='usuario')
    op.drop_table('usuario')
    op.drop_table('programa')
    op.drop_table('politica_examen')
    op.drop_table('politica_calificacion')
    op.drop_table('periodo_examen')

    # Limpiar enums creados
    sa.Enum(name='rolusuario').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='tipoprograma').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='tiponota').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='estadoinscripcionmateria').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='estadoinscripcionexamen').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='tipopreviatura').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='roldocente').drop(op.get_bind(), checkfirst=True)
