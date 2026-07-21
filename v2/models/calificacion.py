from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from v2.models.inscripcion_materia import InscripcionMateria
    from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
    from v2.models.equipo import Equipo
    from v2.models.usuario import Usuario


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class Calificacion(SQLModel, table=True):
    __tablename__ = "calificacion"

    id: Optional[int] = Field(default=None, primary_key=True)
    inscripcion_id: int = Field(foreign_key="inscripcion_materia.id", description="Inscripción del estudiante")
    instancia_evaluacion_id: int = Field(foreign_key="materia_instancia_evaluacion.id", description="Instancia evaluada")
    nota: Decimal = Field(max_digits=5, decimal_places=2, description="Nota obtenida (dentro del peso_maximo)")
    equipo_id: Optional[int] = Field(default=None, foreign_key="equipo.id", description="Equipo si es evaluación grupal")
    # Auditoría: apunta a usuario (no a profesor) porque bedelía —rol ADMINISTRATIVO,
    # sin fila en `profesor`— también carga notas.
    cargado_por_id: int = Field(foreign_key="usuario.id", description="Usuario que cargó la nota (docente o administrativo)")
    fecha: datetime = Field(default_factory=lambda: datetime.now(get_uruguay_tz()), description="Fecha de carga")
    observaciones: Optional[str] = Field(default=None, description="Comentarios del docente")
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    inscripcion: Optional["InscripcionMateria"] = Relationship(back_populates="calificaciones")
    instancia_evaluacion: Optional["MateriaInstanciaEvaluacion"] = Relationship(back_populates="calificaciones")
    equipo: Optional["Equipo"] = Relationship(back_populates="calificaciones")
    cargado_por: Optional["Usuario"] = Relationship(back_populates="calificaciones_cargadas")


# ── Schemas ──────────────────────────────────────────────────────────────────

class CalificacionCreate(SQLModel):
    inscripcion_id: int
    instancia_evaluacion_id: int
    nota: Decimal = Field(max_digits=5, decimal_places=2)
    equipo_id: Optional[int] = None
    observaciones: Optional[str] = None


class CalificacionUpdate(SQLModel):
    nota: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)
    observaciones: Optional[str] = None


class CalificacionRead(SQLModel):
    id: int
    inscripcion_id: int
    instancia_evaluacion_id: int
    nota: Decimal
    equipo_id: Optional[int] = None
    cargado_por_id: int
    fecha: datetime
    observaciones: Optional[str] = None
    id_rastreo: Optional[str] = None


class CalificacionBatchItem(SQLModel):
    """Para carga masiva de notas por instancia"""
    inscripcion_id: int
    nota: Decimal = Field(max_digits=5, decimal_places=2)
    equipo_id: Optional[int] = None
    observaciones: Optional[str] = None


class CalificacionBatchRequest(SQLModel):
    """Request para carga masiva de notas"""
    instancia_evaluacion_id: int
    calificaciones: list[CalificacionBatchItem]
