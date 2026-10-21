from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

from v2.models.enums import TipoNota

if TYPE_CHECKING:
    from v2.models.materia import Materia


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class PoliticaCalificacion(SQLModel, table=True):
    __tablename__ = "politica_calificacion"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(max_length=100, description="Ej: 'Base 100 - Carrera AP', 'Base 12 - Futuro'")
    descripcion: Optional[str] = Field(default=None, description="Explicación de la política")
    nota_maxima: Decimal = Field(max_digits=5, decimal_places=2, description="100, 12, etc.")
    tipo_nota: TipoNota = Field(default=TipoNota.NUMERICA, description="Tipo de escala")
    umbral_aprobacion: Decimal = Field(
        max_digits=5, decimal_places=2,
        description="Mínimo para aprobar directo. Solo se usa cuando umbral_examen "
                    "es NULL (cursos cortos): si hay umbral_examen, el motor decide "
                    "entre A_EXAMEN y REPROBADO y este valor no interviene"
    )
    umbral_examen: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="Mínimo para derecho a examen (null si no aplica)")
    umbral_exoneracion: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="Mínimo para exonerar (null si no aplica)")
    activo: bool = Field(default=True)
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(get_uruguay_tz()))
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    materias: List["Materia"] = Relationship(back_populates="politica")


# ── Schemas ──────────────────────────────────────────────────────────────────

class PoliticaCalificacionCreate(SQLModel):
    nombre: str = Field(max_length=100)
    descripcion: Optional[str] = None
    nota_maxima: Decimal = Field(max_digits=5, decimal_places=2)
    tipo_nota: TipoNota = TipoNota.NUMERICA
    umbral_aprobacion: Decimal = Field(max_digits=5, decimal_places=2)
    umbral_examen: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)
    umbral_exoneracion: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)


class PoliticaCalificacionUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, max_length=100)
    descripcion: Optional[str] = None
    nota_maxima: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)
    tipo_nota: Optional[TipoNota] = None
    umbral_aprobacion: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)
    umbral_examen: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)
    umbral_exoneracion: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)
    activo: Optional[bool] = None


class PoliticaCalificacionRead(SQLModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    nota_maxima: Decimal
    tipo_nota: TipoNota
    umbral_aprobacion: Decimal
    umbral_examen: Optional[Decimal] = None
    umbral_exoneracion: Optional[Decimal] = None
    activo: bool
    fecha_creacion: datetime
    id_rastreo: Optional[str] = None
