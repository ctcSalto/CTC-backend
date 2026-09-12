"""pagos

Revision ID: a6b7c8d9e0f1
Revises: f4a5b6c7d8e9
Create Date: 2026-09-10 20:00:00.000000

Tablas `pago` y `pago_notificacion`: registro propio de los cobros.

POR QUE
-------
Handy respondio que no firma las notificaciones, que no reintenta si la entrega
falla y que no expone endpoint para consultar el estado de un pago. Sin registro
propio no hay contra que validar un aviso de "pago exitoso", y un aviso perdido
no deja ningun rastro: el pago queda cobrado del lado de Handy e invisible del
nuestro. Ver docs/HANDY_RESPUESTAS.md.

`pago.inscripcion_programa_id` implementa la decision de que el pago habilita la
inscripcion. Es nullable porque al crear el cobro la inscripcion todavia no
existe: se completa cuando el pago se acredita.

Las dos tablas son agnosticas del proveedor. MercadoPago no se toca ahora, pero
entra en la misma tabla el dia que se quiera, sin cambiar el esquema.

Dos tablas nuevas, ninguna columna sobre tablas existentes. Sin backfill y sin
impacto en datos existentes.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'a6b7c8d9e0f1'
down_revision = 'f4a5b6c7d8e9'
branch_labels = None
depends_on = None


# Los labels van en MAYUSCULA: es como SQLAlchemy nombra los miembros del Enum
# de Python y como quedaron el resto de los enums de v2 en la base.
#
# create_type=False es necesario: sin eso, create_table intenta crear el tipo por
# su cuenta ademas del .create() explicito de abajo, y la migracion se cae con
# "type proveedorpago already exists".
PROVEEDOR = postgresql.ENUM(
    'HANDY', 'MERCADOPAGO', name='proveedorpago', create_type=False
)
ESTADO = postgresql.ENUM(
    'INICIADO', 'PENDIENTE', 'PAGADO', 'FALLIDO', 'DEVUELTO',
    name='estadopago', create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    PROVEEDOR.create(bind, checkfirst=True)
    ESTADO.create(bind, checkfirst=True)

    op.create_table(
        'pago',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('referencia_externa', sa.String(length=36), nullable=False),
        sa.Column('proveedor', PROVEEDOR, nullable=False),
        sa.Column('proveedor_id', sa.String(length=100), nullable=True),
        sa.Column('estado', ESTADO, nullable=False, server_default='INICIADO'),
        sa.Column('estado_proveedor', sa.String(length=50), nullable=True),
        sa.Column('moneda', sa.Integer(), nullable=False),
        sa.Column('monto_total', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('monto_gravado', sa.Numeric(precision=12, scale=2),
                  nullable=False, server_default='0'),
        sa.Column('concepto', sa.String(length=255), nullable=False),
        sa.Column('programa_id', sa.Integer(), nullable=True),
        sa.Column('alumno_id', sa.Integer(), nullable=True),
        sa.Column('email_comprador', sa.String(length=255), nullable=True),
        sa.Column('inscripcion_programa_id', sa.Integer(), nullable=True),
        sa.Column('url_pago', sa.String(length=500), nullable=True),
        sa.Column('numero_factura', sa.Integer(), nullable=True),
        sa.Column('medio_pago', sa.String(length=100), nullable=True),
        sa.Column('fecha_creacion', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fecha_actualizacion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fecha_pago', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fecha_vencimiento', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id_rastreo', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['programa_id'], ['programa.id'],
                                name='fk_pago_programa_id'),
        sa.ForeignKeyConstraint(['alumno_id'], ['alumno.id'],
                                name='fk_pago_alumno_id'),
        sa.ForeignKeyConstraint(['inscripcion_programa_id'],
                                ['inscripcion_programa.id'],
                                name='fk_pago_inscripcion_programa_id'),
    )

    # Unico: es la clave de conciliacion y lo que sostiene la idempotencia del
    # webhook. Sin esta restriccion, un aviso repetido podria acreditar dos veces.
    op.create_index('ix_pago_referencia_externa', 'pago',
                    ['referencia_externa'], unique=True)
    op.create_index('ix_pago_id_rastreo', 'pago', ['id_rastreo'], unique=True)
    op.create_index('ix_pago_proveedor', 'pago', ['proveedor'])
    op.create_index('ix_pago_estado', 'pago', ['estado'])
    op.create_index('ix_pago_programa_id', 'pago', ['programa_id'])
    op.create_index('ix_pago_alumno_id', 'pago', ['alumno_id'])
    op.create_index('ix_pago_inscripcion_programa_id', 'pago',
                    ['inscripcion_programa_id'])
    op.create_index('ix_pago_fecha_creacion', 'pago', ['fecha_creacion'])

    # La consulta caliente del informe de pagos pendientes: cobros iniciados
    # que no se resolvieron pasado cierto tiempo. Es el unico mecanismo de
    # recuperacion ante un aviso perdido, asi que se corre seguido.
    op.create_index('ix_pago_pendientes', 'pago', ['estado', 'fecha_creacion'])

    op.create_table(
        'pago_notificacion',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pago_id', sa.Integer(), nullable=True),
        sa.Column('referencia_externa', sa.String(length=100), nullable=True),
        sa.Column('proveedor', PROVEEDOR, nullable=False),
        sa.Column('cuerpo', sa.JSON(), nullable=True),
        sa.Column('aceptada', sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column('motivo_rechazo', sa.String(length=255), nullable=True),
        sa.Column('ip_origen', sa.String(length=45), nullable=True),
        sa.Column('fecha_recepcion', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['pago_id'], ['pago.id'],
                                name='fk_pago_notificacion_pago_id'),
    )

    op.create_index('ix_pago_notificacion_pago_id', 'pago_notificacion', ['pago_id'])
    op.create_index('ix_pago_notificacion_referencia_externa',
                    'pago_notificacion', ['referencia_externa'])
    op.create_index('ix_pago_notificacion_proveedor', 'pago_notificacion',
                    ['proveedor'])
    op.create_index('ix_pago_notificacion_aceptada', 'pago_notificacion',
                    ['aceptada'])
    op.create_index('ix_pago_notificacion_fecha_recepcion', 'pago_notificacion',
                    ['fecha_recepcion'])


def downgrade() -> None:
    op.drop_index('ix_pago_notificacion_fecha_recepcion',
                  table_name='pago_notificacion')
    op.drop_index('ix_pago_notificacion_aceptada', table_name='pago_notificacion')
    op.drop_index('ix_pago_notificacion_proveedor', table_name='pago_notificacion')
    op.drop_index('ix_pago_notificacion_referencia_externa',
                  table_name='pago_notificacion')
    op.drop_index('ix_pago_notificacion_pago_id', table_name='pago_notificacion')
    op.drop_table('pago_notificacion')

    op.drop_index('ix_pago_pendientes', table_name='pago')
    op.drop_index('ix_pago_fecha_creacion', table_name='pago')
    op.drop_index('ix_pago_inscripcion_programa_id', table_name='pago')
    op.drop_index('ix_pago_alumno_id', table_name='pago')
    op.drop_index('ix_pago_programa_id', table_name='pago')
    op.drop_index('ix_pago_estado', table_name='pago')
    op.drop_index('ix_pago_proveedor', table_name='pago')
    op.drop_index('ix_pago_id_rastreo', table_name='pago')
    op.drop_index('ix_pago_referencia_externa', table_name='pago')
    op.drop_table('pago')

    bind = op.get_bind()
    ESTADO.drop(bind, checkfirst=True)
    PROVEEDOR.drop(bind, checkfirst=True)
