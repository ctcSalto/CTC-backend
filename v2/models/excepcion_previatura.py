from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from v2.models.alumno import Alumno
    from v2.models.previatura import Previatura
    from v2.models.usuario import Usuario


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class ExcepcionPreviatura(SQLModel, table=True):
    """
    Permiso excepcional de bedelia para cursar una materia sin tener aprobada
    una previatura puntual.

    La excepcion habilita la INSCRIPCION, no convalida la materia adeudada. La
    aprobacion que el alumno consiga cursando bajo excepcion no habilita, a su
    vez, la materia siguiente mientras la previatura original siga sin aprobar:
    eso sale solo de la regla de cumplimiento pleno, sin marcar nada aca.
    """
    __tablename__ = "excepcion_previatura"

    id: Optional[int] = Field(default=None, primary_key=True)
    alumno_id: int = Field(foreign_key="alumno.id", index=True, description="Alumno beneficiado")
    previatura_id: int = Field(
        foreign_key="previatura.id", index=True,
        description="Previatura puntual que se exceptua (materia + materia previa)"
    )
    anio_lectivo: int = Field(
        index=True,
        description="Año lectivo para el que vale. No se traslada al siguiente"
    )
    motivo: str = Field(max_length=255, description="Por qué se otorga. Obligatorio")
    otorgada_por_id: int = Field(
        foreign_key="usuario.id",
        description="Administrativo que la otorgó"
    )
    fecha_otorgamiento: datetime = Field(default_factory=lambda: datetime.now(get_uruguay_tz()))

    revocada: bool = Field(default=False, description="Si fue dada de baja")
    fecha_revocacion: Optional[datetime] = Field(default=None)
    motivo_revocacion: Optional[str] = Field(default=None, max_length=255)
    revocada_por_id: Optional[int] = Field(default=None, foreign_key="usuario.id")

    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    alumno: Optional["Alumno"] = Relationship()
    previatura: Optional["Previatura"] = Relationship()


# ── Schemas ──────────────────────────────────────────────────────────────────

class ExcepcionPreviaturaCreate(SQLModel):
    alumno_id: int
    previatura_id: int
    anio_lectivo: int
    motivo: str = Field(min_length=1, max_length=255)


class ExcepcionPreviaturaRevocar(SQLModel):
    motivo: str = Field(min_length=1, max_length=255)


class ExcepcionPreviaturaRead(SQLModel):
    id: int
    alumno_id: int
    previatura_id: int
    anio_lectivo: int
    motivo: str
    otorgada_por_id: int
    fecha_otorgamiento: datetime
    revocada: bool
    fecha_revocacion: Optional[datetime] = None
    motivo_revocacion: Optional[str] = None
    revocada_por_id: Optional[int] = None
    id_rastreo: Optional[str] = None


class ExcepcionPreviaturaDetalle(ExcepcionPreviaturaRead):
    """Con los nombres resueltos, para las pantallas de bedelia."""
    materia_id: Optional[int] = None
    materia_nombre: Optional[str] = None
    materia_previa_id: Optional[int] = None
    materia_previa_nombre: Optional[str] = None
    vigente: bool = False
