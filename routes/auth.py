from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session
from datetime import timedelta
from database.database import Services, get_services, get_session
from database.models.user import UserCreate, UserLogin, Token, UserRead
from database.services.auth.dependencies import get_current_active_user
from database.services.auth.security import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token
from exceptions import AppException
from exceptions.user_exeption import UserNotFoundException


router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate, 
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> UserRead:
    """Registra un nuevo usuario"""
    try:
        existing_user = services.userService.get_user_by_username(user_data.username, session)
        if existing_user:
            raise HTTPException(status_code=400, detail="El usuario ya existe")
  
        existing_email = services.userService.get_user_by_email(user_data.email, session)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email ya registrado"
            )
        
        new_user = services.userService.create_user(user_data, session)
        user_read = UserRead(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            full_name=new_user.full_name,
            role=new_user.role,
            is_active=new_user.is_active,
            created_at=new_user.created_at
        )
        if not user_read:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear el usuario"
            )
        return user_read
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/login", response_model=Token)
async def login_user(
    login_data: UserLogin,
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> Token:
    """Inicia sesión y devuelve un token JWT"""
    try:
        user = services.userService.authenticate_user(
            login_data.username, 
            login_data.password,
            session
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        
        # Verificar que el usuario esté activo
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        # Crear token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, 
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/generate-permanent-token", response_model=Token)
async def generate_permanent_token(current_user: UserRead = Depends(get_current_active_user)) -> Token:
    """Genera un token JWT permanentemente válido para usuarios con rol de administrador"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    access_token = create_access_token(data={"sub": current_user.username})
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@router.get("/me", response_model=UserRead)
async def get_current_user_info(
    current_user: UserRead = Depends(get_current_active_user),
) -> UserRead:
    """Obtiene la información del usuario actual"""
    return current_user