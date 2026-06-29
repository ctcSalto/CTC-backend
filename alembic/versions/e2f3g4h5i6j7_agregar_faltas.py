"""agregar_faltas

Revision ID: e2f3g4h5i6j7
Revises: d1a2b3c4d5e6
Create Date: 2026-05-01 12:00:00.000000

Agrega sistema de faltas:
- instancia_cursado.faltas_maximas (int nullable)
- inscripcion_materia.faltas (int default 0)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'e2f3g4h5i6j7'
down_revision = 'd1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Faltas máximas por instancia de cursado
    op.add_column('instancia_cursado', sa.Column('faltas_maximas', sa.Integer(), nullable=True))

    # Contador de faltas por inscripción
    op.add_column('inscripcion_materia', sa.Column('faltas', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('inscripcion_materia', 'faltas')
    op.drop_column('instancia_cursado', 'faltas_maximas')
