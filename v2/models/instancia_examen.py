from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

from v2.models.enums import ModalidadExamen, TipoExamen, EstadoInstanciaExamen

if TYPE_CHECKING:
    from v2.models.materia import Materia
    from v2.models.inscripcion_examen import InscripcionExamen
    from v2.models.docente_instancia_examen import DocenteInstanciaExamen


# ── Modelo de tabla ──────────────────────────────────────────────────────────

class InstanciaExamen(SQLModel, table=True):
    __tablename__ = "instancia_examen"

    id: Optional[int] = Field(default=None, primary_key=True)
    materia_id: int = Field(foreign_key="materia.id", index=True, description="Materia del examen")
    nombre: str = Field(max_length=100, description="Ej: 'Febrero 2026 - Programación 1'")
    fecha_inicio_inscripcion: datetime = Field(description="Inicio inscripción al examen")
    fecha_fin_inscripcion: datetime = Field(description="Fin inscripción al examen")
    fecha_examen: datetime = Field(description="Fecha del examen")
    hora: Optional[str] = Field(default=None, max_length=10, description="Hora del examen")
    salon: Optional[str] = Field(default=None, max_length=100, description="Salón del examen")
    modalidad: ModalidadExamen = Field(
        default=ModalidadExamen.PRESENCIAL,
        description="Modalidad del examen"
    )
    tipo: TipoExamen = Field(
        default=TipoExamen.ORDINARIO,
        description="Tipo de examen"
    )
    estado: EstadoInstanciaExamen = Field(
        default=EstadoInstanciaExamen.PROGRAMADO,
        description="Estado de la instancia de examen"
    )
    habilitado: bool = Field(default=True, description="Control manual del admin")
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    materia: Optional["Materia"] = Relationship(back_populates="instancias_examen")
    inscripciones: List["InscripcionExamen"] = Relationship(back_populates="instancia_examen")
    profesores: List["DocenteInstanciaExamen"] = Relationship(back_populates="instancia_examen")


# ── Schemas ──────────────────────────────────────────────────────────────────

class InstanciaExamenCreate(SQLModel):
    materia_id: int
    nombre: str = Field(max_length=100)
    fecha_inicio_inscripcion: datetime
    fecha_fin_inscripcion: datetime
    fecha_examen: datetime
    hora: Optional[str] = None
    salon: Optional[str] = None
    modalidad: Optional[ModalidadExamen] = None
    tipo: Optional[TipoExamen] = None
    habilitado: bool = True


class InstanciaExamenUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, max_length=100)
    fecha_inicio_inscripcion: Optional[datetime] = None
    fecha_fin_inscripcion: Optional[datetime] = None
    fecha_examen: Optional[datetime] = None
    hora: Optional[str] = None
    salon: Optional[str] = None
    modalidad: Optional[ModalidadExamen] = None
    tipo: Optional[TipoExamen] = None
    estado: Optional[EstadoInstanciaExamen] = None
    habilitado: Optional[bool] = None


class InstanciaExamenRead(SQLModel):
    id: int
    materia_id: int
    nombre: str
    fecha_inicio_inscripcion: datetime
    fecha_fin_inscripcion: datetime
    fecha_examen: datetime
    hora: Optional[str] = None
    salon: Optional[str] = None
    modalidad: ModalidadExamen
    tipo: TipoExamen
    estado: EstadoInstanciaExamen
    habilitado: bool
    id_rastreo: Optional[str] = None
