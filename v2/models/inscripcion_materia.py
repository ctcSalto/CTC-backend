from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON
from typing import Optional, List, Any, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

from v2.models.enums import EstadoInscripcionMateria

if TYPE_CHECKING:
    from v2.models.usuario import Usuario
    from v2.models.instancia_cursado import InstanciaCursado
    from v2.models.calificacion import Calificacion
    from v2.models.inscripcion_examen import InscripcionExamen


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class InscripcionMateria(SQLModel, table=True):
    __tablename__ = "inscripcion_materia"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True, description="Estudiante inscripto")
    instancia_cursado_id: int = Field(foreign_key="instancia_cursado.id", index=True, description="Instancia de cursado")
    estado: EstadoInscripcionMateria = Field(
        default=EstadoInscripcionMateria.CURSANDO,
        description="Estado actual de la inscripción"
    )
    nota_curso: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="Suma de notas de instancias")
    nota_final: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="Nota final (puede ser nota examen)")
    nota_final_directa: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="Nota final cargada directamente por profesor")
    creditos_obtenidos: int = Field(default=0, description="Créditos si aprobó, 0 si no")
    faltas: int = Field(default=0, description="Cantidad de faltas acumuladas")

    # Snapshots JSONB - preservan las reglas históricas al momento de inscripción
    snapshot_politica: Optional[dict] = Field(default=None, sa_column=Column(JSON), description="Snapshot de la política de calificación vigente")
    snapshot_instancias: Optional[list] = Field(default=None, sa_column=Column(JSON), description="Snapshot de las instancias de evaluación vigentes")

    fecha_inscripcion: datetime = Field(default_factory=lambda: datetime.now(get_uruguay_tz()))
    fecha_cierre: Optional[datetime] = Field(default=None, description="Fecha en que se determinó el estado final")
    motivo_cierre: Optional[str] = Field(default=None, max_length=255, description="Motivo de inasistencia/abandono")
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    usuario: Optional["Usuario"] = Relationship(back_populates="inscripciones")
    instancia_cursado: Optional["InstanciaCursado"] = Relationship(back_populates="inscripciones")
    calificaciones: List["Calificacion"] = Relationship(back_populates="inscripcion")
    inscripciones_examen: List["InscripcionExamen"] = Relationship(back_populates="inscripcion_materia")


# ── Schemas ──────────────────────────────────────────────────────────────────

class InscripcionMateriaCreate(SQLModel):
    usuario_id: int
    instancia_cursado_id: int


class InscripcionMateriaRead(SQLModel):
    id: int
    usuario_id: int
    instancia_cursado_id: int
    estado: EstadoInscripcionMateria
    nota_curso: Optional[Decimal] = None
    nota_final: Optional[Decimal] = None
    nota_final_directa: Optional[Decimal] = None
    creditos_obtenidos: int
    faltas: int = 0
    snapshot_politica: Optional[dict] = None
    snapshot_instancias: Optional[list] = None
    fecha_inscripcion: datetime
    fecha_cierre: Optional[datetime] = None
    motivo_cierre: Optional[str] = None
    id_rastreo: Optional[str] = None


class InscripcionMateriaResumen(SQLModel):
    """Vista resumida para escolaridad"""
    id: int
    materia_nombre: str
    materia_codigo: Optional[str] = None
    semestre: int
    anio_lectivo: int
    estado: EstadoInscripcionMateria
    nota_curso: Optional[Decimal] = None
    nota_final: Optional[Decimal] = None
    creditos_obtenidos: int
    faltas: int = 0


class MarcarInasistenciaRequest(SQLModel):
    inscripcion_id: int
    motivo: Optional[str] = None


class MarcarAbandonoRequest(SQLModel):
    inscripcion_id: int
    motivo: Optional[str] = None
