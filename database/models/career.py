from sqlmodel import SQLModel, Field, Relationship
from datetime import date, datetime
from typing import Optional, List, TYPE_CHECKING
from enum import Enum

from fastapi import Form
from pydantic import BaseModel

import os
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    # Importación condicional de las clases relacionadas para evitar importación circular
    from database.models.user import User, UserRead
    from database.models.testimony import Testimony, TestimonyRead
    from database.models.news import News

# Enums
class CareerType(str, Enum):
    CAREER = "career"
    COURSE = "course"
    WORKSHOP = "workshop"
    DIPLOMA = "diploma"

class Area(str, Enum):
    ADMINISTRATION = "administration"
    COMMUNICATION = "communication"
    CULTURE = "culture"
    GENERAL = "general"
    IT = "it"
    
def get_uruguay_tz():
    """Lee la variable cada vez que se llama"""
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class CareerBase(SQLModel):
    careerType: CareerType = Field(description="Tipo de carrera")
    area: Area = Field(description="Área de la carrera")
    name: str = Field(max_length=100, description="Nombre de la carrera")
    subtitle: str = Field(max_length=130, description="Subtítulo de la carrera")
    aboutCourse1: str = Field(description="Descripción del curso parte 1")
    aboutCourse2: Optional[str] = Field(default=None, description="Descripción del curso parte 2")
    graduateProfile: Optional[str] = Field(default=None, description="Perfil del egresado")
    studyPlan: Optional[str] = Field(default=None,description="Plan de estudios")
    imageLink: str = Field(description="Enlace de la imagen")
    
    # Campos de fase 2, al ser agregados posteriormente son opcionales
    duration: Optional[str] = Field(default=None, description="Duración")
    hourlyLoad: Optional[str] = Field(default=None, description="Carga horaria")
    cost: Optional[str] = Field(default=None, description="Costo")
    startClasses: Optional[date] = Field(default=None, description="Próximo inicio de clases")
    certificationType: Optional[str] = Field(default=None, description="Tipo certificación")

# Modelo para la tabla (con relaciones)
class Career(CareerBase, table=True):
    careerId: Optional[int] = Field(default=None, primary_key=True, description="ID único de la carrera")
    creationDate: date = Field(default_factory=lambda: datetime.now(get_uruguay_tz()).date(), description="Fecha de creación")
    modificationDate: Optional[date] = Field(default=None, description="Fecha de modificación")
    publicationDate: Optional[date] = Field(default=None, description="Fecha de publicación")
    published: bool = Field(default=False, description="Estado de publicación")
    creator: int = Field(foreign_key="user.userId", description="ID del usuario creador")
    modifier: Optional[int] = Field(default=None, foreign_key="user.userId", description="ID del usuario modificador")
    
    # Relaciones
    creator_user: Optional["User"] = Relationship(
        back_populates="created_careers",
        sa_relationship_kwargs={"foreign_keys": "[Career.creator]"}
    )
    modifier_user: Optional["User"] = Relationship(
        back_populates="modified_careers",
        sa_relationship_kwargs={"foreign_keys": "[Career.modifier]"}
    )
    testimonies: List["Testimony"] = Relationship(back_populates="career_ref")
    news: List["News"] = Relationship(back_populates="career_ref")
    
# Modelo para crear una carrera (POST)
class CareerCreate(CareerBase):
    creator: int
    published: bool = False
    publicationDate: Optional[date] = None
    
class CareerCreateForm(BaseModel):
    name: str
    subtitle: str
    aboutCourse1: str
    published: bool
    aboutCourse2: Optional[str] = None
    graduateProfile: Optional[str] = None
    studyPlan: Optional[str] = None
    careerType: str = "career"
    area: str = "it"
    
    # NUEVOS CAMPOS
    duration: Optional[str] = None
    hourlyLoad: Optional[str] = None
    cost: Optional[str] = None
    startClasses: Optional[date] = None
    certificationType: Optional[str] = None

    @classmethod
    def as_form(
        cls,
        name: str = Form(..., max_length=100),
        subtitle: str = Form(..., max_length=130),
        aboutCourse1: str = Form(...),
        published: bool = Form(...),
        aboutCourse2: Optional[str] = Form(None),
        graduateProfile: Optional[str] = Form(None),
        studyPlan: Optional[str] = Form(None),
        careerType: str = Form("career"),
        area: str = Form("it"),
        # NUEVOS CAMPOS
        duration: Optional[str] = Form(None),
        hourlyLoad: Optional[str] = Form(None),
        cost: Optional[str] = Form(None),
        startClasses: Optional[date] = Form(None),
        certificationType: Optional[str] = Form(None)
    ) -> 'CareerCreateForm':
        return cls(
            name=name,
            subtitle=subtitle,
            aboutCourse1=aboutCourse1,
            published=published,
            aboutCourse2=aboutCourse2,
            graduateProfile=graduateProfile,
            studyPlan=studyPlan,
            careerType=careerType,
            area=area,
            # NUEVOS CAMPOS
            duration=duration,
            hourlyLoad=hourlyLoad,
            cost=cost,
            startClasses=startClasses,
            certificationType=certificationType
        )

