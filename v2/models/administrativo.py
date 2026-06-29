from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from v2.models.usuario import Usuario


# ── Modelo de tabla ──────────────────────────────────────────────────────────

class Administrativo(SQLModel, table=True):
    __tablename__ = "administrativo_perfil"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", unique=True, index=True)
    departamento: Optional[str] = Field(default=None, max_length=100, description="Departamento administrativo")
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    usuario: Optional["Usuario"] = Relationship(back_populates="perfil_administrativo")


# ── Schemas ──────────────────────────────────────────────────────────────────

class AdministrativoCreate(SQLModel):
    usuario_id: int
    departamento: Optional[str] = None


class AdministrativoRead(SQLModel):
    id: int
    usuario_id: int
    departamento: Optional[str] = None
    id_rastreo: Optional[str] = None


class AdministrativoUpdate(SQLModel):
    departamento: Optional[str] = None
