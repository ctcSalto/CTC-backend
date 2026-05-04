from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

if TYPE_CHECKING:
    from v2.models.programa import Programa


class PeriodoInscripcionMateria(SQLModel, table=True):
    __tablename__ = "periodo_inscripcion_materia"

    id: Optional[int] = Field(default=None, primary_key=True)
    programa_id: int = Field(foreign_key="programa.id", description="Programa al que aplica")
    anio_lectivo: int = Field(description="Año lectivo (2026)")
    semestre: Optional[int] = Field(default=None, description="Semestre si aplica por semestre")
    fecha_inicio: datetime = Field(description="Inicio del periodo de inscripción")
    fecha_fin: datetime = Field(description="Fin del periodo de inscripción")
    habilitado: bool = Field(default=True, description="Control manual del admin")
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    programa: Optional["Programa"] = Relationship(back_populates="periodos_inscripcion")


# ── Schemas ──────────────────────────────────────────────────────────────────

class PeriodoInscripcionMateriaCreate(SQLModel):
    programa_id: int
    anio_lectivo: int
    semestre: Optional[int] = None
    fecha_inicio: datetime
    fecha_fin: datetime
    habilitado: bool = True


class PeriodoInscripcionMateriaUpdate(SQLModel):
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    habilitado: Optional[bool] = None


class PeriodoInscripcionMateriaRead(SQLModel):
    id: int
    programa_id: int
    anio_lectivo: int
    semestre: Optional[int] = None
    fecha_inicio: datetime
    fecha_fin: datetime
    habilitado: bool
    id_rastreo: Optional[str] = None
