from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from sqlmodel import Session
import os
import uuid
import logging
from datetime import datetime, timezone
from database.models.user import TokenData

from sqlmodel import Session, text


logger = logging.getLogger(__name__)


# Configuración desde variables de entorno
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _redis_disponible(cache_service) -> bool:
    """
    Chequea conectividad real con Redis antes de confiar en su respuesta.

    Necesario porque RedisService.exists() atrapa sus propias excepciones y
    devuelve False: sin esto, "Redis caido" y "la clave no existe" se ven igual
    desde afuera, que es justo la ambiguedad peligrosa para la blacklist.
    """
    try:
        if hasattr(cache_service, "test_connection"):
            return bool(cache_service.test_connection())
        return True
    except Exception:
        return False

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

    # Marcar el sistema emisor. v1 (CMS) y v2 (portal academico) comparten
    # SECRET_KEY, asi que sin esta marca un token de un sistema es criptografica-
    # mente valido en el otro. v2 ya marcaba sus tokens con system="v2" y los
    # validaba; v1 no marcaba ni validaba, de modo que un token v2 servia en v1
    # para cualquier email que existiera en la tabla `user`.
    to_encode.setdefault("system", "v1")

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

        # Rechazar tokens emitidos por otro sistema (ver create_access_token).
        # Se acepta la ausencia del claim para no invalidar los tokens v1 que ya
        # estaban circulando cuando se agrego la marca; una vez que expiren todos
        # (ACCESS_TOKEN_EXPIRE_MINUTES) esto se puede endurecer a exigir "v1".
        sistema = payload.get("system")
        if sistema is not None and sistema != "v1":
            raise credentials_exception

        if email is None:
            raise credentials_exception

        # Verificar blacklist. Falla CERRADO, igual que v2: si no podemos consultar
        # Redis no sabemos si el token fue revocado, asi que lo rechazamos.
        #
        # Antes fallaba abierto — RedisService.exists() se traga sus excepciones y
        # devuelve False, asi que "Redis caido" y "token no revocado" eran
        # indistinguibles. Con Redis caido, todo token revocado volvia a valer
        # hasta expirar y el logout dejaba de tener efecto. Por eso hay que
        # verificar conectividad por separado antes de confiar en exists().
        if cache_service and session and jti:
            if not _redis_disponible(cache_service):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="No se puede validar la sesion en este momento. Reintenta en unos minutos.",
                )
            if cache_service.exists(f"blacklist_{jti}", session):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return TokenData(email=email, jti=jti)

    except JWTError:
        raise credentials_exception
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado en verify_token: {type(e).__name__}: {e}")
        raise credentials_exception


def blacklist_token(token: str, cache_service, session: Session) -> bool:
    """Agrega un token al blacklist"""
    try:
        
        # Verificar que cache_service esté disponible
        if not cache_service:
            return False
        
        # Test de conexión Redis
        if hasattr(cache_service, 'test_connection'):
            if not cache_service.test_connection():
                return False
        
        # Decodificar token
        SECRET_KEY = os.environ.get("SECRET_KEY")
        ALGORITHM = "HS256"  # Ajusta según tu configuración
        
        if not SECRET_KEY:
            return False
            
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
        

        if not jti:
            return False
        
        # Calcular expires_at
        expires_at = None
        if exp:
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            
            # Verificar que el token no haya expirado ya
            now = datetime.now(tz=timezone.utc)
            if expires_at <= now:
                return False
        else:
            # Si no hay exp, el token no expira - darle una expiración por defecto
            # Opcional: puedes darle 30 días o dejarlo None para permanente
            expires_at = None
        
        # Usar el método específico para blacklist
        success = cache_service.set_blacklist_token(jti, expires_at, session)
        
        
        if success:
            # Verificación inmediata
            is_blacklisted = cache_service.is_token_blacklisted(jti, session)
            
            if not is_blacklisted:
                return False
        
        # NO hacer commit aquí - Redis no necesita transacciones SQL
        # session.commit()  # ❌ Esto puede causar problemas
        
        return success
        
    except JWTError as e:
        return False
    except Exception as e:
        import traceback
        return False


def is_token_blacklisted(token: str, cache_service) -> bool:
    """Verifica si un token está en la blacklist"""
    try:
        
        if not cache_service:
            return False
        
        # Decodificar token para obtener JTI
        SECRET_KEY = os.environ.get("SECRET_KEY")
        ALGORITHM = "HS256"
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        jti = payload.get("jti")
        
        if not jti:
            return False
        
        # Verificar blacklist
        is_blacklisted = cache_service.is_token_blacklisted(jti)
        
        return is_blacklisted
        
    except JWTError as e:
        return False
    except Exception as e:
        return False