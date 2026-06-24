from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

from v2.models.enums import EstadoInscripcionExamen

if TYPE_CHECKING:
    from v2.models.inscripcion_materia import InscripcionMateria
    from v2.models.instancia_examen import InstanciaExamen


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class InscripcionExamen(SQLModel, table=True):
    __tablename__ = "inscripcion_examen"

    id: Optional[int] = Field(default=None, primary_key=True)
    inscripcion_materia_id: int = Field(foreign_key="inscripcion_materia.id", index=True, description="Inscripción a la materia (debe estar en estado A_EXAMEN)")
    instancia_examen_id: int = Field(foreign_key="instancia_examen.id", index=True, description="Instancia de examen")
    fecha_inscripcion: datetime = Field(default_factory=lambda: datetime.now(get_uruguay_tz()))
    nota_examen: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="Nota del examen")
    estado: EstadoInscripcionExamen = Field(
        default=EstadoInscripcionExamen.INSCRIPTO,
        description="Estado de la inscripción al examen"
    )
    numero_rendicion: int = Field(default=1, description="Número de rendición (1ra, 2da, 3ra...)")
    snapshot_politica_examen: Optional[dict] = Field(default=None, sa_column=Column(JSON), description="Snapshot de política de examen vigente")
    notificacion_enviada: bool = Field(default=False, description="Si se envió notificación (WhatsApp futuro)")
    fecha_baja: Optional[datetime] = Field(default=None, description="Fecha de baja de la inscripción al examen")
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    inscripcion_materia: Optional["InscripcionMateria"] = Relationship(back_populates="inscripciones_examen")
    instancia_examen: Optional["InstanciaExamen"] = Relationship(back_populates="inscripciones")


# ── Schemas ──────────────────────────────────────────────────────────────────

class InscripcionExamenCreate(SQLModel):
    inscripcion_materia_id: int
    instancia_examen_id: int


class InscripcionExamenRead(SQLModel):
    id: int
    inscripcion_materia_id: int
    instancia_examen_id: int
    fecha_inscripcion: datetime
    nota_examen: Optional[Decimal] = None
    estado: EstadoInscripcionExamen
    snapshot_politica_examen: Optional[dict] = None
    numero_rendicion: int = 1
    notificacion_enviada: bool = False
    fecha_baja: Optional[datetime] = None
    id_rastreo: Optional[str] = None
    id_rastreo_notificacion: Optional[str] = None


class CalificarExamenRequest(SQLModel):
    nota_examen: Decimal = Field(max_digits=5, decimal_places=2)
