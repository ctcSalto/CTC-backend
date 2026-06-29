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

        # Verificar blacklist si Redis esta disponible
        jti = payload.get("jti")
        if redis_service and jti:
            try:
                if redis_service.exists(f"blacklist_{jti}"):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token revocado",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            except HTTPException:
                raise
            except Exception:
                pass  # Redis no disponible, continuar sin blacklist

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
