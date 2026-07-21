from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from v2.models.profesor import Profesor
    from v2.models.instancia_examen import InstanciaExamen


# ── Modelo de tabla ──────────────────────────────────────────────────────────

class DocenteInstanciaExamen(SQLModel, table=True):
    __tablename__ = "docente_instancia_examen"

    id: Optional[int] = Field(default=None, primary_key=True)
    profesor_id: int = Field(foreign_key="profesor.id", index=True, description="Profesor asignado al examen")
    instancia_examen_id: int = Field(foreign_key="instancia_examen.id", index=True, description="Instancia de examen")

    # Relaciones
    profesor: Optional["Profesor"] = Relationship()
    instancia_examen: Optional["InstanciaExamen"] = Relationship(back_populates="profesores")


# ── Schemas ──────────────────────────────────────────────────────────────────

class DocenteInstanciaExamenCreate(SQLModel):
    profesor_id: int
    instancia_examen_id: int


class DocenteInstanciaExamenRead(SQLModel):
    id: int
    profesor_id: int
    instancia_examen_id: int