# Modelo para actualizar una carrera (PUT/PATCH)
class CareerUpdate(SQLModel):
    careerType: Optional[CareerType] = None
    area: Optional[Area] = None
    name: Optional[str] = Field(default=None, max_length=100)
    subtitle: Optional[str] = Field(default=None, max_length=130)
    aboutCourse1: Optional[str] = None
    aboutCourse2: Optional[str] = None
    graduateProfile: Optional[str] = None
    studyPlan: Optional[str] = None
    imageLink: Optional[str] = None
    publicationDate: Optional[date] = None
    published: Optional[bool] = None
    modifier: Optional[int] = None
    modificationDate: Optional[date] = Field(default_factory=lambda: datetime.now(get_uruguay_tz()).date())
    
    duration: Optional[str] = None
    hourlyLoad: Optional[str] = None
    cost: Optional[str] = None
    startClasses: Optional[date] = None
    certificationType: Optional[str] = None

# Modelo para leer una carrera (GET) - incluye todos los campos
class CareerRead(CareerBase):
    careerId: int
    creationDate: date
    modificationDate: Optional[date] = None
    publicationDate: Optional[date] = None
    published: bool
    creator: int
    modifier: Optional[int] = None
    creator_user: Optional["UserRead"] = None
    modifier_user: Optional["UserRead"] = None
    testimonies: List["TestimonyRead"] = []
    
class CareerFilterResponse(SQLModel):
    careerId: Optional[int] = None
    creationDate: Optional[date] = None
    modificationDate: Optional[date] = None
    publicationDate: Optional[date] = None
    published: Optional[bool] = None
    creator: Optional[int] = None
    modifier: Optional[int] = None
    creator_user: Optional["UserRead"] = None
    modifier_user: Optional["UserRead"] = None
    testimonies: List["TestimonyRead"] = []
    
    duration: Optional[str] = None
    hourlyLoad: Optional[str] = None
    cost: Optional[str] = None
    startClasses: Optional[date] = None
    certificationType: Optional[str] = None
    
class CareerFilterWithCountResponse(SQLModel):
    data: List[CareerFilterResponse] = []
    total_count: int = 0

class CareerReadSimple(CareerBase):
    careerId: int
    creationDate: date
    modificationDate: Optional[date] = None
    publicationDate: Optional[date] = None
    published: bool
    creator: int
    modifier: Optional[int] = None
    
class CareerSimple(SQLModel):
    """Modelo minimalista de carrera para endpoints públicos"""
    careerId: int = Field(description="ID único de la carrera")
    imageLink: str = Field(description="Enlace de la imagen")
    aboutCourse1: str = Field(description="Descripción del curso parte 1")
    careerType: CareerType = Field(description="Tipo de carrera")
    area: Area = Field(description="Área de la carrera")
    name: str = Field(description="Nombre de la carrera")
    
    duration: Optional[str] = None
    hourlyLoad: Optional[str] = None
    cost: Optional[str] = None
    startClasses: Optional[date] = None
    certificationType: Optional[str] = None
    
class CarrerDropdown(SQLModel):
    """Modelo para dropdown de carreras (id, name)"""
    careerId: int = Field(description="ID único de la carrera")
    name: str = Field(description="Nombre de la carrera")
    
class TestimonyForCareer(SQLModel):
    """Testimonio simplificado para mostrar en career sin referencia circular"""
    testimonyId: int
    text: str
    name: str
    lastname: str
    creationDate: date
    
class UserSimple(SQLModel):
    userId: int
    name: str
    lastname: str
    
class CareerReadOptimized(CareerBase):
    careerId: int
    creationDate: date
    modificationDate: Optional[date] = None
    publicationDate: Optional[date] = None
    published: bool
    creator: int
    modifier: Optional[int] = None
    
    # Usuarios simplificados (solo id, name, lastname)
    creator_user: Optional[UserSimple] = None
    modifier_user: Optional[UserSimple] = None
    
    # Testimonios sin referencia circular
    testimonies: List[TestimonyForCareer] = []

# Modelo para respuestas de lista (sin algunos campos sensibles si es necesario)
class CareerInList(SQLModel):
    careerId: int
    name: str
    subtitle: str
    area: Area
    careerType: CareerType
    published: bool
    publicationDate: Optional[date] = None
    imageLink: str
    
    duration: Optional[str] = None
    cost: Optional[str] = None
    startClasses: Optional[date] = None
    
    
from .user import UserRead
from .testimony import TestimonyRead
# Rebuild después de definir todos los modelos
CareerRead.model_rebuild()
CareerReadOptimized.model_rebuild()