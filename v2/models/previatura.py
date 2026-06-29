from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from uuid import uuid4

from v2.models.enums import TipoPreviatura

if TYPE_CHECKING:
    from v2.models.materia import Materia


class Previatura(SQLModel, table=True):
    __tablename__ = "previatura"

    id: Optional[int] = Field(default=None, primary_key=True)
    materia_id: int = Field(foreign_key="materia.id", description="Materia que tiene el requisito")
    materia_previa_id: int = Field(foreign_key="materia.id", description="Materia que es prerequisito")
    tipo_requerido: TipoPreviatura = Field(description="APROBADA (examen o exoneración) o EXONERADA (solo exoneración)")
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    materia: Optional["Materia"] = Relationship(
        back_populates="previaturas",
        sa_relationship_kwargs={"foreign_keys": "[Previatura.materia_id]"}
    )
    materia_previa: Optional["Materia"] = Relationship(
        back_populates="es_previatura_de",
        sa_relationship_kwargs={"foreign_keys": "[Previatura.materia_previa_id]"}
    )


# ── Schemas ──────────────────────────────────────────────────────────────────

class PreviaturaCreate(SQLModel):
    materia_id: int
    materia_previa_id: int
    tipo_requerido: TipoPreviatura


class PreviaturaRead(SQLModel):
    id: int
    materia_id: int
    materia_previa_id: int
    tipo_requerido: TipoPreviatura
    id_rastreo: Optional[str] = None


class PreviaturaConNombres(SQLModel):
    """Para mostrar previaturas con nombres de materias"""
    id: int
    materia_id: int
    materia_nombre: str
    materia_previa_id: int
    materia_previa_nombre: str
    tipo_requerido: TipoPreviatura
