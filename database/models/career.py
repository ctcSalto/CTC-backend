from sqlmodel import SQLModel, Field, Relationship
from datetime import date, datetime
from typing import Optional, List, TYPE_CHECKING
from pydantic import field_validator
from enum import Enum

if TYPE_CHECKING:
    # Importación condicional de las clases relacionadas para evitar importación circular
    from database.models.user import User, UserRead
    from database.models.testimony import Testimony, TestimonyRead
    from database.models.news import News, NewsRead

# Enums
class CareerType(str, Enum):
    CAREER = "career"
    COURSE = "course"
    WORKSHOP = "workshop"

class Area(str, Enum):
    ADMINISTRATION = "administration"
    COMMUNICATION = "communication"
    CULTURE = "culture"
    GENERAL = "general"
    IT = "it"

class CareerBase(SQLModel):
    careerType: CareerType = Field(description="Tipo de carrera")
    area: Area = Field(description="Área de la carrera")
    name: str = Field(max_length=100, description="Nombre de la carrera")
    subtitle: str = Field(max_length=130, description="Subtítulo de la carrera")
    aboutCourse1: str = Field(max_length=600, description="Descripción del curso parte 1")
    aboutCourse2: Optional[str] = Field(default=None, max_length=2000, description="Descripción del curso parte 2")
    graduateProfile: Optional[str] = Field(default=None, max_length=1500, description="Perfil del egresado")
    studyPlan: Optional[str] = Field(default=None, max_length=2500, description="Plan de estudios")
    imageLink: str = Field(description="Enlace de la imagen")

# Modelo para la tabla (con relaciones)
class Career(CareerBase, table=True):
    careerId: Optional[int] = Field(default=None, primary_key=True, description="ID único de la carrera")
    creationDate: date = Field(default_factory=lambda: datetime.now().date(), description="Fecha de creación")
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

# Modelo para actualizar una carrera (PUT/PATCH)
class CareerUpdate(SQLModel):
    careerType: Optional[CareerType] = None
    area: Optional[Area] = None
    name: Optional[str] = Field(default=None, max_length=100)
    subtitle: Optional[str] = Field(default=None, max_length=130)
    aboutCourse1: Optional[str] = Field(default=None, max_length=600)
    aboutCourse2: Optional[str] = Field(default=None, max_length=2000)
    graduateProfile: Optional[str] = Field(default=None, max_length=1500)
    studyPlan: Optional[str] = Field(default=None, max_length=2500)
    imageLink: Optional[str] = None
    publicationDate: Optional[date] = None
    published: Optional[bool] = None
    modifier: Optional[int] = None
    modificationDate: Optional[date] = Field(default_factory=lambda: datetime.now().date())

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
    
    
from .user import UserRead
from .testimony import TestimonyRead
# Rebuild después de definir todos los modelos
CareerRead.model_rebuild()
CareerReadOptimized.model_rebuild()

