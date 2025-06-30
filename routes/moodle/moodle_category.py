from fastapi import APIRouter, HTTPException, Depends
from external_services.moodle_api.models.category import MoodleCategoryRead, MoodleCategoryCreate, MoodleCategoryUpdate, DeleteResponse
from external_services.moodle_api.controllers.moodle_api_controller import MoodleController
from external_services.moodle_api.moodle_config import MoodleConfig
from typing import List

router = APIRouter(prefix="/moodle", tags=["Moodle Categories"])

config = MoodleConfig.from_env()
moodle_controller = MoodleController(config)

@router.post("/categories", response_model=MoodleCategoryRead)
async def create_category(category: MoodleCategoryCreate):
    """
    Crea una nueva categoría en Moodle
    
    - **name**: Nombre de la categoría
    - **description**: Descripción de la categoría
    
    Ejemplo de solicitud:
    ```json
    {
        "name": "Analista Programador",
        "description": "Categoría para analistas programadores"
    }
    ```
    """
    try:
        # Convertir a Category para la API
        moodle_category_payload = category.to_category()
        # Hacer la petición a Moodle
        moodle_response = moodle_controller.categories.create_category(moodle_category_payload)
        # Procesar respuesta: [{"id": 123, "name": "Analista Programador"}]
        return MoodleCategoryRead.from_moodle_response(moodle_response, category)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories", response_model=List[MoodleCategoryRead])
async def get_categories():
    """
    Obtiene todas las categorías de Moodle
    """
    try:
        moodle_categories = moodle_controller.categories.get_categories()
        return moodle_categories
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories/{category_id}", response_model=MoodleCategoryRead)
async def get_category(category_id: int):
    """
    Obtiene una categoría específica de Moodle
    
    - **category_id**: ID de la categoría en Moodle
    """
    try:
        moodle_category = moodle_controller.categories.get_category_by_id(category_id)
        return moodle_category
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/categories/{category_id}", response_model=MoodleCategoryRead)
async def update_category(category_id: int, category: MoodleCategoryUpdate):
    """
    Actualiza una categoría específica de Moodle
    
    - **category_id**: ID de la categoría en Moodle
    """
    try:
        # Convertir a diccionario excluyendo campos None
        updates = category.to_update_dict()
        
        # Validar que se envió al menos un campo para actualizar
        if not updates:
            raise HTTPException(status_code=400, detail="Debe proporcionar al menos un campo para actualizar")
        
        # Llamar al controlador con el diccionario de actualizaciones
        moodle_response = moodle_controller.categories.update_category(category_id, updates)
        
        # Procesar la respuesta de Moodle
        # La respuesta de update puede ser diferente a la de create
        print(f"Respuesta de update: {moodle_response}")
        
        # Obtener la categoría actualizada para devolverla
        # (Moodle update podría no devolver los datos completos)
        try:
            updated_category = moodle_controller.categories.get_category_by_id(category_id)
            return MoodleCategoryRead.from_category_data(updated_category)
        except:
            # Fallback: crear respuesta basada en los datos enviados
            return MoodleCategoryRead(
                id=category_id,
                name=updates.get('name', ''),
                description=updates.get('description', '')
            )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        print(f"Error en update_category: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/categories/{category_id}", response_model=DeleteResponse)
async def delete_category(category_id: int):
    """
    Elimina una categoría específica de Moodle
    
    - **category_id**: ID de la categoría en Moodle
    """
    try:
        moodle_controller.categories.delete_category(category_id)
        return DeleteResponse(
            message="Categoría eliminada exitosamente",
            deleted_id=category_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))