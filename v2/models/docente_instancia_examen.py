from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from v2.models.usuario import Usuario
    from v2.models.instancia_examen import InstanciaExamen


# ── Modelo de tabla ──────────────────────────────────────────────────────────

class DocenteInstanciaExamen(SQLModel, table=True):
    __tablename__ = "docente_instancia_examen"

    id: Optional[int] = Field(default=None, primary_key=True)
    docente_id: int = Field(foreign_key="usuario.id", index=True, description="Docente asignado al examen")
    instancia_examen_id: int = Field(foreign_key="instancia_examen.id", index=True, description="Instancia de examen")

    # Relaciones
    docente: Optional["Usuario"] = Relationship()
    instancia_examen: Optional["InstanciaExamen"] = Relationship(back_populates="profesores")


# ── Schemas ──────────────────────────────────────────────────────────────────

class DocenteInstanciaExamenCreate(SQLModel):
    docente_id: int
    instancia_examen_id: int


class DocenteInstanciaExamenRead(SQLModel):
    id: int
    docente_id: int
    instancia_examen_id: int
