"""careertype: agrega CERTIX

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-11-12 12:00:00.000000

CERTIX como tipo de oferta (pedido del 12/11/2026), ademas del campo booleano
career.certix (d0e1f2a3b4c5), que se mantiene: el tipo dice que la oferta ES de
CERTIX; el campo, que una oferta de cualquier tipo tiene su respaldo.

Mismo patron que DIPLOMA (055950855a1a). Postgres no permite quitar valores de
un enum, asi que el downgrade no hace nada.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD VALUE no puede correr dentro de una transaccion en Postgres viejos
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE careertype ADD VALUE IF NOT EXISTS 'CERTIX'")


def downgrade() -> None:
    pass
