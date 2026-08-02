"""
Revocacion de tokens v2 (logout) y costo de validarlos.

Dos cosas cubiertas aca:

1. El logout nunca revoco nada. blacklist_v2_token escribia en
   `redis_service.client`, atributo que RedisService no tiene: el AttributeError
   lo tragaba el except y la funcion devolvia False siempre. El endpoint
   respondia 500 y el token seguia valido hasta vencer.

2. Validar un token costaba TRES idas a Redis: un ping propio para saber si
   estaba vivo, mas RedisService.exists(), que pinguea antes de consultar.
   Ahora se consulta el cliente directo: una sola ida, y la excepcion ya
   distingue "Redis caido" de "token no revocado".
"""
import pytest
from fastapi import HTTPException

from v2.auth.security import (
    create_v2_token, blacklist_v2_token, verify_v2_token, minutos_de_expiracion,
)


class ClienteCrudo:
    """Imita al cliente de redis-py: exists() va derecho, no pinguea."""

    def __init__(self, viajes):
        self.store = {}
        self.viajes = viajes

    def ping(self):
        self.viajes.append("ping")
        return True

    def set(self, key, value, ex=None):
        self.viajes.append("set")
        self.store[key] = (value, ex)
        return True

    def exists(self, key):
        self.viajes.append("exists")
        return 1 if key in self.store else 0


class RedisFalso:
    """
    Imita a RedisService. Su exists() pinguea antes de consultar, igual que el
    real: si el codigo lo usara en vez del cliente crudo, el conteo lo delata.
    """

    def __init__(self):
        self.viajes = []
        self.redis_client = ClienteCrudo(self.viajes)

    def exists(self, key, session=None):
        self.redis_client.ping()
        return bool(self.redis_client.exists(key))

    def test_connection(self):
        self.redis_client.ping()
        return True


class RedisCaido:
    """Cualquier acceso al cliente falla, como con el servidor abajo."""

    @property
    def redis_client(self):
        raise ConnectionError("Connection refused")


class RedisSinClienteCrudo:
    """Servicio que no expone redis_client: el bug original."""

    def exists(self, key, session=None):
        return False


@pytest.fixture(name="token")
def fixture_token():
    return create_v2_token("alumno@ctcsalto.edu.uy", 1, "estudiante")


class TestLogout:

    def test_revoca_el_token(self, token):
        """El caso que estaba roto: el logout tiene que invalidar el token."""
        redis = RedisFalso()

        assert verify_v2_token(token, redis)["sub"] == "alumno@ctcsalto.edu.uy"

        assert blacklist_v2_token(token, redis) is True

        with pytest.raises(HTTPException) as exc:
            verify_v2_token(token, redis)
        assert exc.value.status_code == 401
        assert exc.value.detail == "Token revocado"

    def test_escribe_la_clave_con_vencimiento(self, token):
        """El TTL evita que la blacklist crezca para siempre."""
        redis = RedisFalso()
        blacklist_v2_token(token, redis)

        claves = list(redis.redis_client.store)
        assert len(claves) == 1
        assert claves[0].startswith("blacklist_")

        _, ttl = redis.redis_client.store[claves[0]]
        assert ttl is not None and ttl > 0

    def test_falla_si_el_servicio_no_expone_el_cliente(self, token):
        """El bug original: devolvia False y el llamador respondia 500."""
        assert blacklist_v2_token(token, RedisSinClienteCrudo()) is False

    def test_falla_con_redis_caido(self, token):
        assert blacklist_v2_token(token, RedisCaido()) is False

    def test_un_token_ya_vencido_no_se_revoca(self):
        """Sin TTL positivo no hay nada que guardar."""
        from datetime import timedelta
        vencido = create_v2_token(
            "a@ctcsalto.edu.uy", 1, "estudiante",
            expires_delta=timedelta(seconds=-10),
        )
        redis = RedisFalso()

        assert blacklist_v2_token(vencido, redis) is False
        assert redis.redis_client.store == {}


class TestCostoDeValidar:

    def test_una_sola_ida_a_redis(self, token):
        """
        Eran tres por request autenticado. Si alguien vuelve a usar
        RedisService.exists() en vez del cliente crudo, aparece un ping y falla.
        """
        redis = RedisFalso()
        redis.viajes.clear()

        verify_v2_token(token, redis)

        assert redis.viajes == ["exists"], (
            f"Se esperaba una sola consulta y hubo {redis.viajes}"
        )

    def test_sin_redis_no_consulta_nada(self, token):
        """Sin servicio de Redis el token se valida igual, solo por firma."""
        assert verify_v2_token(token, None)["sub"] == "alumno@ctcsalto.edu.uy"


class TestDuracionDelToken:
    """
    La sesion del portal dura una jornada.

    Antes se leia ACCESS_TOKEN_EXPIRE_MINUTES, la del CMS, y en los entornos
    donde esa vale 4000 los tokens de alumnos duraban 66 horas.
    """

    def test_default_de_ocho_horas(self, monkeypatch):
        monkeypatch.delenv("V2_ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)
        assert minutos_de_expiracion() == 480

    def test_el_token_vence_a_las_ocho_horas(self, token):
        from datetime import datetime, timezone
        from jose import jwt
        from v2.auth.security import SECRET_KEY, ALGORITHM

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        faltan = datetime.fromtimestamp(payload["exp"], tz=timezone.utc) - datetime.now(timezone.utc)

        # Margen de un minuto por el tiempo de ejecucion del test
        assert 479 <= faltan.total_seconds() / 60 <= 480

    def test_ignora_la_variable_del_cms(self, monkeypatch):
        """Setear la del CMS no tiene que mover la sesion del portal."""
        monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "4000")
        monkeypatch.delenv("V2_ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)

        assert minutos_de_expiracion() == 480

    def test_se_puede_configurar_con_su_propia_variable(self, monkeypatch):
        monkeypatch.setenv("V2_ACCESS_TOKEN_EXPIRE_MINUTES", "120")

        assert minutos_de_expiracion() == 120

    def test_la_variable_propia_se_aplica_al_token(self, monkeypatch):
        """No alcanza con leerla: el token tiene que salir con esa vida."""
        from datetime import datetime, timezone
        from jose import jwt
        from v2.auth.security import SECRET_KEY, ALGORITHM

        monkeypatch.setenv("V2_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        corto = create_v2_token("a@ctcsalto.edu.uy", 1, "estudiante")

        payload = jwt.decode(corto, SECRET_KEY, algorithms=[ALGORITHM])
        faltan = datetime.fromtimestamp(payload["exp"], tz=timezone.utc) - datetime.now(timezone.utc)
        assert 59 <= faltan.total_seconds() / 60 <= 60


class TestFallaCerrado:

    def test_redis_caido_rechaza_el_token(self, token):
        """
        No se puede saber si fue revocado, asi que no se acepta. Fallar abierto
        significaria que un logout deja de tener efecto cuando Redis se cae.
        """
        with pytest.raises(HTTPException) as exc:
            verify_v2_token(token, RedisCaido())

        assert exc.value.status_code == 503
        assert "No se puede validar la sesion" in exc.value.detail

    def test_un_servicio_roto_tampoco_deja_pasar(self, token):
        """
        Un servicio que no expone el cliente es un error de programacion, pero
        el token no se acepta igual: no se pudo consultar la blacklist.
        """
        with pytest.raises(HTTPException) as exc:
            verify_v2_token(token, RedisSinClienteCrudo())

        assert exc.value.status_code == 503
