from sqlmodel import SQLModel, Field, Relationship
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

import os
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from database.models.testimony import Testimony


def get_uruguay_tz():
    """Lee la variable cada vez que se llama"""
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


# Modelo base para la tabla
class TestimonyVideoBase(SQLModel):
    url: str = Field(max_length=500, description="URL del video (YouTube, Supabase, etc.)")
    order: int = Field(default=0, description="Orden de reproducción dentro del testimonio")


# Modelo para la tabla (con relaciones)
class TestimonyVideo(TestimonyVideoBase, table=True):
    __tablename__ = "testimony_video"

    testimonyVideoId: Optional[int] = Field(default=None, primary_key=True, description="ID único del video")
    testimonyId: int = Field(foreign_key="testimony.testimonyId", index=True, description="ID del testimonio")
    creationDate: date = Field(default_factory=lambda: datetime.now(get_uruguay_tz()).date(), description="Fecha de creación")

    testimony: Optional["Testimony"] = Relationship(back_populates="videos")


# Modelo para crear un video (POST) - testimonyId viene del path
class TestimonyVideoCreate(TestimonyVideoBase):
    pass


# Modelo para actualizar un video (PUT/PATCH)
class TestimonyVideoUpdate(SQLModel):
    url: Optional[str] = Field(default=None, max_length=500)
    order: Optional[int] = None


# Modelo para leer un video (GET)
class TestimonyVideoRead(TestimonyVideoBase):
    testimonyVideoId: int
    testimonyId: int
    creationDate: date
