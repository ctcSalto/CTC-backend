from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    # Importación condicional de la clases relacionadas para evitar importación circular
    # Ejemplo: from .example import Example
    from database.models.test.author import Author

# Profile Model
class ProfileBase(SQLModel):
    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50)
    age: int = Field(ge=0, le=150)
    bio: Optional[str] = Field(default=None, max_length=500)
    city: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

class Profile(ProfileBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    author_id: int = Field(foreign_key="author.id", unique=True)
    
    # Relaciones
    author: "Author" = Relationship(back_populates="profile", sa_relationship_kwargs={"lazy": "noload"})

class ProfileCreate(ProfileBase):
    author_id: int

class ProfileRead(ProfileBase):
    id: int
    author_id: int

class ProfileUpdate(SQLModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    age: Optional[int] = None
    bio: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

class ProfileResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    age: int
    bio: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime]
    author_id: int
    # Nota: NO incluimos author aquí para evitar recursión

from .author import AuthorResponse
ProfileResponse.model_rebuild()
