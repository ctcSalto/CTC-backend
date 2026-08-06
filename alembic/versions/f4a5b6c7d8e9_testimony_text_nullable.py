"""testimony_text_nullable

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-08-06 12:00:00.000000

Hace `testimony.text` nullable, para que coincida con lo que el modelo declara.

Un testimonio es texto O video, nunca los dos ni ninguno: lo exige el
`model_validator` de TestimonyCreate. Por lo tanto un testimonio de video tiene
`text = NULL`, y el modelo lo declara asi (`Optional[str]`, default None).

Pero la columna quedo NOT NULL: la migracion `e578594a9f4b`, que reemplazo la
tabla testimony_video por el campo `videoUrl`, nunca la relajo. Resultado: crear
un testimonio de solo video —omitiendo `text`, que es la forma que el validador
aprueba— falla con "null value in column text violates not-null constraint".

Verificado contra la base de develop antes de escribir esto.

Hoy no explota porque los clientes mandan `text: ""` en vez de omitirlo, y el
validador trata el string vacio como ausente. O sea que funciona por como pega el
cliente, no porque el esquema lo permita.

Las 28 filas existentes no se tocan: ninguna tiene text NULL, asi que relajar la
restriccion no las afecta. Los 12 testimonios de video tienen `text = ''` y
quedan como estan.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'f4a5b6c7d8e9'
down_revision = 'e3f4a5b6c7d8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'testimony', 'text',
        existing_type=sa.VARCHAR(length=350),
        nullable=True,
    )


def downgrade() -> None:
    # Volver a NOT NULL requiere que no haya nulos. Se normalizan a '' primero,
    # que es como venian guardandose los testimonios de video.
    op.execute("UPDATE testimony SET text = '' WHERE text IS NULL")
    op.alter_column(
        'testimony', 'text',
        existing_type=sa.VARCHAR(length=350),
        nullable=False,
    )
