from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database.database import Services, get_services, get_session
from .security import verify_token
from database.models.user import UserRead
from sqlmodel import Session

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> UserRead:
    """Obtiene el usuario actual basado en el token JWT"""
    token = credentials.credentials
    token_data = verify_token(token)
    
    user_table = services.userService.get_user_by_username(token_data.username, session)
    if user_table is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_read = UserRead(
        id=user_table.id,
        username=user_table.username,
        email=user_table.email,
        full_name=user_table.full_name,
        role=user_table.role,
        is_active=user_table.is_active,
        created_at=user_table.created_at
    )
    
    return user_read

async def get_current_active_user(
    current_user: UserRead = Depends(get_current_user)
) -> UserRead:
    """Verifica que el usuario esté activo"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )
    return current_user

# Funciones para roles específicos
def require_role(required_role: str):
    """Función para requerir un rol específico"""
    async def role_checker(current_user: UserRead = Depends(get_current_active_user)):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required. Current user role: {current_user.role}"
            )
        return current_user
    return role_checker

async def require_admin_role(current_user: UserRead = Depends(get_current_active_user)):
    """Requiere rol de administrador"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required"
        )
    return current_user

def require_roles(allowed_roles: list[str]):
    """Función para permitir múltiples roles"""
    async def role_checker(current_user: UserRead = Depends(get_current_active_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of these roles required: {', '.join(allowed_roles)}. Current role: {current_user.role}"
            )
        return current_user
    return role_checker