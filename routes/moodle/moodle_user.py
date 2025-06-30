from fastapi import APIRouter, HTTPException, Query
from external_services.moodle_api.models.user import MoodleUserCreate, MoodleUserRead, MoodleUserUpdate, DeleteUserResponse
from external_services.moodle_api.controllers.moodle_api_controller import MoodleController
from external_services.moodle_api.moodle_config import MoodleConfig
from utils.logger import show
from typing import List, Optional

router = APIRouter(prefix="/moodle", tags=["Moodle Users"])

config = MoodleConfig.from_env()
moodle_controller = MoodleController(config)

@router.post("/users", response_model=MoodleUserRead)
async def create_moodle_user(user: MoodleUserCreate):
    """
    Crea un usuario en Moodle. Las contraseñas deben tener al menos 8 caracteres, una mayúscula, una minúscula, un número y un caracter especial
    
    - **username**: Nombre de usuario
    - **firstname**: Nombre
    - **lastname**: Apellido
    - **email**: Email
    - **password**: Contraseña
    
    Ejemplo de solicitud:
    ```json
    {
        "username": "testuser",
        "firstname": "Test",
        "lastname": "User",
        "email": "testuser@example.com",
        "password": "Test@123"
    }
    ```
    """
    show(user)
    try:
        moodle_user_payload = user.to_moodle_user()
        moodle_user = moodle_controller.users.create_user(moodle_user_payload)
        response = MoodleUserRead.from_moodle_response(moodle_user, user)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}", response_model=MoodleUserRead)
async def get_moodle_user(user_id: int):
    """
    Obtiene un usuario de Moodle por su ID
    
    - **user_id**: ID del usuario en Moodle
    """
    try:
        show(user_id)
        show(type(user_id))
        moodle_user = moodle_controller.users.get_user_by_id(user_id)
        show(moodle_user)
        response = MoodleUserRead.from_moodle_get_response(moodle_user)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users", response_model=List[MoodleUserRead])
async def get_moodle_users(
    search_key: Optional[str] = Query(None, description="Campo de búsqueda: id, username, email, firstname, lastname"),
    search_value: Optional[str] = Query(None, description="Valor a buscar")
):
    """
    Obtiene usuarios de Moodle con criterios de búsqueda
    
    - **search_key**: Campo de búsqueda: id, username, email, firstname, lastname
    - **search_value**: Valor a buscar
    """
    try:
        criteria = []
        
        if search_key and search_value:
            criteria.append({"key": search_key, "value": search_value})
        else:
            # Criterio por defecto: obtener usuarios con auth manual
            criteria.append({"key": "auth", "value": "manual"})
        
        show(f"Criterios de búsqueda: {criteria}")
        moodle_users = moodle_controller.users.get_users(criteria)
        show(moodle_users)
        
        # Procesar respuesta
        if isinstance(moodle_users, dict) and 'users' in moodle_users:
            users_list = moodle_users['users']
            return [MoodleUserRead.from_user_data(user) for user in users_list]
        
        return []
        
    except Exception as e:
        show(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}", response_model=MoodleUserRead)
async def update_moodle_user(user_id: int, user_update: MoodleUserUpdate):
    """
    Actualiza un usuario de Moodle por su ID
    
    - **user_id**: ID del usuario en Moodle
    
    Ejemplo de solicitud:
    ```json
    {
        "user_id": 123,
        "user_update": {
            "username": "testuser",
            "firstname": "Test",
            "lastname": "User",
            "email": "testuser@example.com",
            "password": "Test@123"
        }
    }
    ```
    """
    try:
        # Convertir a diccionario excluyendo campos None
        updates = user_update.to_update_dict()
        
        # Validar que se envió al menos un campo para actualizar
        if not updates:
            raise HTTPException(status_code=400, detail="Debe proporcionar al menos un campo para actualizar")
        
        # Llamar al controlador con el diccionario de actualizaciones
        moodle_controller.users.update_user(user_id, updates)
        
        # Obtener el usuario actualizado para devolverlo
        updated_user = moodle_controller.users.get_user_by_id(user_id)
        return MoodleUserRead.from_moodle_get_response(updated_user)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/users/{user_id}", response_model=DeleteUserResponse)
async def delete_moodle_user(user_id: int):
    """
    Elimina un usuario de Moodle por su ID
    
    - **user_id**: ID del usuario en Moodle
    """
    try:
        # Verificar que el usuario existe (opcional)
        try:
            existing_user = moodle_controller.users.get_user_by_id(user_id)
            if not existing_user:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
        except Exception:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Eliminar el usuario
        moodle_controller.users.delete_user(user_id)
        
        # Devolver mensaje de confirmación
        return DeleteUserResponse(
            message="Usuario eliminado exitosamente",
            user_id=user_id
        )
        
    except HTTPException:
        raise 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
