from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON
from datetime import date, datetime
from typing import Optional, List, TYPE_CHECKING
from pydantic import field_validator
from enum import Enum
import json

if TYPE_CHECKING:
    # Importación condicional de las clases relacionadas para evitar importación circular
    from database.models.user import User, UserRead
    from database.models.career import Career, CareerRead

# Enum Area (reutilizado de Career)
class Area(str, Enum):
    ADMINISTRATION = "administration"
    COMMUNICATION = "communication"
    CULTURE = "culture"
    GENERAL = "general"
    IT = "it"

# Modelo base para la tabla
class NewsBase(SQLModel):
    area: Area = Field(description="Área de la noticia")
    career: Optional[int] = Field(default=None, foreign_key="career.careerId", description="ID de la carrera (opcional)")
    title: str = Field(max_length=150, description="Título de la noticia")
    text: str = Field(max_length=5000, description="Contenido de la noticia")
    videoLink: Optional[str] = Field(default=None, description="Enlace del video")

# Modelo para la tabla (con relaciones)
class News(NewsBase, table=True):
    newsId: Optional[int] = Field(default=None, primary_key=True, description="ID único de la noticia")
    creationDate: date = Field(default_factory=lambda: datetime.now().date(), description="Fecha de creación")
    modificationDate: Optional[date] = Field(default=None, description="Fecha de modificación")
    publicationDate: Optional[date] = Field(default=None, description="Fecha de publicación")
    published: bool = Field(default=True, description="Estado de publicación")
    creator: int = Field(foreign_key="user.userId", description="ID del usuario creador")
    modifier: Optional[int] = Field(default=None, foreign_key="user.userId", description="ID del usuario modificador")
    
    # Campo JSON para las imágenes (hasta 6)
    imagesLink: Optional[List[str]] = Field(default=None, sa_column=Column(JSON), description="URLs de las imágenes")
    
    # Relaciones
    creator_user: Optional["User"] = Relationship(
        back_populates="created_news",
        sa_relationship_kwargs={"foreign_keys": "[News.creator]"}
    )
    modifier_user: Optional["User"] = Relationship(
        back_populates="modified_news",
        sa_relationship_kwargs={"foreign_keys": "[News.modifier]"}
    )
    career_ref: Optional["Career"] = Relationship(back_populates="news")

    @property
    def images_list(self) -> List[str]:
        """Convertir JSON a lista de URLs de imágenes"""
        if self.imagesLink:
            try:
                if isinstance(self.imagesLink, list):
                    return self.imagesLink[:6]  # Máximo 6 imágenes
                return json.loads(self.imagesLink)[:6] if isinstance(self.imagesLink, str) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_images_list(self, urls: List[str]) -> None:
        """Establecer URLs desde una lista (máximo 6)"""
        if urls and len(urls) > 6:
            urls = urls[:6]  # Limitar a 6 imágenes
        self.imagesLink = urls if urls else None

    def add_image_url(self, url: str) -> None:
        """Agregar una URL a la lista (respetando el límite de 6)"""
        urls = self.images_list
        if url not in urls and len(urls) < 6:
            urls.append(url)
            self.set_images_list(urls)

    def remove_image_url(self, url: str) -> None:
        """Remover una URL de la lista"""
        urls = self.images_list
        if url in urls:
            urls.remove(url)
            self.set_images_list(urls)

# Modelo para crear una noticia (POST)
class NewsCreate(NewsBase):
    creator: int
    imagesLink: Optional[List[str]] = Field(default=None, max_items=6, description="URLs de las imágenes (máximo 6)")

# Modelo para actualizar una noticia (PUT/PATCH)
class NewsUpdate(SQLModel):
    area: Optional[Area] = None
    career: Optional["CareerRead"] = None
    title: Optional[str] = Field(default=None, max_length=150)
    text: Optional[str] = Field(default=None, max_length=5000)
    videoLink: Optional[str] = None
    imagesLink: Optional[List[str]] = Field(default=None, max_items=6)
    publicationDate: Optional[date] = None
    published: Optional[bool] = None
    modifier: Optional[int] = None
    modificationDate: Optional[date] = Field(default_factory=lambda: datetime.now().date())
    
    @field_validator('imagesLink')
    @classmethod
    def validate_images(cls, v):
        if v and len(v) > 6:
            raise ValueError('Máximo 6 imágenes permitidas')
        return v
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Actualizar fecha de modificación automáticamente
        self.modificationDate = datetime.now().date()

# Modelo para leer una noticia (GET) - incluye todos los campos
class NewsRead(NewsBase):
    newsId: int
    creationDate: date
    modificationDate: Optional[date] = None
    publicationDate: Optional[date] = None
    published: bool
    creator: int
    modifier: Optional[int] = None
    imagesLink: Optional[List[str]] = None


class NewsFilterResponse(SQLModel):
    newsId: int
    title: str
    text: str
    area: Area
    published: bool
    publicationDate: Optional[date] = None
    creationDate: date
    modificationDate: Optional[date] = None
    videoLink: Optional[str] = None
    imagesLink: Optional[List[str]] = None
    career: Optional[int] = None  # ID de la carrera
    creator: Optional[int] = None  
    modifier: Optional[int] = None
    
    # Relaciones opcionales
    creator_user: Optional["UserRead"] = None
    modifier_user: Optional["UserRead"] = None
    career_ref: Optional["CareerRead"] = None
# Modelo para respuestas de lista
class NewsInList(SQLModel):
    newsId: int
    title: str
    area: Area
    published: bool
    publicationDate: Optional[date] = None
    creationDate: date
    # Primera imagen para preview
    preview_image: Optional[str] = None

    @classmethod
    def from_news(cls, news: News):
        """Crear desde un objeto News con imagen preview"""
        images = news.images_list
        return cls(
            newsId=news.newsId,
            title=news.title,
            area=news.area,
            published=news.published,
            publicationDate=news.publicationDate,
            creationDate=news.creationDate,
            preview_image=images[0] if images else None
        )

# Modelo público para mostrar noticias (sin información sensible)
class NewsPublic(SQLModel):
    newsId: int
    title: str
    text: str
    area: Area
    publicationDate: Optional[date] = None
    videoLink: Optional[str] = None
    imagesLink: Optional[List[str]] = None
    career_name: Optional[str] = None
    
from .career import CareerRead
from .user import UserRead
# Rebuild después de definir todos los modelos
NewsRead.model_rebuild()
