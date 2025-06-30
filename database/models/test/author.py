from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from database.models.test.post import Post, PostRead, PostResponse
    from database.models.test.profile import Profile, ProfileRead, ProfileResponse

# Enums para testing
class AuthorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

# Modelos base
class AuthorBase(SQLModel):
    username: str = Field(index=True, max_length=50)
    email: str = Field(index=True, unique=True, max_length=100)
    status: AuthorStatus = Field(default=AuthorStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_verified: bool = Field(default=False)

class Author(AuthorBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relaciones
    profile: Optional["Profile"] = Relationship(back_populates="author", sa_relationship_kwargs={"lazy": "noload"})
    posts: List["Post"] = Relationship(back_populates="author", sa_relationship_kwargs={"lazy": "noload"})

class AuthorCreate(AuthorBase):
    pass

class AuthorRead(AuthorBase):
    id: int
    profile: Optional["ProfileRead"] = None
    posts: List["PostRead"] = []

class AuthorUpdate(SQLModel):
    username: Optional[str] = None
    email: Optional[str] = None
    status: Optional[AuthorStatus] = None
    is_verified: Optional[bool] = None

# CORREGIDO: AuthorResponse ahora coincide con los campos reales de Author
class AuthorResponse(BaseModel):
    id: int
    username: str  # Cambiado de 'name' a 'username'
    email: str
    status: AuthorStatus
    created_at: datetime
    is_verified: bool
    posts: List["PostResponse"] = []
    profile: Optional["ProfileResponse"] = None
    
    class Config:
        from_attributes = True

from .post import PostResponse
from .profile import ProfileResponse
# Rebuild después de definir todos los modelos
AuthorResponse.model_rebuild()