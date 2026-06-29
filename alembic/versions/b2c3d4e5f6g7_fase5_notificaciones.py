"""Fase5: tabla notificacion_log y campo notificacion en inscripcion_materia

Revision ID: b2c3d4e5f6g7
Revises: 087c21eff7fd
Create Date: 2026-06-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = '087c21eff7fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Verifica si una columna ya existe en la tabla (PostgreSQL)."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.fetchone() is not None


def _table_exists(table: str) -> bool:
    """Verifica si una tabla ya existe."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :table"
        ),
        {"table": table},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    # 1. Crear tabla notificacion_log
    if not _table_exists("notificacion_log"):
        op.create_table(
            "notificacion_log",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tipo", sa.String(50), nullable=False),
            sa.Column("canal", sa.String(20), nullable=False, server_default="email"),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=False),
            sa.Column("email_destino", sa.String(255), nullable=False),
            sa.Column("asunto", sa.String(255), nullable=False),
            sa.Column("referencia_id", sa.Integer(), nullable=True),
            sa.Column("referencia_tipo", sa.String(50), nullable=True),
            sa.Column("estado", sa.String(20), nullable=False, server_default="enviada"),
            sa.Column("error_detalle", sa.String(500), nullable=True),
            sa.Column("enviado_por_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
            sa.Column("fecha_envio", sa.DateTime(timezone=True), nullable=False,
                       server_default=sa.text("now()")),
            sa.Column("id_rastreo", sa.String(), nullable=True, unique=True),
        )
        op.create_index("ix_notificacion_log_usuario_id", "notificacion_log", ["usuario_id"])
        op.create_index("ix_notificacion_log_id_rastreo", "notificacion_log", ["id_rastreo"])
        op.create_index("ix_notificacion_log_tipo_fecha", "notificacion_log", ["tipo", "fecha_envio"])

    # 2. Agregar campo notificacion_calificacion_enviada a inscripcion_materia
    if not _column_exists("inscripcion_materia", "notificacion_calificacion_enviada"):
        op.add_column(
            "inscripcion_materia",
            sa.Column(
                "notificacion_calificacion_enviada",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    # Quitar campo de inscripcion_materia
    if _column_exists("inscripcion_materia", "notificacion_calificacion_enviada"):
        op.drop_column("inscripcion_materia", "notificacion_calificacion_enviada")

    # Eliminar tabla notificacion_log
    if _table_exists("notificacion_log"):
        op.drop_index("ix_notificacion_log_tipo_fecha", table_name="notificacion_log")
        op.drop_index("ix_notificacion_log_id_rastreo", table_name="notificacion_log")
        op.drop_index("ix_notificacion_log_usuario_id", table_name="notificacion_log")
        op.drop_table("notificacion_log")
