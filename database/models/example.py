from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON
from typing import Optional, List
from fastapi import UploadFile
import json

class ExampleBase(SQLModel):
    name: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=3, max_length=100, unique=True)
    age: Optional[int] = Field(default=None, ge=0, le=120)
    # Mantener image_url para compatibilidad hacia atrás
    image_url: Optional[str] = Field(default=None, max_length=500)
    # Usar Text para almacenar JSON de URLs múltiples
    image_urls: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))

    @property
    def image_urls_list(self) -> List[str]:
        """Convertir JSON string a lista de URLs"""
        if self.image_urls:
            try:
                return json.loads(self.image_urls)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_image_urls_list(self, urls: List[str]) -> None:
        """Establecer URLs desde una lista"""
        self.image_urls = json.dumps(urls) if urls else None

    def add_image_url(self, url: str) -> None:
        """Agregar una URL a la lista"""
        urls = self.image_urls_list
        if url not in urls:
            urls.append(url)
            self.set_image_urls_list(urls)

    def remove_image_url(self, url: str) -> None:
        """Remover una URL de la lista"""
        urls = self.image_urls_list
        if url in urls:
            urls.remove(url)
            self.set_image_urls_list(urls)

class Example(ExampleBase, table=True):
    __tablename__ = "example"
    
    id: Optional[int] = Field(default=None, primary_key=True)

# Schemas para recibir datos (sin archivos)
class ExampleCreate(SQLModel):
    """Schema para datos básicos de creación (sin imágenes)"""
    name: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=3, max_length=100)
    age: Optional[int] = Field(default=None, ge=0, le=120)
    image_url: Optional[str] = Field(default=None, max_length=500)
    image_urls: Optional[List[str]] = Field(default=None)

class ExampleUpdate(SQLModel):
    """Schema para datos básicos de actualización (sin imágenes)"""
    name: Optional[str] = Field(default=None, min_length=3, max_length=100)
    email: Optional[str] = Field(default=None, min_length=3, max_length=100)
    age: Optional[int] = Field(default=None, ge=0, le=120)
    image_url: Optional[str] = Field(default=None, max_length=500)
    image_urls: Optional[List[str]] = Field(default=None)

# Schema para respuesta
class ExampleRead(SQLModel):
    """Schema para leer ejemplos (respuesta de API)"""
    id: int
    name: str
    email: str
    age: Optional[int] = None
    image_url: Optional[str] = None
    image_urls: Optional[List[str]] = None
    
    @classmethod
    def from_orm(cls, obj: Example) -> "ExampleRead":
        """Crear desde objeto ORM"""
        return cls(
            id=obj.id,
            name=obj.name,
            email=obj.email,
            age=obj.age,
            image_url=obj.image_url,
            image_urls=obj.image_urls
        )