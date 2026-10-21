"""Refactor: FKs academicas apuntan a alumno/profesor en vez de usuario

Cambia el sujeto academico de `usuario` a los perfiles `alumno` / `profesor`:

    inscripcion_materia.usuario_id       -> alumno_id      (FK alumno.id)
    equipo_miembro.usuario_id            -> alumno_id      (FK alumno.id)
    docente_materia.docente_id           -> profesor_id    (FK profesor.id)
    docente_instancia_examen.docente_id  -> profesor_id    (FK profesor.id)

Ademas:
    calificacion.docente_id -> cargado_por_id  (sigue apuntando a usuario.id;
        es auditoria, y bedelia —rol ADMINISTRATIVO, sin fila en profesor—
        tambien carga notas)
    usuario.email pasa a ser nullable (oyentes registrados por administracion
        que no tienen cuenta institucional)

El backfill crea los perfiles faltantes antes de resolver las FKs, de modo que
ninguna fila existente se pierde aunque haya usuarios sin perfil.

Revision ID: 9a3f7c1e5b28
Revises: e578594a9f4b
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9a3f7c1e5b28'
down_revision: Union[str, None] = 'e578594a9f4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    return bool(conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = :t AND column_name = :c
    """), {"t": table, "c": column}).scalar())


def _abort_si_quedan_nulos(tabla: str, columna: str, perfil: str) -> None:
    """
    Verificacion defensiva: si tras el backfill quedan filas sin resolver,
    cortamos la migracion antes de imponer NOT NULL. Preferimos fallar ruidoso
    con la cuenta exacta a dejar la tabla en un estado inconsistente.
    """
    conn = op.get_bind()
    huerfanos = conn.execute(
        sa.text(f'SELECT count(*) FROM {tabla} WHERE {columna} IS NULL')
    ).scalar()
    if huerfanos:
        raise RuntimeError(
            f"[{tabla}] {huerfanos} fila(s) no pudieron resolverse a un perfil "
            f"'{perfil}'. Revisar manualmente antes de reintentar la migracion."
        )


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. usuario.email pasa a nullable ─────────────────────────────────────
    # Un oyente registrado por administracion puede no tener email. El constraint
    # unique se mantiene: Postgres admite multiples NULL bajo un indice unico.
    op.alter_column('usuario', 'email', existing_type=sa.String(255), nullable=True)

    # ── 2. Crear perfiles faltantes ──────────────────────────────────────────
    # Antes de mover las FKs hay que garantizar que todo usuario referenciado
    # tenga su fila de perfil. Sin esto el backfill dejaria huerfanos.
    conn.execute(sa.text("""
        INSERT INTO alumno (usuario_id, id_rastreo)
        SELECT DISTINCT u.id, gen_random_uuid()::text
        FROM usuario u
        WHERE (
            u.id IN (SELECT usuario_id FROM inscripcion_materia)
            OR u.id IN (SELECT usuario_id FROM equipo_miembro)
        )
        AND NOT EXISTS (SELECT 1 FROM alumno a WHERE a.usuario_id = u.id)
    """))

    conn.execute(sa.text("""
        INSERT INTO profesor (usuario_id, id_rastreo)
        SELECT DISTINCT u.id, gen_random_uuid()::text
        FROM usuario u
        WHERE (
            u.id IN (SELECT docente_id FROM docente_materia)
            OR u.id IN (SELECT docente_id FROM docente_instancia_examen)
        )
        AND NOT EXISTS (SELECT 1 FROM profesor p WHERE p.usuario_id = u.id)
    """))

    # ── 3. inscripcion_materia.usuario_id -> alumno_id ───────────────────────
    op.add_column('inscripcion_materia', sa.Column('alumno_id', sa.Integer(), nullable=True))
    conn.execute(sa.text("""
        UPDATE inscripcion_materia im
        SET alumno_id = a.id
        FROM alumno a
        WHERE a.usuario_id = im.usuario_id
    """))
    _abort_si_quedan_nulos('inscripcion_materia', 'alumno_id', 'alumno')
    op.alter_column('inscripcion_materia', 'alumno_id', nullable=False)
    op.drop_column('inscripcion_materia', 'usuario_id')
    op.create_index('ix_inscripcion_materia_alumno_id', 'inscripcion_materia', ['alumno_id'])
    op.create_foreign_key(
        'fk_inscripcion_materia_alumno_id', 'inscripcion_materia', 'alumno',
        ['alumno_id'], ['id'],
    )

    # ── 4. equipo_miembro.usuario_id -> alumno_id ────────────────────────────
    op.add_column('equipo_miembro', sa.Column('alumno_id', sa.Integer(), nullable=True))
    conn.execute(sa.text("""
        UPDATE equipo_miembro em
        SET alumno_id = a.id
        FROM alumno a
        WHERE a.usuario_id = em.usuario_id
    """))
    _abort_si_quedan_nulos('equipo_miembro', 'alumno_id', 'alumno')
    op.alter_column('equipo_miembro', 'alumno_id', nullable=False)
    op.drop_column('equipo_miembro', 'usuario_id')
    op.create_foreign_key(
        'fk_equipo_miembro_alumno_id', 'equipo_miembro', 'alumno',
        ['alumno_id'], ['id'],
    )

    # ── 5. docente_materia.docente_id -> profesor_id ─────────────────────────
    op.add_column('docente_materia', sa.Column('profesor_id', sa.Integer(), nullable=True))
    conn.execute(sa.text("""
        UPDATE docente_materia dm
        SET profesor_id = p.id
        FROM profesor p
        WHERE p.usuario_id = dm.docente_id
    """))
    _abort_si_quedan_nulos('docente_materia', 'profesor_id', 'profesor')
    op.alter_column('docente_materia', 'profesor_id', nullable=False)
    op.drop_column('docente_materia', 'docente_id')
    op.create_index('ix_docente_materia_profesor_id', 'docente_materia', ['profesor_id'])
    op.create_foreign_key(
        'fk_docente_materia_profesor_id', 'docente_materia', 'profesor',
        ['profesor_id'], ['id'],
    )

    # ── 6. docente_instancia_examen.docente_id -> profesor_id ────────────────
    op.add_column('docente_instancia_examen', sa.Column('profesor_id', sa.Integer(), nullable=True))
    conn.execute(sa.text("""
        UPDATE docente_instancia_examen die
        SET profesor_id = p.id
        FROM profesor p
        WHERE p.usuario_id = die.docente_id
    """))
    _abort_si_quedan_nulos('docente_instancia_examen', 'profesor_id', 'profesor')
    op.alter_column('docente_instancia_examen', 'profesor_id', nullable=False)
    op.drop_column('docente_instancia_examen', 'docente_id')
    op.create_index('ix_docente_instancia_examen_profesor_id', 'docente_instancia_examen', ['profesor_id'])
    op.create_foreign_key(
        'fk_docente_instancia_examen_profesor_id', 'docente_instancia_examen', 'profesor',
        ['profesor_id'], ['id'],
    )

    # ── 7. calificacion.docente_id -> cargado_por_id ─────────────────────────
    # Solo rename: sigue apuntando a usuario.id. El nombre viejo mentia, porque
    # un administrativo tambien carga notas y no tiene fila en `profesor`.
    if _column_exists('calificacion', 'docente_id'):
        op.alter_column('calificacion', 'docente_id', new_column_name='cargado_por_id')


