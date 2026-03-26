"""
Endpoints de Google Workspace API vía n8n
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

logger = logging.getLogger(__name__)

from database.models.user import UserRead
from database.services.auth.dependencies import require_admin_role
from external_services.google.google_service import google_workspace_service
from external_services.google.utils import generate_secure_password
from external_services.google.notification_service import send_credentials_notification

router = APIRouter(
    prefix="/google/test",
    tags=["Google Workspace"]
)


# ========== Schemas ==========

class CreateGoogleAccountRequest(BaseModel):
    """Schema para crear cuenta de Google"""
    primaryEmail: EmailStr = Field(..., description="Email del usuario @ctcsalto.edu.uy")
    givenName: str = Field(..., min_length=1, max_length=50, description="Nombre")
    familyName: str = Field(..., min_length=1, max_length=50, description="Apellido")
    orgUnitPath: str = Field(default="/Alumnos", description="Unidad organizativa")
    generatePassword: bool = Field(default=True, description="Generar contraseña automáticamente")
    password: Optional[str] = Field(None, description="Contraseña personalizada (opcional)")


class CreateAccountAndNotifyRequest(BaseModel):
    """Schema para crear cuenta y enviar notificación"""
    primaryEmail: EmailStr = Field(..., description="Email del usuario @ctcsalto.edu.uy")
    givenName: str = Field(..., min_length=1, max_length=50, description="Nombre")
    familyName: str = Field(..., min_length=1, max_length=50, description="Apellido")
    orgUnitPath: str = Field(default="/Alumnos", description="Unidad organizativa")
    notificationEmail: EmailStr = Field(..., description="Email personal para enviar credenciales")
    password: Optional[str] = Field(None, description="Contraseña personalizada (opcional)")


class UpdateGoogleAccountRequest(BaseModel):
    """Schema para actualizar cuenta de Google"""
    primaryEmail: EmailStr = Field(..., description="Email del usuario")
    givenName: Optional[str] = Field(None, min_length=1, max_length=50)
    familyName: Optional[str] = Field(None, min_length=1, max_length=50)
    orgUnitPath: Optional[str] = None
    suspended: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, description="Nueva contraseña (mínimo 8 caracteres)")


class UserEmailRequest(BaseModel):
    """Schema para peticiones que solo requieren email"""
    primaryEmail: EmailStr = Field(..., description="Email del usuario")


class AddToGroupRequest(BaseModel):
    """Schema para agregar/remover usuario de grupo"""
    primaryEmail: EmailStr = Field(..., description="Email del usuario")
    groupId: str = Field(..., description="ID del grupo o email del grupo")


class CreateGroupRequest(BaseModel):
    """Schema para crear grupo"""
    groupEmail: EmailStr = Field(..., description="Email del grupo")
    groupName: str = Field(..., min_length=1, description="Nombre del grupo")
    description: Optional[str] = Field(None, description="Descripción del grupo")


class GroupIdRequest(BaseModel):
    """Schema para peticiones que requieren ID o email de grupo"""
    groupId: str = Field(..., description="ID del grupo o email del grupo")


class UpdateGroupRequest(BaseModel):
    """Schema para actualizar grupo"""
    groupId: str = Field(..., description="ID del grupo o email del grupo")
    name: Optional[str] = Field(None, description="Nuevo nombre del grupo")
    description: Optional[str] = Field(None, description="Nueva descripción")
    email: Optional[EmailStr] = Field(None, description="Nuevo email del grupo")


class GroupEmailRequest(BaseModel):
    """Schema para peticiones que requieren email de grupo"""
    groupEmail: EmailStr = Field(..., description="Email del grupo")


# ========== Endpoints de Usuarios ==========

@router.post("/create-account", status_code=status.HTTP_201_CREATED)
async def create_google_account(
    request: CreateGoogleAccountRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Crear una cuenta de Google Workspace
    """
    try:
        password = request.password if request.password else generate_secure_password(12)

        result = google_workspace_service.create_google_account(
            primary_email=request.primaryEmail,
            given_name=request.givenName,
            family_name=request.familyName,
            password=password,
            org_unit_path=request.orgUnitPath
        )

        return {
            "status": "success",
            "message": "Usuario creado exitosamente en Google Workspace",
            "data": result,
            "temporaryPassword": password if request.generatePassword else None
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.post("/create-account-and-notify", status_code=status.HTTP_201_CREATED)
async def create_account_and_notify(
    request: CreateAccountAndNotifyRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Crear cuenta de Google Workspace y enviar credenciales por email.

    Crea la cuenta y luego envía un email al correo personal del usuario
    con las credenciales de acceso via n8n.
    """
    try:
        password = request.password if request.password else generate_secure_password(12)

        result = google_workspace_service.create_google_account(
            primary_email=request.primaryEmail,
            given_name=request.givenName,
            family_name=request.familyName,
            password=password,
            org_unit_path=request.orgUnitPath
        )

        notification_sent = False
        notification_error = None
        try:
            send_credentials_notification(
                nuevo_correo=request.primaryEmail,
                nueva_contrasena=password,
                firstname=request.givenName,
                lastname=request.familyName,
                email_original=request.notificationEmail,
            )
            notification_sent = True
        except Exception as e:
            notification_error = str(e)

        return {
            "status": "success",
            "message": "Usuario creado exitosamente en Google Workspace",
            "data": result,
            "temporaryPassword": password,
            "notificationSent": notification_sent,
            "notificationError": notification_error,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.post("/update-account")
async def update_google_account(
    request: UpdateGoogleAccountRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Actualizar una cuenta de Google Workspace
    """
    try:
        result = google_workspace_service.update_google_account(
            user_email=request.primaryEmail,
            given_name=request.givenName,
            family_name=request.familyName,
            org_unit_path=request.orgUnitPath,
            suspended=request.suspended,
            password=request.password
        )

        return {
            "status": "success",
            "message": "Usuario actualizado exitosamente",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error en update-account para {request.primaryEmail}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.post("/delete-account")
async def delete_google_account(
    request: UserEmailRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Eliminar una cuenta de Google Workspace

    CUIDADO: Esta operación elimina permanentemente el usuario.
    """
    try:
        result = google_workspace_service.delete_google_account(
            user_email=request.primaryEmail
        )

        return {
            "status": "success",
            "message": "Usuario eliminado exitosamente de Google Workspace",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.post("/suspend-account")
async def suspend_google_account(
    request: UserEmailRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Suspender una cuenta de Google Workspace
    """
    try:
        result = google_workspace_service.suspend_google_account(
            user_email=request.primaryEmail
        )

        return {
            "status": "success",
            "message": "Usuario suspendido exitosamente",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.post("/unsuspend-account")
async def unsuspend_google_account(
    request: UserEmailRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Reactivar una cuenta suspendida de Google Workspace
    """
    try:
        result = google_workspace_service.unsuspend_google_account(
            user_email=request.primaryEmail
        )

        return {
            "status": "success",
            "message": "Usuario reactivado exitosamente",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.post("/get-account")
async def get_google_account(
    request: UserEmailRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Obtener información de una cuenta de Google Workspace
    """
    try:
        result = google_workspace_service.get_google_account(
            user_email=request.primaryEmail
        )

        return {
            "status": "success",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.get("/list-accounts")
async def list_google_accounts(
    max_results: int = 100,
    page_token: Optional[str] = None,
    query: Optional[str] = None,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Listar cuentas de Google Workspace

    Parámetros:
    - max_results: Número máximo de resultados (default: 100)
    - page_token: Token para paginación
    - query: Filtro de búsqueda (opcional)
    """
    try:
        result = google_workspace_service.list_google_accounts(
            max_results=max_results,
            page_token=page_token,
            query=query
        )

        return {
            "status": "success",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


# ========== Endpoints de Grupos ==========

@router.post("/add-to-group")
async def add_user_to_group(
    request: AddToGroupRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Agregar usuario a un grupo de Google Workspace
    """
    try:
        result = google_workspace_service.add_user_to_group(
            user_email=request.primaryEmail,
            group_id=request.groupId
        )

        return {
            "status": "success",
            "message": f"Usuario agregado al grupo {request.groupId}",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.post("/remove-from-group")
async def remove_user_from_group(
    request: AddToGroupRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Remover usuario de un grupo de Google Workspace
    """
    try:
        result = google_workspace_service.remove_user_from_group(
            user_email=request.primaryEmail,
            group_id=request.groupId
        )

        return {
            "status": "success",
            "message": f"Usuario removido del grupo {request.groupId}",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.post("/create-group", status_code=status.HTTP_201_CREATED)
async def create_google_group(
    request: CreateGroupRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Crear un grupo en Google Workspace
    """
    try:
        result = google_workspace_service.create_google_group(
            group_email=request.groupEmail,
            group_name=request.groupName,
            description=request.description
        )

        return {
            "status": "success",
            "message": "Grupo creado exitosamente",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.get("/list-groups")
async def list_google_groups(
    max_results: int = 100,
    page_token: Optional[str] = None,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Listar grupos de Google Workspace

    Parámetros:
    - max_results: Número máximo de resultados (default: 100)
    - page_token: Token para paginación
    """
    try:
        result = google_workspace_service.list_google_groups(
            max_results=max_results,
            page_token=page_token
        )

        return {
            "status": "success",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.post("/get-group")
async def get_google_group(
    request: GroupIdRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Obtener información de un grupo de Google Workspace
    """
    try:
        result = google_workspace_service.get_google_group(
            group_id=request.groupId
        )

        return {
            "status": "success",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.post("/update-group")
async def update_google_group(
    request: UpdateGroupRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Actualizar un grupo de Google Workspace
    """
    try:
        result = google_workspace_service.update_google_group(
            group_id=request.groupId,
            name=request.name,
            description=request.description,
            email=request.email
        )

        return {
            "status": "success",
            "message": "Grupo actualizado exitosamente",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.post("/delete-group")
async def delete_google_group(
    request: GroupIdRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Eliminar un grupo de Google Workspace

    CUIDADO: Esta operación elimina permanentemente el grupo.
    """
    try:
        result = google_workspace_service.delete_google_group(
            group_id=request.groupId
        )

        return {
            "status": "success",
            "message": "Grupo eliminado exitosamente",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.post("/list-group-members")
async def list_group_members(
    request: GroupEmailRequest,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Listar miembros de un grupo de Google Workspace
    """
    try:
        result = google_workspace_service.list_group_members(
            group_email=request.groupEmail
        )

        return {
            "status": "success",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


# ========== Utilidades ==========

@router.get("/generate-password")
async def generate_password(
    length: int = 12,
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Generar una contraseña segura aleatoria
    """
    try:
        if length < 8:
            length = 8
        if length > 50:
            length = 50

        password = generate_secure_password(length)

        return {
            "status": "success",
            "password": password,
            "length": len(password),
            "requirements": {
                "minLength": 8,
                "hasUppercase": any(c.isupper() for c in password),
                "hasNumber": any(c.isdigit() for c in password),
                "hasSpecialChar": any(c in '@.*$' for c in password)
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando contraseña: {str(e)}"
        )
