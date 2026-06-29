from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

from v2.models.enums import TipoDocumento

if TYPE_CHECKING:
    from v2.models.usuario import Usuario


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


# ── Modelo de tabla ──────────────────────────────────────────────────────────

class DocumentoUsuario(SQLModel, table=True):
    __tablename__ = "documento_usuario"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True, description="Usuario dueño del documento")
    tipo: TipoDocumento = Field(description="Tipo de documento")
    nombre_original: str = Field(max_length=255, description="Nombre del archivo que subió el usuario")
    ruta_relativa: str = Field(max_length=500, description="Ruta relativa dentro de DOCUMENTOS_BASE_PATH")
    mime_type: str = Field(max_length=100, description="Tipo MIME del archivo")
    tamanio_bytes: int = Field(description="Tamaño del archivo en bytes")
    descripcion: Optional[str] = Field(default=None, max_length=500, description="Descripción libre")
    subido_por: int = Field(foreign_key="usuario.id", description="Usuario que subió el archivo (puede ser admin)")
    fecha_subida: datetime = Field(
        default_factory=lambda: datetime.now(get_uruguay_tz()),
        description="Fecha de subida"
    )
    activo: bool = Field(default=True, description="Soft delete")
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    usuario: Optional["Usuario"] = Relationship(
        back_populates="documentos",
        sa_relationship_kwargs={"foreign_keys": "[DocumentoUsuario.usuario_id]"}
    )


# ── Schemas ──────────────────────────────────────────────────────────────────

class DocumentoUsuarioCreate(SQLModel):
    tipo: TipoDocumento
    descripcion: Optional[str] = Field(default=None, max_length=500)


class DocumentoUsuarioRead(SQLModel):
    id: int
    usuario_id: int
    tipo: TipoDocumento
    nombre_original: str
    mime_type: str
    tamanio_bytes: int
    descripcion: Optional[str] = None
    subido_por: int
    fecha_subida: datetime
    activo: bool
    id_rastreo: Optional[str] = None
