"""career.certix: respaldo de CERTIX en la oferta academica

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-11-09 12:00:00.000000

CERTIX es la nueva division de certificados del instituto (09/11/2026). No es
un tipo de oferta (careerType sigue siendo carrera, curso, taller o diploma):
es un respaldo que algunas ofertas tienen y otras no. Un booleano; las ofertas
que ya existen quedan sin respaldo (false).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('career', sa.Column('certix', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('career', 'certix')
