from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from external_services.moodle_api.models.user import MoodleUserCreate, MoodleUserRead, MoodleUserUpdate, DeleteUserResponse
from external_services.moodle_api.controllers.moodle_api_controller import MoodleController
from external_services.moodle_api.moodle_config import MoodleConfig
from utils.logger import show
from typing import List, Optional
import subprocess
import sys
import os

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


# ─── ENDPOINT PARA ACTUALIZAR FOTOS DE PERFIL ────────────────────────────────

def run_update_photos_script():
    """
    Ejecuta el script actualizar_fotos_perfil.py en un subproceso.
    Esta función se ejecuta en background para no bloquear el endpoint.
    """
    script_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..",
        "external_services", "moodle_api", "scripts", "actualizar_fotos_perfil.py"
    )

    try:
        show(f"Ejecutando script: {script_path}")
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutos máximo
        )

        if result.returncode == 0:
            show(f"Script completado exitosamente:\n{result.stdout}")
        else:
            show(f"Error en script:\n{result.stderr}")

    except subprocess.TimeoutExpired:
        show("Script excedió el tiempo límite de 10 minutos")
    except Exception as e:
        show(f"Error ejecutando script: {e}")


@router.post("/usuarios/actualizar-fotos-perfil")
async def actualizar_fotos_perfil(background_tasks: BackgroundTasks):
    """
    Actualiza las fotos de perfil de todos los usuarios en Moodle con el logo del instituto.

    Este endpoint ejecuta un proceso en background que:
    1. Obtiene todos los usuarios de Moodle
    2. Crea un ZIP con copias del logo CTC nombradas por username
    3. Sube el ZIP a Moodle usando Playwright
    4. Limpia archivos temporales

    **Nota**: El proceso se ejecuta en background y puede tardar varios minutos.
    La respuesta se devuelve inmediatamente, pero el proceso continúa ejecutándose.

    Returns:
        dict: Mensaje confirmando que el proceso se inició
    """
    try:
        # Agregar tarea en background
        background_tasks.add_task(run_update_photos_script)

        return {
            "message": "Proceso de actualización de fotos iniciado en background",
            "status": "processing",
            "note": "El proceso puede tardar varios minutos. Revisa los logs del servidor para ver el progreso."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al iniciar proceso: {str(e)}")
