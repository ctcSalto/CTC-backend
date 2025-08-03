from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from sqlmodel import Session
import os
import uuid
from datetime import datetime, timezone
from database.models.user import TokenData

from sqlmodel import Session, text


# Configuración desde variables de entorno
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña coincide con el hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Genera hash de la contraseña"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crea un token JWT con JTI único. Si expires_delta es None, el token no tiene expiración."""
    to_encode = data.copy()
    
    # Agregar JTI único para identificar el token
    jti = str(uuid.uuid4())
    to_encode.update({"jti": jti})

    if expires_delta is not None:
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, cache_service=None, session: Session = None) -> TokenData:
    """Verifica y decodifica un token JWT, incluyendo verificación de blacklist"""
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        jti: str = payload.get("jti")
        
        print(f"DEBUG verify_token: Token decodificado - email: {email}, jti: {jti}")
        
        if email is None:
            raise credentials_exception
            
        # Verificar blacklist si se proporcionan los servicios
        if cache_service and session and jti:
            print(f"DEBUG verify_token: Session ID: {id(session)}")
            blacklist_key = f"blacklist_{jti}"
            
            print(f"DEBUG verify_token: Verificando blacklist con key: {blacklist_key}")

            if cache_service.exists(blacklist_key, session):
                print(f"DEBUG verify_token: Token ESTÁ en blacklist - RECHAZADO")

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                print(f"DEBUG verify_token: Token NO está en blacklist")
        else:
            print(f"DEBUG verify_token: No se verificó blacklist - cache_service: {cache_service is not None}, session: {session is not None}, jti: {jti}")
        
        print(f"DEBUG verify_token: Creando TokenData")
        token_data = TokenData(email=email, jti=jti)
        return token_data
        
    except JWTError as e:
        print(f"DEBUG verify_token: Error JWT: {type(e).__name__}: {e}")
        raise credentials_exception
    except HTTPException:
        print(f"DEBUG verify_token: Re-lanzando HTTPException")
        raise
    except Exception as e:
        print(f"DEBUG verify_token: Error inesperado: {type(e).__name__}: {e}")
        raise credentials_exception


def blacklist_token(token: str, cache_service, session: Session) -> bool:
    """Agrega un token al blacklist"""
    try:
        print(f"DEBUG blacklist_token: Iniciando blacklist del token")
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
        
        print(f"DEBUG blacklist_token: jti: {jti}, exp: {exp}")

        if not jti:
            print("DEBUG blacklist_token: Token sin JTI válido")
            return False
            
        # Para tokens con expiración, calcular expires_at
        if exp:
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            print(f"DEBUG blacklist_token: Token expira en: {expires_at}")
        
        # Guardar en blacklist con la clave correcta
        blacklist_key = f"blacklist_{jti}"  # ✅ Clave consistente
        success = cache_service.set(blacklist_key, True, expires_at, session)
        session.commit()
        
        print(f"DEBUG blacklist_token: Token {'agregado' if success else 'NO agregado'} a blacklist con key: {blacklist_key}")
            # ✅ DEBUG: Verificar inmediatamente después de set()

        return success
        
    except JWTError as e:
        print(f"DEBUG blacklist_token: Error JWT: {e}")
        return False
    except Exception as e:
        print(f"DEBUG blacklist_token: Error inesperado: {e}")
        return False