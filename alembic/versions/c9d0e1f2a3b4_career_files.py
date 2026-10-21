"""career.files: archivos descargables de la oferta academica

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-08 12:00:00.000000

Pedido de direccion (08/10/2026): que el sitio publico ofrezca para descargar el
programa, el plan de estudios y otros archivos de cada carrera o curso.

Una columna JSON con la lista de URLs publicas. Las carreras que ya existen
quedan con la lista vacia ('[]'), asi que no hay que cargar nada para aplicarla.
Los archivos van a la VPS (ver database/services/career_files_service.py), no a
la base.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('career', sa.Column('files', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    op.drop_column('career', 'files')
