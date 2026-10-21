"""Indices en columnas de fecha para el endpoint de proximos eventos

El endpoint GET /v2/portal/proximos-eventos corre en cada carga de la pantalla de
inicio y filtra por fecha (>= now) sobre tres tablas. Se agregan indices en las
columnas de fecha involucradas y en la FK programa_id de periodo_inscripcion_materia,
que se usa como join key y no tenia indice.

Revision ID: b7e2c9f14a30
Revises: 9a3f7c1e5b28
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e2c9f14a30'
down_revision: Union[str, None] = '9a3f7c1e5b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (indice, tabla, columna)
_INDICES = [
    ("ix_periodo_inscripcion_materia_programa_id", "periodo_inscripcion_materia", "programa_id"),
    ("ix_periodo_inscripcion_materia_fecha_inicio", "periodo_inscripcion_materia", "fecha_inicio"),
    ("ix_periodo_inscripcion_materia_fecha_fin", "periodo_inscripcion_materia", "fecha_fin"),
    ("ix_instancia_examen_fecha_inicio_inscripcion", "instancia_examen", "fecha_inicio_inscripcion"),
    ("ix_instancia_examen_fecha_fin_inscripcion", "instancia_examen", "fecha_fin_inscripcion"),
    ("ix_instancia_examen_fecha_examen", "instancia_examen", "fecha_examen"),
    ("ix_instancia_cursado_fecha_inicio", "instancia_cursado", "fecha_inicio"),
    ("ix_instancia_cursado_fecha_fin", "instancia_cursado", "fecha_fin"),
]


def _existing_indexes(table: str) -> set:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return {ix["name"] for ix in insp.get_indexes(table)}


def upgrade() -> None:
    for nombre, tabla, columna in _INDICES:
        # Idempotente: si el indice ya existe (p. ej. creado por create_all en dev),
        # no se recrea.
        if nombre not in _existing_indexes(tabla):
            op.create_index(nombre, tabla, [columna])


def downgrade() -> None:
    for nombre, tabla, _ in _INDICES:
        if nombre in _existing_indexes(tabla):
            op.drop_index(nombre, table_name=tabla)
