from sqlmodel import SQLModel, Field, Relationship
from datetime import date, datetime
from typing import Optional, List, TYPE_CHECKING
from pydantic import field_validator

if TYPE_CHECKING:
    from database.models.user import User, UserRead
    from database.models.career import Career, CareerRead

# Modelo base para la tabla
class TestimonyBase(SQLModel):
    text: str = Field(max_length=350, description="Texto del testimonio")
    name: str = Field(max_length=50, description="Nombre de la persona")
    lastname: str = Field(max_length=50, description="Apellido de la persona")
    career: int = Field(foreign_key="career.careerId", description="ID de la carrera")

# Modelo para la tabla (con relaciones)
class Testimony(TestimonyBase, table=True):
    testimonyId: Optional[int] = Field(default=None, primary_key=True, description="ID único del testimonio")
    creationDate: date = Field(default_factory=lambda: datetime.now().date(), description="Fecha de creación")
    modificationDate: Optional[date] = Field(default=None, description="Fecha de modificación")
    creator: int = Field(foreign_key="user.userId", description="ID del usuario creador")
    modifier: Optional[int] = Field(default=None, foreign_key="user.userId", description="ID del usuario modificador")
    
    creator_user: Optional["User"] = Relationship(back_populates="created_testimonies", sa_relationship_kwargs={"foreign_keys": "[Testimony.creator]"})
    modifier_user: Optional["User"] = Relationship(back_populates="modified_testimonies", sa_relationship_kwargs={"foreign_keys": "[Testimony.modifier]"})
    career_ref: Optional["Career"] = Relationship(back_populates="testimonies")

# Modelo para crear un testimonio (POST)
class TestimonyCreate(TestimonyBase):
    creator: int
# Modelo para actualizar un testimonio (PUT/PATCH)
class TestimonyUpdate(SQLModel):
    text: Optional[str] = Field(default=None, max_length=350)
    name: Optional[str] = Field(default=None, max_length=50)
    lastname: Optional[str] = Field(default=None, max_length=50)
    career: Optional[int] = None
    modifier: Optional[int] = None
    modificationDate: Optional[date] = Field(default_factory=lambda: datetime.now().date())
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Actualizar fecha de modificación automáticamente
        self.modificationDate = datetime.now().date()

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

# Modelo para respuestas de lista
class TestimonyInList(SQLModel):
    testimonyId: int
    text: str
    name: str
    lastname: str
    career: int
    creationDate: date

# Modelo público para mostrar testimonios (sin información sensible)
class TestimonyPublic(SQLModel):
    testimonyId: int
    text: str
    name: str
    lastname: str
    # career_name: Optional[str] = None  # Se puede agregar con join
    
from .user import UserRead
from .career import CareerRead
# Rebuild después de definir todos los modelos
TestimonyRead.model_rebuild()
