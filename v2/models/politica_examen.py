from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from v2.models.materia import Materia


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class PoliticaExamen(SQLModel, table=True):
    __tablename__ = "politica_examen"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(max_length=100, description="Ej: 'Examen estándar base 100'")
    nota_maxima: Decimal = Field(max_digits=5, decimal_places=2, description="Nota máxima del examen")
    umbral_aprobacion: Decimal = Field(max_digits=5, decimal_places=2, description="Mínimo para aprobar el examen")
    activo: bool = Field(default=True)
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(get_uruguay_tz()))
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    materias: List["Materia"] = Relationship(back_populates="politica_examen_rel")


# ── Schemas ──────────────────────────────────────────────────────────────────

class PoliticaExamenCreate(SQLModel):
    nombre: str = Field(max_length=100)
    nota_maxima: Decimal = Field(max_digits=5, decimal_places=2)
    umbral_aprobacion: Decimal = Field(max_digits=5, decimal_places=2)


class PoliticaExamenUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, max_length=100)
    nota_maxima: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)
    umbral_aprobacion: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)
    activo: Optional[bool] = None


class PoliticaExamenRead(SQLModel):
    id: int
    nombre: str
    nota_maxima: Decimal
    umbral_aprobacion: Decimal
    activo: bool
    fecha_creacion: datetime
    id_rastreo: Optional[str] = None
