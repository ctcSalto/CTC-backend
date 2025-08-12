from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database.database import Services, get_services, get_session
from .security import verify_token
from database.models.user import UserRead, UserRole
from sqlmodel import Session
from sqlalchemy.exc import SQLAlchemyError

from utils.logger import show

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> UserRead:
    """Obtiene el usuario actual basado en el token JWT con verificación de blacklist"""
    try:
        token = credentials.credentials
        cache_service = services.redisService
        
        # Verificar token incluyendo blacklist
        token_data = verify_token(token, cache_service, session)
        
        # Cambiar get_user_by_username por get_user_by_email ya que usamos email
        user_table = services.userService.get_user_by_email(token_data.email, session)
        
        if user_table is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user_table
        
    except HTTPException:
        # Re-lanzar HTTPExceptions sin modificar
        raise
        
    except SQLAlchemyError as e:
        # Error específico de base de datos
        show(f"Database error in get_current_user: {e}")
        session.rollback()  # Hacer rollback explícito
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error during authentication",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    except Exception as e:
        # Cualquier otro error
        show(f"Unexpected error in get_current_user: {e}")
        session.rollback()  # Hacer rollback explícito por seguridad
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(
    current_user: UserRead = Depends(get_current_user)
) -> UserRead:
    """Verifica que el usuario esté activo"""
    show(current_user)
    if not current_user.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Usuario inactivo"
        )
    return current_user

async def get_current_confirmed_user(
    current_user: UserRead = Depends(get_current_active_user)
) -> UserRead:
    """Verifica que el usuario esté confirmado"""
    if not current_user.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Correo electrónico no confirmado"
        )
    return current_user

# Funciones para roles específicos usando enum
def require_role(required_role: UserRole):
    """Función para requerir un rol específico"""
    async def role_checker(current_user: UserRead = Depends(get_current_confirmed_user)):
        if current_user.rol != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role.value}' required. Current user role: {current_user.rol.value}"
            )
        return current_user
    return role_checker

async def require_admin_role(current_user: UserRead = Depends(get_current_confirmed_user)):
    """Requiere rol de administrador"""
    if current_user.rol != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rol de administrador requerido"
        )
    return current_user

async def require_auth_user(current_user: UserRead = Depends(get_current_confirmed_user)):
    """Requiere rol de estudiante"""
    if current_user.rol not in [UserRole.STUDENT, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rol de estudiante requerido"
        )
    return current_user

async def require_student_role(current_user: UserRead = Depends(get_current_confirmed_user)):
    """Requiere rol de estudiante"""
    if current_user.rol != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rol de estudiante requerido"
        )
    return current_user

def require_roles(allowed_roles: list[UserRole]):
    """Función para permitir múltiples roles"""
    async def role_checker(current_user: UserRead = Depends(get_current_confirmed_user)):
        if current_user.rol not in allowed_roles:
            role_names = [role.value for role in allowed_roles]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of these roles required: {', '.join(role_names)}. Current role: {current_user.rol.value}"
            )
        return current_user
    return role_checker

# Funciones de conveniencia para casos comunes
async def require_admin_or_self(
    userId: int,
    current_user: UserRead = Depends(get_current_confirmed_user)
) -> UserRead:
    """Permite acceso si es admin o si es el mismo usuario"""
    if current_user.rol != UserRole.ADMIN and current_user.userId != userId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required or accessing own data"
        )
    return current_user

# Decoradores para endpoints específicos
require_any_authenticated = Depends(get_current_confirmed_user)
require_admin = Depends(require_admin_role)
require_student = Depends(require_student_role)
require_admin_or_student = Depends(require_roles([UserRole.ADMIN, UserRole.STUDENT]))