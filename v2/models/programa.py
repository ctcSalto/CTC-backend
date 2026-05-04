from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

import os
from zoneinfo import ZoneInfo

from uuid import uuid4
from v2.models.enums import TipoPrograma, AreaPrograma

if TYPE_CHECKING:
    from v2.models.materia import Materia
    from v2.models.periodo_inscripcion_materia import PeriodoInscripcionMateria
    from v2.models.profesor import Profesor
    from v2.models.inscripcion_programa import InscripcionPrograma


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class Programa(SQLModel, table=True):
    __tablename__ = "programa"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(max_length=150, description="Ej: 'Analista Programador', 'Marketing Digital'")
    tipo: TipoPrograma = Field(description="Tipo de programa educativo")
    moodle_category_id: Optional[int] = Field(default=None, description="ID categoría Moodle sincronizada")
    duracion_semestres: Optional[int] = Field(default=None, description="Duración en semestres (solo carreras)")
    area: Optional[AreaPrograma] = Field(default=None, description="Área/categoría del programa")
    coordinador_id: Optional[int] = Field(default=None, foreign_key="profesor.id", description="Profesor coordinador")
    profesor_externo_nombre: Optional[str] = Field(default=None, max_length=200, description="Nombre del profesor externo (si aplica)")
    creditos_requeridos: Optional[int] = Field(default=None, description="Créditos necesarios para egreso")
    activo: bool = Field(default=True)
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(get_uruguay_tz()))
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    materias: List["Materia"] = Relationship(back_populates="programa")
    periodos_inscripcion: List["PeriodoInscripcionMateria"] = Relationship(back_populates="programa")
    coordinador: Optional["Profesor"] = Relationship(back_populates="programas_coordinados")
    inscripciones_programa: List["InscripcionPrograma"] = Relationship(back_populates="programa")


# ── Schemas ──────────────────────────────────────────────────────────────────

class ProgramaCreate(SQLModel):
    nombre: str = Field(max_length=150)
    tipo: TipoPrograma
    moodle_category_id: Optional[int] = None
    duracion_semestres: Optional[int] = None
    area: Optional[AreaPrograma] = None
    coordinador_id: Optional[int] = None
    profesor_externo_nombre: Optional[str] = None
    creditos_requeridos: Optional[int] = None


class ProgramaUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, max_length=150)
    tipo: Optional[TipoPrograma] = None
    moodle_category_id: Optional[int] = None
    duracion_semestres: Optional[int] = None
    area: Optional[AreaPrograma] = None
    coordinador_id: Optional[int] = None
    profesor_externo_nombre: Optional[str] = None
    creditos_requeridos: Optional[int] = None
    activo: Optional[bool] = None


class ProgramaRead(SQLModel):
    id: int
    nombre: str
    tipo: TipoPrograma
    moodle_category_id: Optional[int] = None
    duracion_semestres: Optional[int] = None
    area: Optional[AreaPrograma] = None
    coordinador_id: Optional[int] = None
    profesor_externo_nombre: Optional[str] = None
    creditos_requeridos: Optional[int] = None
    activo: bool
    fecha_creacion: datetime
    id_rastreo: Optional[str] = None


class ProgramaConMaterias(ProgramaRead):
    """Programa con lista de materias (para vista detallada)"""
    materias: List["MateriaSimple"] = []


# Forward ref resuelta al final del módulo de materia
from v2.models.materia import MateriaSimple  # noqa: E402
ProgramaConMaterias.model_rebuild()
