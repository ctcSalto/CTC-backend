from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from v2.models.programa import Programa
    from v2.models.politica_calificacion import PoliticaCalificacion
    from v2.models.politica_examen import PoliticaExamen
    from v2.models.previatura import Previatura
    from v2.models.instancia_cursado import InstanciaCursado
    from v2.models.instancia_examen import InstanciaExamen


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class Materia(SQLModel, table=True):
    __tablename__ = "materia"

    id: Optional[int] = Field(default=None, primary_key=True)
    programa_id: int = Field(foreign_key="programa.id", description="Programa al que pertenece")
    nombre: str = Field(max_length=150, description="Ej: 'Programación 1', 'Base de Datos'")
    codigo: Optional[str] = Field(default=None, unique=True, max_length=20, description="Código corto: 'PROG1', 'BD1'")
    moodle_course_id: Optional[int] = Field(default=None, description="ID curso Moodle sincronizado")
    semestre: int = Field(description="Semestre en el programa (1, 2, 3...)")
    creditos: int = Field(description="Créditos de la materia")
    politica_id: int = Field(foreign_key="politica_calificacion.id", description="Política de calificación")
    politica_examen_id: Optional[int] = Field(default=None, foreign_key="politica_examen.id", description="Política de examen (null si no tiene examen)")
    horas_semanales: Optional[int] = Field(default=None, description="Horas semanales de clase")
    horas_totales: Optional[int] = Field(default=None, description="Horas totales de la materia")
    activo: bool = Field(default=True)
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(get_uruguay_tz()))
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    programa: Optional["Programa"] = Relationship(back_populates="materias")
    politica: Optional["PoliticaCalificacion"] = Relationship(back_populates="materias")
    politica_examen_rel: Optional["PoliticaExamen"] = Relationship(back_populates="materias")
    previaturas: List["Previatura"] = Relationship(
        back_populates="materia",
        sa_relationship_kwargs={"foreign_keys": "[Previatura.materia_id]"}
    )
    es_previatura_de: List["Previatura"] = Relationship(
        back_populates="materia_previa",
        sa_relationship_kwargs={"foreign_keys": "[Previatura.materia_previa_id]"}
    )
    instancias_cursado: List["InstanciaCursado"] = Relationship(back_populates="materia")
    instancias_examen: List["InstanciaExamen"] = Relationship(back_populates="materia")


# ── Schemas ──────────────────────────────────────────────────────────────────

class MateriaCreate(SQLModel):
    programa_id: int
    nombre: str = Field(max_length=150)
    codigo: Optional[str] = Field(default=None, max_length=20)
    moodle_course_id: Optional[int] = None
    semestre: int
    creditos: int
    politica_id: int
    politica_examen_id: Optional[int] = None
    horas_semanales: Optional[int] = None
    horas_totales: Optional[int] = None


class MateriaUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, max_length=150)
    codigo: Optional[str] = Field(default=None, max_length=20)
    moodle_course_id: Optional[int] = None
    semestre: Optional[int] = None
    creditos: Optional[int] = None
    politica_id: Optional[int] = None
    politica_examen_id: Optional[int] = None
    horas_semanales: Optional[int] = None
    horas_totales: Optional[int] = None
    activo: Optional[bool] = None


class MateriaRead(SQLModel):
    id: int
    programa_id: int
    nombre: str
    codigo: Optional[str] = None
    moodle_course_id: Optional[int] = None
    semestre: int
    creditos: int
    politica_id: int
    politica_examen_id: Optional[int] = None
    horas_semanales: Optional[int] = None
    horas_totales: Optional[int] = None
    activo: bool
    fecha_creacion: datetime
    id_rastreo: Optional[str] = None


class MateriaSimple(SQLModel):
    """Para listas embebidas (ej: dentro de ProgramaConMaterias)"""
    id: int
    nombre: str
    codigo: Optional[str] = None
    semestre: int
    creditos: int
    activo: bool
