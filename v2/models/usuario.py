from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, date
from decimal import Decimal
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

from v2.models.enums import RolUsuario

if TYPE_CHECKING:
    from v2.models.inscripcion_materia import InscripcionMateria
    from v2.models.docente_materia import DocenteMateria
    from v2.models.calificacion import Calificacion
    from v2.models.equipo import EquipoMiembro
    from v2.models.alumno import Alumno
    from v2.models.profesor import Profesor
    from v2.models.administrativo import Administrativo
    from v2.models.documento_usuario import DocumentoUsuario


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


# ── Modelo de tabla ──────────────────────────────────────────────────────────

class Usuario(SQLModel, table=True):
    __tablename__ = "usuario"

    id: Optional[int] = Field(default=None, primary_key=True)
    google_id: Optional[str] = Field(default=None, unique=True, index=True, description="Google sub (ID permanente)")
    moodle_id: Optional[int] = Field(default=None, unique=True, description="ID de usuario en Moodle")
    email: str = Field(unique=True, index=True, max_length=255, description="Email institucional @ctcsalto.edu.uy")
    nombre: str = Field(max_length=100, description="Nombre")
    apellido: str = Field(max_length=100, description="Apellido")
    documento: Optional[str] = Field(default=None, max_length=20, description="CI o pasaporte")
    telefono: Optional[str] = Field(default=None, max_length=20, description="Teléfono para WhatsApp")
    foto_url: Optional[str] = Field(default=None, description="URL foto de perfil de Google")
    ou_google: Optional[str] = Field(default=None, max_length=100, description="Última OU conocida (ej: /Alumnos)")
    rol: RolUsuario = Field(description="Rol asignado desde OU de Google")
    activo: bool = Field(default=True, description="Acceso al sistema")
    google_activo: bool = Field(default=True, description="Cuenta Google existe")
    moodle_activo: bool = Field(default=True, description="Cuenta Moodle existe")
    fecha_creacion: datetime = Field(
        default_factory=lambda: datetime.now(get_uruguay_tz()),
        description="Fecha de primer login"
    )
    ultimo_acceso: Optional[datetime] = Field(default=None, description="Último login")
    email_personal: Optional[str] = Field(default=None, max_length=255, description="Email personal del usuario")
    fecha_nacimiento: Optional[date] = Field(default=None, description="Fecha de nacimiento")
    domicilio: Optional[str] = Field(default=None, max_length=200, description="Dirección del usuario")
    eliminado: bool = Field(default=False, description="Soft-delete flag")
    fecha_eliminacion: Optional[datetime] = Field(default=None, description="Fecha de eliminación lógica")
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    inscripciones: List["InscripcionMateria"] = Relationship(back_populates="usuario")
    asignaciones_docente: List["DocenteMateria"] = Relationship(back_populates="docente")
    calificaciones_cargadas: List["Calificacion"] = Relationship(back_populates="docente")
    equipos: List["EquipoMiembro"] = Relationship(back_populates="usuario")
    perfil_alumno: Optional["Alumno"] = Relationship(back_populates="usuario")
    perfil_profesor: Optional["Profesor"] = Relationship(back_populates="usuario")
    perfil_administrativo: Optional["Administrativo"] = Relationship(back_populates="usuario")
    documentos: List["DocumentoUsuario"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={"foreign_keys": "[DocumentoUsuario.usuario_id]"}
    )


# ── Schemas ──────────────────────────────────────────────────────────────────

class UsuarioRead(SQLModel):
    id: int
    google_id: Optional[str] = None
    moodle_id: Optional[int] = None
    email: str
    email_personal: Optional[str] = None
    nombre: str
    apellido: str
    documento: Optional[str] = None
    telefono: Optional[str] = None
    foto_url: Optional[str] = None
    ou_google: Optional[str] = None
    rol: RolUsuario
    activo: bool
    google_activo: bool
    moodle_activo: bool
    fecha_nacimiento: Optional[date] = None
    domicilio: Optional[str] = None
    eliminado: bool = False
    fecha_creacion: datetime
    ultimo_acceso: Optional[datetime] = None
    id_rastreo: Optional[str] = None


class UsuarioUpdate(SQLModel):
    documento: Optional[str] = Field(default=None, max_length=20)
    telefono: Optional[str] = Field(default=None, max_length=20)
    email_personal: Optional[str] = Field(default=None, max_length=255)
    fecha_nacimiento: Optional[date] = None
    domicilio: Optional[str] = Field(default=None, max_length=200)
    activo: Optional[bool] = None
    google_activo: Optional[bool] = None
    moodle_activo: Optional[bool] = None


class UsuarioPublic(SQLModel):
    """Datos públicos del usuario (sin IDs externos)"""
    id: int
    email: str
    nombre: str
    apellido: str
    foto_url: Optional[str] = None
    rol: RolUsuario


class UsuarioSimple(SQLModel):
    """Para referencias embebidas (ej: en calificaciones, equipos)"""
    id: int
    nombre: str
    apellido: str
    email: str
