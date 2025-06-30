from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from moodle_api.payloads.moodle_category import Category

class MoodleCategoryCreate(BaseModel):
    """Modelo para crear categorías de Moodle"""
    name: str = Field(..., description="Nombre de la categoría")
    description: str = Field(..., description="Descripción de la categoría")
    parent: int = Field(..., description="ID de la categoría padre")
    idnumber: str = Field(..., description="Número de identificación de la categoría")
    
    def to_category(self) -> 'Category':
        """Convierte MoodleCategoryCreate a Category para la API de Moodle"""
        from moodle_api.payloads.moodle_category import Category  # Ajusta según tu estructura
        
        return Category(
            name=self.name,
            description=self.description,
            parent=self.parent,
            idnumber=self.idnumber
        )

class MoodleCategoryUpdate(BaseModel):
    """Modelo para actualizar categorías - todos los campos opcionales"""
    name: Optional[str] = None
    description: Optional[str] = None
    parent: Optional[int] = None
    idnumber: Optional[str] = None
    
    def to_update_dict(self) -> Dict[str, Union[str, int]]:
        """Convierte a diccionario excluyendo campos None"""
        data = self.model_dump(exclude_none=True)
        return data

class MoodleCategoryRead(BaseModel):
    """Modelo para leer categorías de Moodle"""
    id: int = Field(..., description="ID de la categoría")
    name: str = Field(..., description="Nombre de la categoría")
    description: str = Field(..., description="Descripción de la categoría")

    @classmethod
    def from_moodle_response(cls, response: List, original_category: 'MoodleCategoryCreate' = None) -> 'MoodleCategoryRead':
        """
        Procesa la respuesta de Moodle create_categories
        Respuesta: [{"id": int, "name": str}]
        """
        if not response or len(response) == 0:
            raise ValueError("Respuesta vacía de Moodle")
        
        # Tomar el primer elemento de la lista
        category_data = response[0]
        
        return cls(
            id=category_data['id'],
            name=category_data['name'],
            # Como Moodle no devuelve description en create, usamos el original
            description=original_category.description if original_category else ""
        )
    
    @classmethod 
    def from_category_data(cls, category_data: dict) -> 'MoodleCategoryRead':
        """Para cuando tienes datos completos de categoría (ej: en GET)"""
        return cls(
            id=category_data['id'],
            name=category_data['name'],
            description=category_data.get('description', '')
        )
    
    @classmethod
    def from_moodle_get_response(cls, response: Dict) -> 'MoodleCategoryRead':
        """Para respuestas de GET que pueden tener formato diferente"""
        # Si es una lista de categorías
        if isinstance(response, list) and len(response) > 0:
            category_data = response[0]
        # Si es un dict con categorías
        elif isinstance(response, dict) and 'categories' in response:
            if len(response['categories']) == 0:
                raise ValueError("Categoría no encontrada")
            category_data = response['categories'][0]
        else:
            category_data = response
            
        return cls(
            id=category_data['id'],
            name=category_data['name'],
            description=category_data.get('description', '')
        )

class DeleteResponse(BaseModel):
    message: str = Field(..., description="Mensaje de respuesta")
    deleted_id: int = Field(..., description="ID de la categoría eliminada")