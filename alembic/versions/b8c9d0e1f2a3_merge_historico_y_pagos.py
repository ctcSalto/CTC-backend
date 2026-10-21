"""merge historico y pagos

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2, a6b7c8d9e0f1
Create Date: 2026-09-11 21:13:25.675837

Revision de merge, sin cambios de esquema. Junta dos ramas que salieron de
f4a5b6c7d8e9 en paralelo:

  - a7b8c9d0e1f2  historico de escolaridades (rama develop)
  - a6b7c8d9e0f1  tablas de pagos (rama Handy)

Existe para que Alembic vuelva a tener un solo head despues de mergear Handy
en develop. `alembic upgrade head` desde cualquiera de las dos aplica la que le
falte y despues esta.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = ('a7b8c9d0e1f2', 'a6b7c8d9e0f1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
