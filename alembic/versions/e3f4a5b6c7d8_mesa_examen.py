"""mesa_examen

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-08-06 10:00:00.000000

Tabla `mesa_examen`: la mesa a la que pertenece un conjunto de examenes.

No se reusa el nombre `periodo_examen` a proposito: esa tabla existio antes con
otro significado (la creo c80c0cfd30d6 y la borro d1a2b3c4d5e6 al reemplazarla
por instancia_examen), y en develop quedo una huerfana que el create_all de dev
resucito. Reusar el nombre haria ilegible la historia de migraciones.

Existe para que el tope de examenes por periodo sea un hecho declarado y no algo
inferido de la fecha. Con el mes calendario como periodo habia dos fallas: una
mesa que cruzaba fin de mes contaba doble, y dos mesas dentro de un mismo mes
contaban como una.

`instancia_examen.mesa_examen_id` es NULLABLE a proposito: los examenes ya
cargados no tienen mesa, y para esos el periodo sigue siendo el mes calendario.
Asi la migracion no necesita backfill ni cambia el comportamiento de lo que ya
existe.

Tabla nueva + una columna nullable. Sin impacto en datos existentes.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'e3f4a5b6c7d8'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mesa_examen',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('anio_lectivo', sa.Integer(), nullable=False),
        sa.Column('fecha_inicio_inscripcion', sa.DateTime(), nullable=False),
        sa.Column('fecha_fin_inscripcion', sa.DateTime(), nullable=False),
        sa.Column('max_examenes', sa.Integer(), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('id_rastreo', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mesa_examen_anio_lectivo', 'mesa_examen', ['anio_lectivo'])
    op.create_index('ix_mesa_examen_id_rastreo', 'mesa_examen', ['id_rastreo'], unique=True)

    op.add_column(
        'instancia_examen',
        sa.Column('mesa_examen_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_instancia_examen_mesa_examen_id',
        'instancia_examen', 'mesa_examen',
        ['mesa_examen_id'], ['id'],
    )
    op.create_index(
        'ix_instancia_examen_mesa_examen_id',
        'instancia_examen', ['mesa_examen_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_instancia_examen_mesa_examen_id', table_name='instancia_examen')
    op.drop_constraint(
        'fk_instancia_examen_mesa_examen_id', 'instancia_examen', type_='foreignkey'
    )
    op.drop_column('instancia_examen', 'mesa_examen_id')

    op.drop_index('ix_mesa_examen_id_rastreo', table_name='mesa_examen')
    op.drop_index('ix_mesa_examen_anio_lectivo', table_name='mesa_examen')
    op.drop_table('mesa_examen')
