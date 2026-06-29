from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

from v2.models.enums import TipoNotificacion, CanalNotificacion, EstadoNotificacion


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


# ── Modelo de tabla ──────────────────────────────────────────────────────────

class NotificacionLog(SQLModel, table=True):
    """Log de todas las notificaciones enviadas (email, futuro WhatsApp)."""
    __tablename__ = "notificacion_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    tipo: TipoNotificacion = Field(description="Tipo de notificación")
    canal: CanalNotificacion = Field(
        default=CanalNotificacion.EMAIL,
        description="Canal de envío"
    )
    usuario_id: int = Field(foreign_key="usuario.id", index=True, description="Destinatario")
    email_destino: str = Field(max_length=255, description="Email al que se envió")
    asunto: str = Field(max_length=255, description="Asunto del email")
    referencia_id: Optional[int] = Field(
        default=None,
        description="ID de la entidad relacionada (inscripcion, examen, etc.)"
    )
    referencia_tipo: Optional[str] = Field(
        default=None, max_length=50,
        description="Tipo de entidad: inscripcion_materia, inscripcion_examen, etc."
    )
    estado: EstadoNotificacion = Field(
        default=EstadoNotificacion.ENVIADA,
        description="Resultado del envío"
    )
    error_detalle: Optional[str] = Field(
        default=None, max_length=500,
        description="Detalle del error si falló"
    )
    enviado_por_id: Optional[int] = Field(
        default=None, foreign_key="usuario.id",
        description="Admin que disparó la notificación (null si automática)"
    )
    fecha_envio: datetime = Field(
        default_factory=lambda: datetime.now(get_uruguay_tz()),
        description="Fecha y hora de envío"
    )
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )


# ── Schemas ──────────────────────────────────────────────────────────────────

class NotificacionLogRead(SQLModel):
    id: int
    tipo: TipoNotificacion
    canal: CanalNotificacion
    usuario_id: int
    email_destino: str
    asunto: str
    referencia_id: Optional[int] = None
    referencia_tipo: Optional[str] = None
    estado: EstadoNotificacion
    error_detalle: Optional[str] = None
    enviado_por_id: Optional[int] = None
    fecha_envio: datetime
    id_rastreo: Optional[str] = None