def downgrade() -> None:
    conn = op.get_bind()

    # 7. calificacion
    if _column_exists('calificacion', 'cargado_por_id'):
        op.alter_column('calificacion', 'cargado_por_id', new_column_name='docente_id')

    # 6. docente_instancia_examen
    op.add_column('docente_instancia_examen', sa.Column('docente_id', sa.Integer(), nullable=True))
    conn.execute(sa.text("""
        UPDATE docente_instancia_examen die
        SET docente_id = p.usuario_id
        FROM profesor p
        WHERE p.id = die.profesor_id
    """))
    op.alter_column('docente_instancia_examen', 'docente_id', nullable=False)
    op.drop_constraint('fk_docente_instancia_examen_profesor_id', 'docente_instancia_examen', type_='foreignkey')
    op.drop_index('ix_docente_instancia_examen_profesor_id', table_name='docente_instancia_examen')
    op.drop_column('docente_instancia_examen', 'profesor_id')
    op.create_foreign_key(
        'fk_docente_instancia_examen_docente_id', 'docente_instancia_examen', 'usuario',
        ['docente_id'], ['id'],
    )

    # 5. docente_materia
    op.add_column('docente_materia', sa.Column('docente_id', sa.Integer(), nullable=True))
    conn.execute(sa.text("""
        UPDATE docente_materia dm
        SET docente_id = p.usuario_id
        FROM profesor p
        WHERE p.id = dm.profesor_id
    """))
    op.alter_column('docente_materia', 'docente_id', nullable=False)
    op.drop_constraint('fk_docente_materia_profesor_id', 'docente_materia', type_='foreignkey')
    op.drop_index('ix_docente_materia_profesor_id', table_name='docente_materia')
    op.drop_column('docente_materia', 'profesor_id')
    op.create_foreign_key(
        'fk_docente_materia_docente_id', 'docente_materia', 'usuario',
        ['docente_id'], ['id'],
    )

    # 4. equipo_miembro
    op.add_column('equipo_miembro', sa.Column('usuario_id', sa.Integer(), nullable=True))
    conn.execute(sa.text("""
        UPDATE equipo_miembro em
        SET usuario_id = a.usuario_id
        FROM alumno a
        WHERE a.id = em.alumno_id
    """))
    op.alter_column('equipo_miembro', 'usuario_id', nullable=False)
    op.drop_constraint('fk_equipo_miembro_alumno_id', 'equipo_miembro', type_='foreignkey')
    op.drop_column('equipo_miembro', 'alumno_id')
    op.create_foreign_key(
        'fk_equipo_miembro_usuario_id', 'equipo_miembro', 'usuario',
        ['usuario_id'], ['id'],
    )

    # 3. inscripcion_materia
    op.add_column('inscripcion_materia', sa.Column('usuario_id', sa.Integer(), nullable=True))
    conn.execute(sa.text("""
        UPDATE inscripcion_materia im
        SET usuario_id = a.usuario_id
        FROM alumno a
        WHERE a.id = im.alumno_id
    """))
    op.alter_column('inscripcion_materia', 'usuario_id', nullable=False)
    op.drop_constraint('fk_inscripcion_materia_alumno_id', 'inscripcion_materia', type_='foreignkey')
    op.drop_index('ix_inscripcion_materia_alumno_id', table_name='inscripcion_materia')
    op.drop_column('inscripcion_materia', 'alumno_id')
    op.create_index('ix_inscripcion_materia_usuario_id', 'inscripcion_materia', ['usuario_id'])
    op.create_foreign_key(
        'fk_inscripcion_materia_usuario_id', 'inscripcion_materia', 'usuario',
        ['usuario_id'], ['id'],
    )

    # 1. usuario.email vuelve a NOT NULL. Si hay filas sin email (oyentes sin
    # cuenta creados despues del upgrade), no se puede revertir sin decidir que
    # hacer con esas personas: cortamos con un mensaje explicito.
    sin_email = conn.execute(
        sa.text('SELECT count(*) FROM usuario WHERE email IS NULL')
    ).scalar()
    if sin_email:
        raise RuntimeError(
            f"No se puede revertir: hay {sin_email} usuario(s) sin email. "
            "Asignarles un email o eliminarlos antes de hacer downgrade."
        )
    op.alter_column('usuario', 'email', existing_type=sa.String(255), nullable=False)
