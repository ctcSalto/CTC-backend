from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from v2.models.usuario import Usuario
    from v2.models.inscripcion_programa import InscripcionPrograma
    from v2.models.inscripcion_materia import InscripcionMateria
    from v2.models.equipo import EquipoMiembro


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


# ── Modelo de tabla ──────────────────────────────────────────────────────────

class Alumno(SQLModel, table=True):
    __tablename__ = "alumno"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", unique=True, index=True)
    fecha_ingreso: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(get_uruguay_tz()),
        description="Fecha de ingreso como alumno"
    )
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    usuario: Optional["Usuario"] = Relationship(back_populates="perfil_alumno")
    inscripciones_programa: List["InscripcionPrograma"] = Relationship(back_populates="alumno")
    inscripciones: List["InscripcionMateria"] = Relationship(back_populates="alumno")
    equipos: List["EquipoMiembro"] = Relationship(back_populates="alumno")


# ── Schemas ──────────────────────────────────────────────────────────────────

class AlumnoCreate(SQLModel):
    usuario_id: int


class AlumnoRead(SQLModel):
    id: int
    usuario_id: int
    fecha_ingreso: Optional[datetime] = None
    id_rastreo: Optional[str] = None


class AlumnoUpdate(SQLModel):
    fecha_ingreso: Optional[datetime] = None
