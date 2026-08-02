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
# Variable propia de v2. Antes leia ACCESS_TOKEN_EXPIRE_MINUTES, la misma que v1,
# asi que setearla pensando en el portal academico (8h) le cambiaba la vida a los
# tokens del CMS (30 min). Fallback a la compartida para no romper entornos que
# solo tienen esa seteada.
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("V2_ACCESS_TOKEN_EXPIRE_MINUTES")
    or os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480")
)


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


def _cliente_redis(redis_service):
    """
    Cliente redis-py crudo detras del servicio.

    Se usa el cliente directo en vez de RedisService.exists() porque ese metodo
    atrapa sus propias excepciones y devuelve False: desde afuera "Redis caido"
    y "la clave no existe" se ven igual, y para una blacklist esa ambiguedad es
    justo la peligrosa. Yendo al cliente, una excepcion significa "no se pudo
    consultar" sin lugar a dudas.
    """
    cliente = getattr(redis_service, "redis_client", None)
    if cliente is None:
        raise AttributeError(
            "El servicio de Redis no expone redis_client: no se puede consultar "
            "la blacklist de tokens"
        )
    return cliente


def _token_revocado(redis_service, jti: str) -> bool:
    """
    True si el token esta en la blacklist.

    Levanta si Redis no se puede consultar; el llamador traduce eso a un 503.
    """
    return bool(_cliente_redis(redis_service).exists(f"blacklist_{jti}"))


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
        # Una sola ida a Redis. Antes eran TRES por request autenticado: un ping
        # propio para saber si Redis estaba vivo, mas RedisService.exists(), que
        # a su vez pinguea antes de consultar. Consultando el cliente directo, la
        # excepcion ya distingue "caido" de "no revocado" y el ping sobra.
        jti = payload.get("jti")
        if redis_service and jti:
            try:
                revocado = _token_revocado(redis_service, jti)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="No se puede validar la sesion en este momento. Reintenta en unos minutos.",
                )
            if revocado:
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
    """
    Agrega un token v2 al blacklist de Redis.

    Escribia en `redis_service.client`, atributo que RedisService no tiene: el
    AttributeError lo tragaba el except y la funcion devolvia False siempre. El
    logout de v2 nunca revoco nada — respondia 500 y el token seguia valido
    hasta vencer. El atributo correcto es `redis_client`.
    """
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

        _cliente_redis(redis_service).set(f"blacklist_{jti}", "1", ex=ttl)
        return True

    except Exception as e:
        # El llamador responde 500, pero sin esto el motivo no queda en ningun
        # lado y un error de programacion se ve igual que un Redis caido.
        print(f"[ERROR] blacklist_v2_token: no se pudo revocar el token: {e!r}")
        return False
