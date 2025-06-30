from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    # Importación condicional de la clases relacionadas para evitar importación circular
    # Ejemplo: from .example import Example
    from database.models.test.author import Author, AuthorRead

class PostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

# Post Model
class PostBase(SQLModel):
    title: str = Field(max_length=200, index=True)
    content: str
    status: PostStatus = Field(default=PostStatus.DRAFT)
    tags: Optional[str] = Field(default=None, max_length=500)  # JSON string o tags separados por comas
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None

class Post(PostBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    author_id: int = Field(foreign_key="author.id")
    
    # Relaciones
    author: "Author" = Relationship(back_populates="posts", sa_relationship_kwargs={"lazy": "noload"})

class PostCreate(PostBase):
    author_id: int

class PostRead(PostBase):
    id: int
    author_id: int
    author: Optional["AuthorRead"] = None

class PostUpdate(SQLModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[PostStatus] = None
    tags: Optional[str] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None

class PostResponse(BaseModel):
    id: int
    title: str
    content: str
    status: str
    views: int
    likes: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]
    author_id: int
    # Nota: NO incluimos author aquí para evitar recursión

from .author import AuthorResponse
PostResponse.model_rebuild()

