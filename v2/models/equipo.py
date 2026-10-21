from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
    from v2.models.calificacion import Calificacion
    from v2.models.alumno import Alumno


class Equipo(SQLModel, table=True):
    __tablename__ = "equipo"

    id: Optional[int] = Field(default=None, primary_key=True)
    instancia_evaluacion_id: int = Field(foreign_key="materia_instancia_evaluacion.id", description="Instancia de evaluación grupal")
    nombre: str = Field(max_length=100, description="Ej: 'Equipo 1', 'Grupo A'")
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    instancia_evaluacion: Optional["MateriaInstanciaEvaluacion"] = Relationship(back_populates="equipos")
    miembros: List["EquipoMiembro"] = Relationship(back_populates="equipo")
    calificaciones: List["Calificacion"] = Relationship(back_populates="equipo")


class EquipoMiembro(SQLModel, table=True):
    __tablename__ = "equipo_miembro"

    id: Optional[int] = Field(default=None, primary_key=True)
    equipo_id: int = Field(foreign_key="equipo.id", description="Equipo al que pertenece")
    alumno_id: int = Field(foreign_key="alumno.id", description="Alumno miembro")

    # Relaciones
    equipo: Optional["Equipo"] = Relationship(back_populates="miembros")
    alumno: Optional["Alumno"] = Relationship(back_populates="equipos")


# ── Schemas ──────────────────────────────────────────────────────────────────

class EquipoCreate(SQLModel):
    instancia_evaluacion_id: int
    nombre: str = Field(max_length=100)
    miembros_ids: list[int] = Field(default=[], description="IDs de alumno (no de usuario)")


class EquipoRead(SQLModel):
    id: int
    instancia_evaluacion_id: int
    nombre: str


class EquipoConMiembros(EquipoRead):
    miembros: list["EquipoMiembroRead"] = []


class EquipoMiembroRead(SQLModel):
    id: int
    equipo_id: int
    alumno_id: int


EquipoConMiembros.model_rebuild()
