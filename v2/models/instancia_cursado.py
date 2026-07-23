from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

from v2.models.enums import EstadoInstanciaCursado

if TYPE_CHECKING:
    from v2.models.materia import Materia
    from v2.models.docente_materia import DocenteMateria
    from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
    from v2.models.inscripcion_materia import InscripcionMateria


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


# ── Modelo de tabla ──────────────────────────────────────────────────────────

class InstanciaCursado(SQLModel, table=True):
    __tablename__ = "instancia_cursado"

    id: Optional[int] = Field(default=None, primary_key=True)
    materia_id: int = Field(foreign_key="materia.id", index=True, description="Materia base")
    anio_lectivo: int = Field(description="Año lectivo (2026, 2027...)")
    fecha_inicio: Optional[datetime] = Field(default=None, index=True, description="Fecha de inicio del cursado")
    fecha_fin: Optional[datetime] = Field(default=None, index=True, description="Fecha de fin del cursado")
    salon: Optional[str] = Field(default=None, max_length=100, description="Salón asignado")
    horario: Optional[str] = Field(default=None, max_length=200, description="Horario (ej: 'Lunes 18-21')")
    cupo_maximo: Optional[int] = Field(default=None, description="Cupo máximo de alumnos")
    faltas_maximas: Optional[int] = Field(default=None, description="Cantidad de faltas con la que se pierde el curso")
    estado: EstadoInstanciaCursado = Field(
        default=EstadoInstanciaCursado.PLANIFICADA,
        description="Estado de la instancia de cursado"
    )
    estadisticas: Optional[dict] = Field(
        default=None, sa_column=Column(JSON),
        description="Estadísticas calculadas (aprobados, reprobados, etc.)"
    )
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    materia: Optional["Materia"] = Relationship(back_populates="instancias_cursado")
    docentes: List["DocenteMateria"] = Relationship(back_populates="instancia_cursado")
    evaluaciones: List["MateriaInstanciaEvaluacion"] = Relationship(back_populates="instancia_cursado")
    inscripciones: List["InscripcionMateria"] = Relationship(back_populates="instancia_cursado")


# ── Schemas ──────────────────────────────────────────────────────────────────

class InstanciaCursadoCreate(SQLModel):
    materia_id: int
    anio_lectivo: int
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    salon: Optional[str] = None
    horario: Optional[str] = None
    cupo_maximo: Optional[int] = None
    faltas_maximas: Optional[int] = None
    estado: Optional[EstadoInstanciaCursado] = None


class InstanciaCursadoUpdate(SQLModel):
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    salon: Optional[str] = None
    horario: Optional[str] = None
    cupo_maximo: Optional[int] = None
    faltas_maximas: Optional[int] = None
    estado: Optional[EstadoInstanciaCursado] = None


class InstanciaCursadoRead(SQLModel):
    id: int
    materia_id: int
    anio_lectivo: int
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    salon: Optional[str] = None
    horario: Optional[str] = None
    cupo_maximo: Optional[int] = None
    faltas_maximas: Optional[int] = None
    estado: EstadoInstanciaCursado
    estadisticas: Optional[dict] = None
    id_rastreo: Optional[str] = None
