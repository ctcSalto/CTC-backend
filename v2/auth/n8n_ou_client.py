"""
Cliente para obtener la Unidad Organizativa (OU) de Google
de un usuario via n8n webhook.

Sigue el patron de external_services/google/google_service.py
"""
import os
import requests
from typing import Optional

from v2.models.enums import RolUsuario


# Mapeo OU de Google -> Rol del sistema
OU_TO_ROL = {
    "/Alumnos": RolUsuario.ESTUDIANTE,
    "/Equipo Docente": RolUsuario.DOCENTE,
    "/Administración y Ventas": RolUsuario.ADMINISTRATIVO,
}


class N8nOUClient:
    def __init__(self):
        self.base_url = os.getenv('N8N_BASE_URL', '')
        self.api_token = os.getenv('N8N_API_TOKEN', '')
        self.header_name = os.getenv('N8N_HEADER_NAME', 'Authorization')
        self.timeout = int(os.getenv('N8N_TIMEOUT', '30'))
        self.ou_endpoint = os.getenv('N8N_OU_ENDPOINT', 'google-user-ou')

    def _get_headers(self) -> dict:
        return {
            self.header_name: self.api_token,
            'Content-Type': 'application/json'
        }

    def get_user_ou(self, email: str) -> Optional[str]:
        """
        Llama a n8n para obtener la OU de un usuario de Google.
        Retorna el orgUnitPath (ej: '/Alumnos') o None si falla.
        """
        url = f"{self.base_url}/{self.ou_endpoint}"

        try:
            response = requests.request(
                method='POST',
                url=url,
                headers=self._get_headers(),
                json={"email": email},
                timeout=self.timeout
            )

            if response.status_code >= 400:
                print(f"[WARN] n8n OU lookup fallo para {email}: {response.status_code} - {response.text}")
                return None

            data = response.json()

            # n8n puede devolver la OU en distintos formatos
            if isinstance(data, dict):
                return data.get("orgUnitPath") or data.get("ou") or data.get("orgUnit")
            if isinstance(data, str):
                return data

            return None

        except requests.exceptions.Timeout:
            print(f"[WARN] Timeout al consultar OU para {email}")
            return None
        except requests.exceptions.ConnectionError:
            print(f"[WARN] No se pudo conectar con n8n para OU de {email}")
            return None
        except Exception as e:
            print(f"[WARN] Error obteniendo OU para {email}: {e}")
            return None

    @staticmethod
    def ou_to_rol(ou_path: Optional[str]) -> Optional[RolUsuario]:
        """
        Mapea una OU de Google a un rol del sistema.

        Devuelve None cuando no se pudo determinar, que NO es lo mismo que
        "es estudiante". Antes devolvia ESTUDIANTE como default seguro, pero
        quien consume esto lo escribe en cada login: con la consulta de OU
        caida, eso degrada a estudiante a todo el que entre, incluidos los
        administrativos, y despues nadie puede devolverles el rol desde el
        portal porque esa pantalla pide ser administrativo.

        El default de minimo privilegio sigue existiendo, pero solo al crear
        un usuario nuevo. Ver `rol_o_default`.
        """
        if ou_path is None:
            return None

        # Busqueda exacta primero
        if ou_path in OU_TO_ROL:
            return OU_TO_ROL[ou_path]

        # Busqueda parcial (por si la OU tiene subniveles como /Alumnos/2026)
        for ou_prefix, rol in OU_TO_ROL.items():
            if ou_path.startswith(ou_prefix):
                return rol

        # La OU existe pero no esta mapeada: tampoco se sabe que es
        return None

    @staticmethod
    def rol_o_default(rol: Optional[RolUsuario]) -> RolUsuario:
        """Para crear un usuario nuevo: sin OU conocida, el minimo privilegio."""
        return rol if rol is not None else RolUsuario.ESTUDIANTE


# Singleton
n8n_ou_client = N8nOUClient()
