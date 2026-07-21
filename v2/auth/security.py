"""
Seguridad JWT para el portal academico v2.
Reutiliza SECRET_KEY y ALGORITHM de v1, pero agrega claim "system":"v2"
para distinguir tokens v1 (CMS) de v2 (portal academico).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status
import os
import uuid


SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))


def create_v2_token(
    email: str,
    usuario_id: int,
    rol: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Crea un JWT v2 con claims del portal academico."""
    to_encode = {
        "sub": email,
        "system": "v2",
        "usuario_id": usuario_id,
        "rol": rol,
        "jti": str(uuid.uuid4()),
    }

    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _redis_disponible(redis_service) -> bool:
    """
    Chequea conectividad real con Redis antes de confiar en su respuesta.

    Necesario porque RedisService.exists() atrapa sus propias excepciones y
    devuelve False, o sea que "Redis caido" y "la clave no existe" se ven igual
    desde afuera. Para la blacklist esa ambiguedad es justamente la peligrosa.
    """
    try:
        return bool(redis_service.test_connection())
    except Exception:
        return False


def verify_v2_token(token: str, redis_service=None) -> dict:
    """
    Decodifica y valida un JWT v2.
    Retorna el payload completo si es valido.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Verificar que sea un token v2
        if payload.get("system") != "v2":
            raise credentials_exception

        email = payload.get("sub")
        if email is None:
            raise credentials_exception

        # Verificar blacklist. Falla CERRADO: si no podemos consultar Redis, no
        # podemos saber si el token fue revocado, asi que lo rechazamos.
        #
        # Antes esto fallaba abierto (`except Exception: pass`), lo que significaba
        # que con Redis caido todos los tokens revocados volvian a ser validos hasta
        # expirar: un logout dejaba de tener efecto y un token robado que habias
        # revocado servia de nuevo. El logout es la unica forma de cortar acceso
        # antes del vencimiento, asi que no puede depender de que Redis este vivo.
        #
        # Ojo: RedisService.exists() se traga sus propias excepciones y devuelve
        # False, asi que no alcanza con envolver la llamada en un try. Hay que
        # verificar la conectividad por separado.
        jti = payload.get("jti")
        if redis_service and jti:
            if not _redis_disponible(redis_service):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="No se puede validar la sesion en este momento. Reintenta en unos minutos.",
                )
            if redis_service.exists(f"blacklist_{jti}"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token revocado",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return payload

    except JWTError:
        raise credentials_exception
    except HTTPException:
        raise


def blacklist_v2_token(token: str, redis_service) -> bool:
    """Agrega un token v2 al blacklist de Redis."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")

        if not jti:
            return False

        # Calcular TTL basado en la expiracion del token
        ttl = None
        if exp:
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            if expires_at <= now:
                return False  # Ya expiro
            ttl = int((expires_at - now).total_seconds())

        redis_service.client.set(f"blacklist_{jti}", "1", ex=ttl)
        return True

    except Exception:
        return False
