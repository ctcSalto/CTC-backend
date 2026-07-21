"""
Tests del sistema de autenticacion Google OAuth v2.

Cubre:
- Creacion y verificacion de tokens JWT v2
- Validacion de dominio institucional
- Mapeo OU → Rol
- Extraccion de datos de Google
- Token expirado / invalido
- Blacklist de tokens (mock Redis)
"""
import os
import pytest
from datetime import timedelta
from unittest.mock import MagicMock, patch
from jose import jwt

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")

from v2.auth.security import (
    create_v2_token, verify_v2_token, blacklist_v2_token,
    SECRET_KEY, ALGORITHM,
)
from v2.auth.google_oauth import (
    validate_google_domain, extract_user_data,
)
from v2.auth.n8n_ou_client import N8nOUClient, OU_TO_ROL
from v2.models.enums import RolUsuario


# ══════════════════════════════════════════════════════════════════════════════
# JWT v2: Creacion y verificacion
# ══════════════════════════════════════════════════════════════════════════════

class TestJWTCreacion:
    """Creacion de tokens JWT v2."""

    def test_crear_token_basico(self):
        """Token se crea con los claims correctos."""
        token = create_v2_token(
            email="juan@ctcsalto.edu.uy",
            usuario_id=1,
            rol="estudiante",
        )
        assert token is not None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "juan@ctcsalto.edu.uy"
        assert payload["usuario_id"] == 1
        assert payload["rol"] == "estudiante"
        assert payload["system"] == "v2"
        assert "jti" in payload
        assert "exp" in payload

    def test_crear_token_con_expiracion_custom(self):
        """Token respeta expiracion personalizada."""
        token = create_v2_token(
            email="test@ctcsalto.edu.uy",
            usuario_id=2,
            rol="docente",
            expires_delta=timedelta(minutes=5),
        )
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["rol"] == "docente"

    def test_crear_token_cada_rol(self):
        """Tokens se crean correctamente para cada rol."""
        for rol in RolUsuario:
            token = create_v2_token(
                email=f"{rol.value}@ctcsalto.edu.uy",
                usuario_id=10,
                rol=rol.value,
            )
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            assert payload["rol"] == rol.value

    def test_tokens_tienen_jti_unico(self):
        """Cada token tiene un jti diferente."""
        t1 = create_v2_token("a@ctcsalto.edu.uy", 1, "estudiante")
        t2 = create_v2_token("a@ctcsalto.edu.uy", 1, "estudiante")
        p1 = jwt.decode(t1, SECRET_KEY, algorithms=[ALGORITHM])
        p2 = jwt.decode(t2, SECRET_KEY, algorithms=[ALGORITHM])
        assert p1["jti"] != p2["jti"]


