from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session
from datetime import timedelta
from database.database import Services, get_services, get_session
from database.models.user import UserCreate, UserLogin, Token, UserRead, UserReadFilters, UserUpdate

from database.services.filter.filters import Filter
from database.services.auth.dependencies import get_current_user, require_admin_role, HTTPAuthorizationCredentials, security
from database.services.auth.security import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token
from exceptions import AppException

from jose import jwt
import os
from typing import List

from utils.logger import show

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/create-first-user", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_first_user(
        services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> UserRead:
    """Crea el primer usuario administrador"""
    try:
        
        users = services.userService.get_all_users(session)
        if users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existen usuarios en la base de datos"
            )
        # Crear el primer usuario administrador
        first_user_data = UserCreate(
            email="admin@gmail.com",
            password="Admin@123",
            rol="admin",
            name="Admin",
            lastname="User",
            document="12345678",
            phone="12345678"
        )
        
        first_user = services.userService.create_user(first_user_data, session)
        if not first_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear el primer usuario"
            )
        return first_user
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        show(f"Error al crear el primer usuario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    #current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> UserRead:
    """Registra un nuevo usuario"""
    try:
        # Verificar si ya existe usuario con ese email
        if services.userService.user_exists_by_email(user_data.email, session):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email ya registrado"
            )
        
        # Verificar si ya existe usuario con ese documento
        if services.userService.user_exists_by_document(user_data.document, session):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Documento ya registrado"
            )
        
        print("Paso verificación de documento")
        
        # Crear el usuario
        new_user = services.userService.create_user(user_data, session)
        
        show(f"Usuario creado: {new_user}")
        
        if not new_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear el usuario"
            )
        
        return new_user
        
    except ValueError as e:
        # Captura errores de validación (email/documento duplicado)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )


# Verificar que el usuario este confirmado y activo
@router.post("/login", response_model=Token)
async def login_user(
    login_data: UserLogin,
    
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> Token:
    """Inicia sesión y devuelve un token JWT"""
    try:
        # Usar email para autenticación
        user: UserRead = services.userService.authenticate_user(
            login_data.email,
            login_data.password,
            session
        )
        
        show(f"DEBUG login_user: Usuario autenticado: {user}")
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        if not user.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario inactivo"
            )
            
        if not user.confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Correo electrónico no confirmado"
            )
        
        # Crear token con email
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )


@router.post("/logout")
async def logout_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: UserRead = Depends(get_current_user),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
):
    """Cierra sesión agregando el token al blacklist"""
    try:
        from database.services.auth.security import blacklist_token
        from sqlmodel import text
        
        # Verificar que tenemos los servicios necesarios
        if not services or not services.redisService:
            print("DEBUG logout: Services o redisService no disponible")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Servicio de cache no disponible"
            )
        
        cache_service = services.redisService
        token = credentials.credentials
        
        # Decodificar token para obtener JTI
        payload = jwt.decode(token, os.environ.get("SECRET_KEY"), algorithms=["HS256"])
        jti = payload.get("jti")
        
        if not jti:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token sin JTI válido"
            )
        
        # Blacklist el token
        success = blacklist_token(token, cache_service, session)
        
        if success:
            blacklist_key = f"blacklist_{jti}"
            
            return {
                "message": "Sesión cerrada exitosamente",
                "jti": jti,
                "blacklist_key": blacklist_key
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error al cerrar sesión"
            )
            
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )
    except Exception as e:
        print(f"DEBUG logout: Error inesperado: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )

@router.post("/confirm/{userId}")
async def confirm_user_email(
    userId: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> UserRead:
    """Confirma el email de un usuario (solo administradores)"""
    try:
        confirmed_user = services.userService.get_user_by_id(userId, session)
        show(confirmed_user)
        if not confirmed_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        if confirmed_user.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario ya está activo"
            )
        confirmed_user = services.userService.confirm_user(userId, session)
        
        if not confirmed_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        return confirmed_user
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )


@router.post("/deactivate/{userId}")
async def deactivate_user(
    userId: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> UserRead:
    """Desactiva un usuario (solo administradores)"""
    try:
        # Verificar si el usuario existe
        user = services.userService.get_user_by_id(userId, session)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        # Desactivar el usuario
        if not user.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario ya está inactivo"
            )
        
        show(f"Desactivando usuario: {user}")
        deactivated_user = services.userService.deactivate_user(userId, session)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )
    
    if not deactivated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    return deactivated_user

@router.post("/activate/{userId}")
async def activate_user(
    userId: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> UserRead:
    """Activa un usuario (solo administradores)"""
    try:
        # Verificar si el usuario existe
        user = services.userService.get_user_by_id(userId, session)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        # Activar el usuario
        if user.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario ya está activo"
            )
        
        show(f"Activando usuario: {user}")
        activated_user = services.userService.activate_user(userId, session)
        if not activated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        return activated_user
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )
        

@router.get("/me", response_model=UserRead)
async def get_current_user_info(
    current_user: UserRead = Depends(get_current_user),
) -> UserRead:
    """Obtiene la información del usuario actual"""
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No estás autenticado"
            )
        return current_user
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )

@router.get("/users", response_model=List[UserRead])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[UserRead]:
    """Obtiene todos los usuarios (solo administradores)"""
    try:
        users = services.userService.get_all_users(session, skip=skip, limit=limit)
        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron usuarios"
            )
        return users
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )
        
@router.post("/filters/users", response_model=list[dict])
async def get_all_users(
    filters: Filter,
    #current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[UserRead]:
    """Obtiene todos los usuarios (solo administradores)"""
    try:
        users = services.userService.get_with_filters_clean(session, filters)
        if not users:
            return []
        show(users)
        return [user.model_dump() if hasattr(user, 'model_dump') else user for user in users]
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )
        
@router.put("/users/{userId}", response_model=UserRead)
async def update_user(
    userId: int,
    user_update: UserUpdate,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> UserRead:
    """Actualiza un usuario (solo administradores)"""
    try:
        return services.userService.update_user(userId, user_update, session)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )
        
@router.delete("/users/{userId}", response_model=UserRead)
async def delete_user(
    userId: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> UserRead:
    """Elimina un usuario (solo administradores)"""
    try:
        user = services.userService.delete_user(userId, session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        return user
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )