from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from decimal import Decimal
from uuid import uuid4

if TYPE_CHECKING:
    from v2.models.instancia_cursado import InstanciaCursado
    from v2.models.calificacion import Calificacion
    from v2.models.equipo import Equipo


class MateriaInstanciaEvaluacion(SQLModel, table=True):
    __tablename__ = "materia_instancia_evaluacion"

    id: Optional[int] = Field(default=None, primary_key=True)
    instancia_cursado_id: int = Field(foreign_key="instancia_cursado.id", index=True, description="Instancia de cursado")
    nombre: str = Field(max_length=100, description="Ej: 'Primer Parcial', 'Proyecto Obligatorio'")
    peso_maximo: Decimal = Field(max_digits=5, decimal_places=2, description="Puntaje máximo de esta instancia")
    orden: int = Field(description="Orden de presentación (1, 2, 3, 4)")
    es_grupal: bool = Field(default=False, description="Permite evaluación por equipos")
    activo: bool = Field(default=True)
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    instancia_cursado: Optional["InstanciaCursado"] = Relationship(back_populates="evaluaciones")
    calificaciones: List["Calificacion"] = Relationship(back_populates="instancia_evaluacion")
    equipos: List["Equipo"] = Relationship(back_populates="instancia_evaluacion")


# ── Schemas ──────────────────────────────────────────────────────────────────

class InstanciaEvaluacionCreate(SQLModel):
    instancia_cursado_id: int
    nombre: str = Field(max_length=100)
    peso_maximo: Decimal = Field(max_digits=5, decimal_places=2)
    orden: int
    es_grupal: bool = False


class InstanciaEvaluacionUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, max_length=100)
    peso_maximo: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)
    orden: Optional[int] = None
    es_grupal: Optional[bool] = None
    activo: Optional[bool] = None


class InstanciaEvaluacionRead(SQLModel):
    id: int
    instancia_cursado_id: int
    nombre: str
    peso_maximo: Decimal
    orden: int
    es_grupal: bool
    activo: bool
    id_rastreo: Optional[str] = None
