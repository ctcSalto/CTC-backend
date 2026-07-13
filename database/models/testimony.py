from sqlmodel import SQLModel, Field, Relationship
from pydantic import model_validator
from datetime import date, datetime
from typing import Optional, List, TYPE_CHECKING

import os
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from database.models.user import User, UserRead
    from database.models.career import Career

def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)

# Modelo base para la tabla
class TestimonyBase(SQLModel):
    text: Optional[str] = Field(default=None, max_length=350, description="Texto del testimonio (exclusivo con videoUrl)")
    name: str = Field(max_length=50, description="Nombre de la persona")
    lastname: str = Field(max_length=50, description="Apellido de la persona")
    career: int = Field(foreign_key="career.careerId", description="ID de la carrera")
    videoUrl: Optional[str] = Field(default=None, max_length=500, description="URL del video (exclusivo con text)")

# Modelo para la tabla (con relaciones)
class Testimony(TestimonyBase, table=True):
    testimonyId: Optional[int] = Field(default=None, primary_key=True)
    creationDate: date = Field(default_factory=lambda: datetime.now(get_uruguay_tz()).date())
    modificationDate: Optional[date] = Field(default=None)
    creator: int = Field(foreign_key="user.userId")
    modifier: Optional[int] = Field(default=None, foreign_key="user.userId")

    creator_user: Optional["User"] = Relationship(back_populates="created_testimonies", sa_relationship_kwargs={"foreign_keys": "[Testimony.creator]"})
    modifier_user: Optional["User"] = Relationship(back_populates="modified_testimonies", sa_relationship_kwargs={"foreign_keys": "[Testimony.modifier]"})
    career_ref: Optional["Career"] = Relationship(back_populates="testimonies")

# Modelo para crear un testimonio (POST)
class TestimonyCreate(TestimonyBase):
    creator: Optional[int] = None  # se asigna desde el usuario autenticado en el endpoint

    @model_validator(mode="after")
    def validar_texto_o_video(self):
        tiene_text = bool(self.text and self.text.strip())
        tiene_video = bool(self.videoUrl and self.videoUrl.strip())
        if tiene_text and tiene_video:
            raise ValueError("Un testimonio no puede tener texto y video al mismo tiempo. Enviá solo uno de los dos.")
        if not tiene_text and not tiene_video:
            raise ValueError("Un testimonio debe tener texto o URL de video. No puede estar vacío.")
        return self

# Modelo para actualizar un testimonio (PUT/PATCH)
class TestimonyUpdate(SQLModel):
    text: Optional[str] = Field(default=None, max_length=350)
    name: Optional[str] = Field(default=None, max_length=50)
    lastname: Optional[str] = Field(default=None, max_length=50)
    career: Optional[int] = None
    videoUrl: Optional[str] = Field(default=None, max_length=500)
    modifier: Optional[int] = None
    modificationDate: Optional[date] = Field(default_factory=lambda: datetime.now(get_uruguay_tz()).date())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.modificationDate = datetime.now(get_uruguay_tz()).date()

    @model_validator(mode="after")
    def validar_no_ambos(self):
        tiene_text = bool(self.text and self.text.strip())
        tiene_video = bool(self.videoUrl and self.videoUrl.strip())
        if tiene_text and tiene_video:
            raise ValueError("Un testimonio no puede tener texto y video al mismo tiempo. Enviá solo uno de los dos.")
        return self

# Modelo para leer un testimonio (GET) - incluye todos los campos
class TestimonyRead(TestimonyBase):
    testimonyId: int
    creationDate: date
    modificationDate: Optional[date] = None
    creator: int
    modifier: Optional[int] = None
    creator_user: Optional["UserRead"] = None
    modifier_user: Optional["UserRead"] = None
    career: Optional[int] = None


class TestimonyFilterResponse(SQLModel):
    testimonyId: Optional[int] = None
    creationDate: Optional[date] = None
    modificationDate: Optional[date] = None
    creator: Optional[int] = None
    modifier: Optional[int] = None
    creator_user: Optional["UserRead"] = None
    modifier_user: Optional["UserRead"] = None
    career: Optional[int] = None

class TestimonyFilterWithCountResponse(SQLModel):
    data: List[TestimonyFilterResponse] = []
    total_count: int = 0

# Modelo para respuestas de lista
class TestimonyInList(SQLModel):
    testimonyId: int
    text: Optional[str] = None
    name: str
    lastname: str
    career: int
    creationDate: date

# Modelo público para mostrar testimonios (sin información sensible)
class TestimonyPublic(SQLModel):
    testimonyId: int
    text: Optional[str] = None
    name: str
    lastname: str
    career: int
    career_name: str
    videoUrl: Optional[str] = None

from .user import UserRead
# Rebuild después de definir todos los modelos
TestimonyRead.model_rebuild()
TestimonyPublic.model_rebuild()
