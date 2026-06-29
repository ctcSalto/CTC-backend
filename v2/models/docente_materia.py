from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from uuid import uuid4

from v2.models.enums import RolDocente

if TYPE_CHECKING:
    from v2.models.usuario import Usuario
    from v2.models.instancia_cursado import InstanciaCursado


class DocenteMateria(SQLModel, table=True):
    __tablename__ = "docente_materia"

    id: Optional[int] = Field(default=None, primary_key=True)
    docente_id: int = Field(foreign_key="usuario.id", description="ID del docente")
    instancia_cursado_id: int = Field(foreign_key="instancia_cursado.id", index=True, description="Instancia de cursado")
    rol_docente: RolDocente = Field(description="Rol del docente en esta materia")
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    docente: Optional["Usuario"] = Relationship(back_populates="asignaciones_docente")
    instancia_cursado: Optional["InstanciaCursado"] = Relationship(back_populates="docentes")


# ── Schemas ──────────────────────────────────────────────────────────────────

class DocenteMateriaCreate(SQLModel):
    docente_id: int
    instancia_cursado_id: int
    rol_docente: RolDocente


class DocenteMateriaUpdate(SQLModel):
    rol_docente: Optional[RolDocente] = None


class DocenteMateriaRead(SQLModel):
    id: int
    docente_id: int
    instancia_cursado_id: int
    rol_docente: RolDocente
    id_rastreo: Optional[str] = None