class TestJWTVerificacion:
    """Verificacion de tokens JWT v2."""

    def test_verificar_token_valido(self):
        """Token valido se decodifica correctamente."""
        token = create_v2_token("juan@ctcsalto.edu.uy", 1, "estudiante")
        payload = verify_v2_token(token)
        assert payload["sub"] == "juan@ctcsalto.edu.uy"
        assert payload["usuario_id"] == 1

    def test_rechazar_token_expirado(self):
        """Token expirado lanza HTTPException 401."""
        from fastapi import HTTPException
        token = create_v2_token(
            "test@ctcsalto.edu.uy", 1, "estudiante",
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(HTTPException) as exc_info:
            verify_v2_token(token)
        assert exc_info.value.status_code == 401

    def test_rechazar_token_firma_invalida(self):
        """Token con firma incorrecta falla."""
        from fastapi import HTTPException
        token = jwt.encode(
            {"sub": "x@ctcsalto.edu.uy", "system": "v2", "usuario_id": 1, "rol": "estudiante"},
            "clave-incorrecta",
            algorithm=ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc_info:
            verify_v2_token(token)
        assert exc_info.value.status_code == 401

    def test_rechazar_token_sin_system_v2(self):
        """Token sin claim system=v2 es rechazado."""
        from fastapi import HTTPException
        token = jwt.encode(
            {"sub": "x@ctcsalto.edu.uy", "usuario_id": 1, "rol": "estudiante", "system": "v1"},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc_info:
            verify_v2_token(token)
        assert exc_info.value.status_code == 401


class _FakeRedis:
    """
    Doble de RedisService. Imita su contrato real, incluido el detalle que
    importa: exists() se traga los errores y devuelve False, asi que "Redis
    caido" y "la clave no existe" se ven identicos desde afuera.
    """
    def __init__(self, disponible=True, revocados=()):
        self.disponible = disponible
        self.revocados = set(revocados)

    def test_connection(self):
        return self.disponible

    def exists(self, key, session=None):
        if not self.disponible:
            return False  # tal cual el real: falla silenciosa
        return key in self.revocados


class TestBlacklistFallaCerrado:
    """
    La blacklist debe fallar CERRADO. El logout es la unica forma de cortar
    acceso antes de que venza el token, asi que no puede quedar deshabilitado
    silenciosamente cuando Redis no responde.
    """

    def test_token_revocado_es_rechazado(self):
        from fastapi import HTTPException
        token = create_v2_token("juan@ctcsalto.edu.uy", 1, "estudiante")
        jti = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["jti"]
        redis = _FakeRedis(revocados=[f"blacklist_{jti}"])

        with pytest.raises(HTTPException) as exc_info:
            verify_v2_token(token, redis)
        assert exc_info.value.status_code == 401

    def test_token_no_revocado_pasa(self):
        token = create_v2_token("juan@ctcsalto.edu.uy", 1, "estudiante")
        payload = verify_v2_token(token, _FakeRedis())
        assert payload["sub"] == "juan@ctcsalto.edu.uy"

    def test_redis_caido_rechaza_en_vez_de_dejar_pasar(self):
        """
        Con Redis caido no podemos saber si el token fue revocado. Antes esto
        dejaba pasar cualquier token revocado hasta su expiracion.
        """
        from fastapi import HTTPException
        token = create_v2_token("juan@ctcsalto.edu.uy", 1, "estudiante")

        with pytest.raises(HTTPException) as exc_info:
            verify_v2_token(token, _FakeRedis(disponible=False))
        assert exc_info.value.status_code == 503

    def test_redis_caido_no_deja_entrar_token_revocado(self):
        """El caso concreto que motivo el fix: token revocado + Redis caido."""
        from fastapi import HTTPException
        token = create_v2_token("juan@ctcsalto.edu.uy", 1, "estudiante")
        jti = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["jti"]
        redis = _FakeRedis(disponible=False, revocados=[f"blacklist_{jti}"])

        with pytest.raises(HTTPException):
            verify_v2_token(token, redis)

    def test_rechazar_token_sin_email(self):
        """Token sin claim sub (email) es rechazado."""
        from fastapi import HTTPException
        token = jwt.encode(
            {"system": "v2", "usuario_id": 1, "rol": "estudiante"},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc_info:
            verify_v2_token(token)
        assert exc_info.value.status_code == 401


class TestJWTBlacklist:
    """Blacklist de tokens via Redis."""

    def test_blacklist_token_valido(self):
        """Token se agrega al blacklist correctamente."""
        token = create_v2_token("test@ctcsalto.edu.uy", 1, "estudiante")
        mock_redis = MagicMock()
        mock_redis.client = MagicMock()

        result = blacklist_v2_token(token, mock_redis)
        assert result is True
        mock_redis.client.set.assert_called_once()
        call_args = mock_redis.client.set.call_args
        assert call_args[0][0].startswith("blacklist_")

    def test_verificar_token_en_blacklist(self):
        """Token en blacklist es rechazado."""
        from fastapi import HTTPException
        token = create_v2_token("test@ctcsalto.edu.uy", 1, "estudiante")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload["jti"]

        mock_redis = MagicMock()
        mock_redis.exists.return_value = True

        with pytest.raises(HTTPException) as exc_info:
            verify_v2_token(token, redis_service=mock_redis)
        assert exc_info.value.status_code == 401
        assert "revocado" in exc_info.value.detail.lower()

    def test_token_no_en_blacklist_pasa(self):
        """Token no en blacklist es aceptado."""
        token = create_v2_token("test@ctcsalto.edu.uy", 1, "estudiante")
        mock_redis = MagicMock()
        mock_redis.exists.return_value = False

        payload = verify_v2_token(token, redis_service=mock_redis)
        assert payload["sub"] == "test@ctcsalto.edu.uy"

    def test_redis_caido_bloquea(self):
        """
        Si Redis no responde, el token se rechaza con 503.

        Este test antes se llamaba `test_redis_caido_no_bloquea` y afirmaba lo
        contrario ("Redis es no critico, el token pasa igual"). Eso convertia un
        agujero de seguridad en comportamiento esperado: con Redis caido, todo
        token revocado volvia a ser valido hasta expirar. Redis SI es critico
        para la blacklist, porque el logout es la unica forma de cortar acceso
        antes del vencimiento.
        """
        from fastapi import HTTPException
        token = create_v2_token("test@ctcsalto.edu.uy", 1, "estudiante")
        mock_redis = MagicMock()
        mock_redis.test_connection.return_value = False
        mock_redis.exists.side_effect = ConnectionError("Redis down")

        with pytest.raises(HTTPException) as exc_info:
            verify_v2_token(token, redis_service=mock_redis)
        assert exc_info.value.status_code == 503


# ══════════════════════════════════════════════════════════════════════════════
# Google OAuth: Validacion de dominio
# ══════════════════════════════════════════════════════════════════════════════

class TestGoogleDominio:
    """Validacion del dominio institucional @ctcsalto.edu.uy."""

    def test_dominio_valido(self):
        """Email del dominio institucional es aceptado."""
        user_info = {"hd": "ctcsalto.edu.uy", "email": "juan@ctcsalto.edu.uy"}
        assert validate_google_domain(user_info) is True

    def test_dominio_invalido_gmail(self):
        """Email de Gmail es rechazado."""
        user_info = {"hd": "gmail.com", "email": "juan@gmail.com"}
        assert validate_google_domain(user_info) is False

    def test_dominio_invalido_otro(self):
        """Email de otro dominio es rechazado."""
        user_info = {"hd": "otraescuela.edu.uy", "email": "juan@otraescuela.edu.uy"}
        assert validate_google_domain(user_info) is False

    def test_sin_hosted_domain(self):
        """Cuenta personal sin hd es rechazada."""
        user_info = {"email": "juan@gmail.com"}
        assert validate_google_domain(user_info) is False

    def test_hd_vacio(self):
        """hd vacio es rechazado."""
        user_info = {"hd": "", "email": "juan@ctcsalto.edu.uy"}
        assert validate_google_domain(user_info) is False


# ══════════════════════════════════════════════════════════════════════════════
# Google OAuth: Extraccion de datos
# ══════════════════════════════════════════════════════════════════════════════

class TestExtractUserData:
    """Extraccion de datos del id_token de Google."""

    def test_datos_completos(self):
        """Extrae todos los campos correctamente."""
        user_info = {
            "sub": "google123",
            "email": "juan@ctcsalto.edu.uy",
            "given_name": "Juan",
            "family_name": "Perez",
            "picture": "https://lh3.google.com/foto.jpg",
        }
        data = extract_user_data(user_info)
        assert data["google_id"] == "google123"
        assert data["email"] == "juan@ctcsalto.edu.uy"
        assert data["nombre"] == "Juan"
        assert data["apellido"] == "Perez"
        assert data["foto_url"] == "https://lh3.google.com/foto.jpg"

    def test_datos_parciales(self):
        """Maneja campos faltantes con defaults vacios."""
        user_info = {"sub": "google456"}
        data = extract_user_data(user_info)
        assert data["google_id"] == "google456"
        assert data["email"] == ""
        assert data["nombre"] == ""
        assert data["apellido"] == ""
        assert data["foto_url"] is None


# ══════════════════════════════════════════════════════════════════════════════
# Mapeo OU → Rol
# ══════════════════════════════════════════════════════════════════════════════

class TestOUMapeo:
    """Mapeo de Unidad Organizativa de Google a rol del sistema."""

    def test_ou_alumnos(self):
        """OU /Alumnos mapea a ESTUDIANTE."""
        assert N8nOUClient.ou_to_rol("/Alumnos") == RolUsuario.ESTUDIANTE

    def test_ou_docentes(self):
        """OU /Equipo Docente mapea a DOCENTE."""
        assert N8nOUClient.ou_to_rol("/Equipo Docente") == RolUsuario.DOCENTE

    def test_ou_administracion(self):
        """OU /Administración y Ventas mapea a ADMINISTRATIVO."""
        assert N8nOUClient.ou_to_rol("/Administración y Ventas") == RolUsuario.ADMINISTRATIVO

    def test_ou_subnivel_alumnos(self):
        """OU con subnivel /Alumnos/2026 mapea a ESTUDIANTE."""
        assert N8nOUClient.ou_to_rol("/Alumnos/2026") == RolUsuario.ESTUDIANTE

    def test_ou_subnivel_docente(self):
        """OU con subnivel /Equipo Docente/Informática mapea a DOCENTE."""
        assert N8nOUClient.ou_to_rol("/Equipo Docente/Informática") == RolUsuario.DOCENTE

    def test_ou_desconocida(self):
        """OU no reconocida defaultea a ESTUDIANTE."""
        assert N8nOUClient.ou_to_rol("/Otra/OU") == RolUsuario.ESTUDIANTE

    def test_ou_none(self):
        """OU None defaultea a ESTUDIANTE."""
        assert N8nOUClient.ou_to_rol(None) == RolUsuario.ESTUDIANTE

    def test_ou_vacia(self):
        """OU vacía defaultea a ESTUDIANTE."""
        assert N8nOUClient.ou_to_rol("") == RolUsuario.ESTUDIANTE


# ══════════════════════════════════════════════════════════════════════════════
# n8n client: mock del servicio
# ══════════════════════════════════════════════════════════════════════════════

class TestN8nClient:
    """Tests del cliente n8n con mocks."""

    @patch("v2.auth.n8n_ou_client.requests.request")
    def test_get_user_ou_exitoso(self, mock_request):
        """Retorna OU cuando n8n responde correctamente."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"orgUnitPath": "/Alumnos"}
        mock_request.return_value = mock_response

        client = N8nOUClient()
        ou = client.get_user_ou("juan@ctcsalto.edu.uy")
        assert ou == "/Alumnos"

    @patch("v2.auth.n8n_ou_client.requests.request")
    def test_get_user_ou_error_http(self, mock_request):
        """Retorna None si n8n devuelve error HTTP."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_request.return_value = mock_response

        client = N8nOUClient()
        ou = client.get_user_ou("juan@ctcsalto.edu.uy")
        assert ou is None

    @patch("v2.auth.n8n_ou_client.requests.request")
    def test_get_user_ou_timeout(self, mock_request):
        """Retorna None si n8n hace timeout."""
        import requests
        mock_request.side_effect = requests.exceptions.Timeout("timeout")

        client = N8nOUClient()
        ou = client.get_user_ou("juan@ctcsalto.edu.uy")
        assert ou is None

    @patch("v2.auth.n8n_ou_client.requests.request")
    def test_get_user_ou_connection_error(self, mock_request):
        """Retorna None si no hay conexion con n8n."""
        import requests
        mock_request.side_effect = requests.exceptions.ConnectionError("no connection")

        client = N8nOUClient()
        ou = client.get_user_ou("juan@ctcsalto.edu.uy")
        assert ou is None

    @patch("v2.auth.n8n_ou_client.requests.request")
    def test_get_user_ou_respuesta_string(self, mock_request):
        """Soporta respuesta en formato string."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = "/Equipo Docente"
        mock_request.return_value = mock_response

        client = N8nOUClient()
        ou = client.get_user_ou("docente@ctcsalto.edu.uy")
        assert ou == "/Equipo Docente"
