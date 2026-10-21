"""
Avance de un alumno en una carrera: qué aprobó, qué cursa, qué debe rendir y
qué le falta. Solo schemas de respuesta, sin tabla.

Ver v2/services/avance_service.py.
"""
from decimal import Decimal
from typing import List, Optional

from sqlmodel import SQLModel, Field


class AvanceMateriaItem(SQLModel):
    """Una materia del plan, con lo que corresponde a la lista en que aparece."""
    materia_id: int
    nombre: str
    codigo: Optional[str] = None
    semestre: int
    creditos: int
    inscripcion_id: Optional[int] = Field(default=None, description="La inscripcion que define el estado")
    estado: Optional[str] = Field(default=None, description="Estado de esa inscripcion; None si nunca la curso")
    anio_lectivo: Optional[int] = None
    nota_curso: Optional[Decimal] = None
    nota_final: Optional[Decimal] = None
    faltas: Optional[int] = Field(default=None, description="Solo en cursando")
    rendiciones_usadas: Optional[int] = Field(default=None, description="Solo en a_examen")
    max_oportunidades: Optional[int] = Field(default=None, description="Solo en a_examen")
    cumple_previaturas: Optional[bool] = Field(default=None, description="Solo en pendientes")
    previaturas_faltantes: List[str] = Field(default_factory=list, description="Solo en pendientes")
    programa: Optional[str] = Field(default=None, description="Solo en aprobadas_otros_planes")


class AvanceResumen(SQLModel):
    materias_totales: int
    aprobadas: int
    cursando: int
    a_examen: int
    pendientes: int
    creditos_obtenidos: int
    creditos_requeridos: int
    porcentaje_avance: float


class AvanceCarreraRead(SQLModel):
    """
    Las materias activas del plan, repartidas en cuatro listas sin repetir:
    cada materia aparece en una sola.
    """
    alumno_id: int
    programa_id: int
    programa_nombre: str
    resumen: AvanceResumen
    aprobadas: List[AvanceMateriaItem] = Field(
        default_factory=list, description="APROBADO, EXONERADO o REVALIDADA")
    cursando: List[AvanceMateriaItem] = Field(
        default_factory=list, description="CURSANDO ahora")
    a_examen: List[AvanceMateriaItem] = Field(
        default_factory=list, description="Curso aprobado, examen pendiente")
    pendientes: List[AvanceMateriaItem] = Field(
        default_factory=list, description="Nunca cursada, reprobada, abandonada o perdida por faltas")
    aprobadas_otros_planes: List[AvanceMateriaItem] = Field(
        default_factory=list,
        description="Cumplidas en otros planes de la misma carrera. No descuentan pendientes: "
                    "las equivalencias entre planes no estan definidas.")
