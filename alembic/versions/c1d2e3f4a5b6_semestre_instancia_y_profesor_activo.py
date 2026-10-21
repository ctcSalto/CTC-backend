"""semestre_instancia_y_profesor_activo

Revision ID: c1d2e3f4a5b6
Revises: b7e2c9f14a30
Create Date: 2026-07-27 12:00:00.000000

- instancia_cursado.semestre (int nullable): semestre calendario en que se dicta
  esa instancia. Es distinto de materia.semestre, que es la posicion de la
  materia en el plan de estudios. Nullable porque las instancias ya existentes
  no tienen el dato y no se puede inferir; las consultas de disponibilidad
  tratan NULL como "se dicta en cualquier semestre" para no ocultar oferta
  vigente despues de migrar.

- profesor.activo (bool not null, default true): si el profesor dicta
  actualmente. Es distinto de usuario.activo, que controla el acceso al
  sistema: un profesor retirado puede quedar inactivo como docente y seguir
  entrando a ver su historico.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'c1d2e3f4a5b6'
down_revision = 'b7e2c9f14a30'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('instancia_cursado', sa.Column('semestre', sa.Integer(), nullable=True))
    op.add_column(
        'profesor',
        sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column('profesor', 'activo')
    op.drop_column('instancia_cursado', 'semestre')
