"""
Flujo Google OAuth 2.0 para el portal academico.
Solo permite cuentas @ctcsalto.edu.uy (validacion via hosted domain).
"""
import os
from typing import Optional

from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

from v2.auth.n8n_ou_client import n8n_ou_client, N8nOUClient
from v2.models.enums import RolUsuario


# Configuracion OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/v2/auth/google/callback")
GOOGLE_ALLOWED_DOMAIN = os.getenv("GOOGLE_ALLOWED_DOMAIN", "ctcsalto.edu.uy")

# Configurar authlib OAuth
oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
        "prompt": "select_account",
    },
)


def get_google_client():
    """Retorna el cliente OAuth de Google configurado."""
    return oauth.google


def validate_google_domain(user_info: dict) -> bool:
    """Valida que el usuario pertenezca al dominio institucional."""
    hd = user_info.get("hd", "")
    return hd == GOOGLE_ALLOWED_DOMAIN


def extract_user_data(user_info: dict) -> dict:
    """Extrae los datos relevantes del id_token de Google."""
    return {
        "google_id": user_info.get("sub"),
        "email": user_info.get("email", ""),
        "nombre": user_info.get("given_name", ""),
        "apellido": user_info.get("family_name", ""),
        "foto_url": user_info.get("picture"),
    }


def get_role_from_ou(email: str) -> tuple[Optional[str], Optional[RolUsuario]]:
    """
    Obtiene la OU del usuario via n8n y la mapea a un rol.

    Retorna (ou_path, rol), y el rol es None cuando no se pudo determinar.
    Quien llama tiene que distinguir "no se sabe" de "es estudiante": el rol
    se re-escribe en cada login, asi que tomar el default cuando la consulta
    falla degrada a estudiante a todos los que entren.
    """
    ou_path = n8n_ou_client.get_user_ou(email)
    rol = N8nOUClient.ou_to_rol(ou_path)
    return ou_path, rol


def lookup_moodle_id(email: str) -> Optional[int]:
    """
    Busca el moodle_id del usuario usando el controller existente.
    Retorna None si no se encuentra o hay error.
    """
    try:
        from external_services.moodle_api.controllers.moodle_user_controller import MoodleUserController
        controller = MoodleUserController()
        result = controller.get_users_by_field("email", email)

        if result and isinstance(result, list) and len(result) > 0:
            user_data = result[0]
            if isinstance(user_data, dict):
                return user_data.get("id")
            if hasattr(user_data, "id"):
                return user_data.id

        return None
    except Exception as e:
        print(f"[WARN] No se pudo obtener moodle_id para {email}: {e}")
        return None
