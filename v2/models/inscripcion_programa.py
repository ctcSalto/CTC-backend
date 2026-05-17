from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

from v2.models.enums import EstadoInscripcionPrograma

if TYPE_CHECKING:
    from v2.models.alumno import Alumno
    from v2.models.programa import Programa


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


# ── Modelo de tabla ──────────────────────────────────────────────────────────

class InscripcionPrograma(SQLModel, table=True):
    __tablename__ = "inscripcion_programa"

    id: Optional[int] = Field(default=None, primary_key=True)
    alumno_id: int = Field(foreign_key="alumno.id", index=True)
    programa_id: int = Field(foreign_key="programa.id", index=True)
    fecha_inscripcion: datetime = Field(
        default_factory=lambda: datetime.now(get_uruguay_tz()),
        description="Fecha de inscripción al programa"
    )
    estado: EstadoInscripcionPrograma = Field(
        default=EstadoInscripcionPrograma.ACTIVA,
        description="Estado de la inscripción"
    )
    anio_ingreso: int = Field(description="Año de ingreso al programa")
    fecha_baja: Optional[datetime] = Field(default=None, description="Fecha de baja del programa")
    motivo_baja: Optional[str] = Field(default=None, max_length=255, description="Motivo de la baja")
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    alumno: Optional["Alumno"] = Relationship(back_populates="inscripciones_programa")
    programa: Optional["Programa"] = Relationship(back_populates="inscripciones_programa")


# ── Schemas ──────────────────────────────────────────────────────────────────

class InscripcionProgramaCreate(SQLModel):
    alumno_id: int
    programa_id: int
    anio_ingreso: int


class InscripcionProgramaRead(SQLModel):
    id: int
    alumno_id: int
    programa_id: int
    fecha_inscripcion: datetime
    estado: EstadoInscripcionPrograma
    anio_ingreso: int
    fecha_baja: Optional[datetime] = None
    motivo_baja: Optional[str] = None
    id_rastreo: Optional[str] = None


class InscripcionProgramaUpdate(SQLModel):
    estado: Optional[EstadoInscripcionPrograma] = None
    fecha_baja: Optional[datetime] = None
    motivo_baja: Optional[str] = Field(default=None, max_length=255)
