from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from uuid import uuid4

from v2.models.enums import CargoDocente, DedicacionDocente

if TYPE_CHECKING:
    from v2.models.usuario import Usuario
    from v2.models.programa import Programa
    from v2.models.docente_materia import DocenteMateria


# ── Modelo de tabla ──────────────────────────────────────────────────────────

class Profesor(SQLModel, table=True):
    __tablename__ = "profesor"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", unique=True, index=True)
    cargo: Optional[CargoDocente] = Field(default=None, description="Cargo docente")
    dedicacion: Optional[DedicacionDocente] = Field(default=None, description="Tipo de dedicación")
    especialidad: Optional[str] = Field(default=None, max_length=200, description="Área de especialidad")
    carga_horaria_semanal: Optional[int] = Field(default=None, description="Carga horaria semanal en horas")
    activo: bool = Field(
        default=True,
        description="Si dicta actualmente. Distinto de usuario.activo, que controla "
                    "el acceso al sistema: un profesor retirado puede quedar inactivo "
                    "como docente y seguir entrando a ver su historico"
    )
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    usuario: Optional["Usuario"] = Relationship(back_populates="perfil_profesor")
    programas_coordinados: List["Programa"] = Relationship(back_populates="coordinador")
    asignaciones_materia: List["DocenteMateria"] = Relationship(back_populates="profesor")


# ── Schemas ──────────────────────────────────────────────────────────────────

class ProfesorCreate(SQLModel):
    usuario_id: int
    cargo: Optional[CargoDocente] = None
    dedicacion: Optional[DedicacionDocente] = None
    especialidad: Optional[str] = None
    carga_horaria_semanal: Optional[int] = None
    activo: bool = True


class ProfesorRead(SQLModel):
    id: int
    usuario_id: int
    cargo: Optional[CargoDocente] = None
    dedicacion: Optional[DedicacionDocente] = None
    especialidad: Optional[str] = None
    carga_horaria_semanal: Optional[int] = None
    activo: bool = True
    id_rastreo: Optional[str] = None


class ProfesorUpdate(SQLModel):
    cargo: Optional[CargoDocente] = None
    dedicacion: Optional[DedicacionDocente] = None
    especialidad: Optional[str] = None
    carga_horaria_semanal: Optional[int] = None
    activo: Optional[bool] = None
