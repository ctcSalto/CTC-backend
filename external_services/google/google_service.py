"""
Servicio para interactuar con Google Workspace a través de n8n webhooks
"""
import os
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class GoogleWorkspaceService:
    """
    Servicio para gestionar usuarios y grupos de Google Workspace
    mediante webhooks de n8n
    """

    def __init__(self):
        self.base_url = os.getenv('N8N_BASE_URL', 'https://automatizaciones-n8n.vtu0xl.easypanel.host/webhook-test')
        self.api_token = os.getenv('N8N_API_TOKEN', 'MobuEZYKJfic3G4LoRbliS2u4IyLq1Aup7qQ3L9KCFORBJfDbVCAD090VPZDLZM3')
        self.header_name = os.getenv('N8N_HEADER_NAME', 'Authorization')  # Nombre del header de autenticación
        self.timeout = int(os.getenv('N8N_TIMEOUT', '30'))  # timeout en segundos

    def _get_headers(self) -> Dict[str, str]:
        """
        Genera los headers necesarios para las peticiones a n8n

        Returns:
            Dict con los headers de autenticación
        """
        # n8n Header Auth con nombre de header configurable
        return {
            self.header_name: self.api_token,
            'Content-Type': 'application/json'
        }

    def _make_request(
        self,
        endpoint: str,
        method: str = 'POST',
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Realiza una petición HTTP al webhook de n8n

        Args:
            endpoint: Endpoint del webhook (ej: 'createGoogleAccount')
            method: Método HTTP (POST, GET, PUT, DELETE)
            data: Datos a enviar en el body (para POST/PUT)

        Returns:
            Dict con la respuesta del servidor

        Raises:
            requests.exceptions.RequestException: Si la petición falla
            ValueError: Si la respuesta no es 200
        """
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_headers()

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                timeout=self.timeout
            )

            # Si el status code es 400 o mayor, levantar excepción
            if response.status_code >= 400:
                error_message = response.text
                try:
                    error_json = response.json()
                    error_message = error_json.get('message', error_message)
                except:
                    pass
                raise ValueError(f"Error en n8n webhook: {error_message}")

            # Intentar parsear JSON
            try:
                return response.json()
            except:
                return {"status": "success", "message": response.text}

        except requests.exceptions.Timeout:
            raise ValueError(f"Timeout al conectar con n8n (>{self.timeout}s)")
        except requests.exceptions.ConnectionError:
            raise ValueError("No se pudo conectar con n8n. Verifica que esté corriendo.")
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Error en la petición a n8n: {str(e)}")

    # ========== CRUD de Usuarios ==========

    def create_google_account(
        self,
        primary_email: str,
        given_name: str,
        family_name: str,
        password: str,
        org_unit_path: str = "/Alumnos"
    ) -> Dict[str, Any]:
        """
        Crea una cuenta de usuario en Google Workspace

        Args:
            primary_email: Email del usuario (ej: usuario@ctcsalto.edu.uy)
            given_name: Nombre del usuario
            family_name: Apellido del usuario
            password: Contraseña temporal (se fuerza cambio en primer login)
            org_unit_path: Unidad organizativa (default: /Alumnos)

        Returns:
            Dict con los datos del usuario creado

        Raises:
            ValueError: Si hay un error al crear el usuario
        """
        data = {
            "primaryEmail": primary_email,
            "givenName": given_name,
            "familyName": family_name,
            "password": password,
            "orgUnitPath": org_unit_path
        }

        return self._make_request('createGoogleAccount', method='POST', data=data)

    def update_google_account(
        self,
        user_email: str,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        org_unit_path: Optional[str] = None,
        suspended: Optional[bool] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Actualiza una cuenta de usuario en Google Workspace

        Args:
            user_email: Email del usuario a actualizar
            given_name: Nuevo nombre (opcional)
            family_name: Nuevo apellido (opcional)
            org_unit_path: Nueva unidad organizativa (opcional)
            suspended: Suspender/activar cuenta (opcional)
            password: Nueva contraseña (opcional)

        Returns:
            Dict con los datos del usuario actualizado
        """
        data = {"primaryEmail": user_email}

        if given_name:
            data["givenName"] = given_name
        if family_name:
            data["familyName"] = family_name
        if org_unit_path:
            data["orgUnitPath"] = org_unit_path
        if suspended is not None:
            data["suspended"] = suspended
        if password:
            data["password"] = password

        return self._make_request('updateGoogleAccount', method='POST', data=data)

    def delete_google_account(self, user_email: str) -> Dict[str, Any]:
        """
        Elimina una cuenta de usuario de Google Workspace

        Args:
            user_email: Email del usuario a eliminar

        Returns:
            Dict con confirmación de eliminación
        """
        data = {"primaryEmail": user_email}
        return self._make_request('deleteGoogleAccount', method='POST', data=data)

    def suspend_google_account(self, user_email: str) -> Dict[str, Any]:
        """
        Suspende una cuenta de usuario en Google Workspace

        Args:
            user_email: Email del usuario a suspender

        Returns:
            Dict con confirmación de suspensión
        """
        data = {"primaryEmail": user_email, "suspended": True}
        return self._make_request('updateGoogleAccount', method='POST', data=data)

    def unsuspend_google_account(self, user_email: str) -> Dict[str, Any]:
        """
        Reactiva una cuenta de usuario suspendida en Google Workspace

        Args:
            user_email: Email del usuario a reactivar

        Returns:
            Dict con confirmación de reactivación
        """
        data = {"primaryEmail": user_email, "suspended": False}
        return self._make_request('updateGoogleAccount', method='POST', data=data)

    def get_google_account(self, user_email: str) -> Dict[str, Any]:
        """
        Obtiene información de una cuenta de usuario de Google Workspace

        Args:
            user_email: Email del usuario

        Returns:
            Dict con los datos del usuario
        """
        data = {"primaryEmail": user_email}
        return self._make_request('getGoogleAccount', method='POST', data=data)

    def list_google_accounts(
        self,
        max_results: int = 100,
        page_token: Optional[str] = None,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lista usuarios de Google Workspace

        Args:
            max_results: Número máximo de resultados (default: 100)
            page_token: Token para paginación (opcional)
            query: Query de búsqueda (opcional)

        Returns:
            Dict con lista de usuarios y token de siguiente página
        """
        data = {"maxResults": max_results}

        if page_token:
            data["pageToken"] = page_token
        if query:
            data["query"] = query

        return self._make_request('getManyUsersGoogle', method='POST', data=data)

    # ========== Gestión de Grupos ==========

    def add_user_to_group(self, user_email: str, group_id: str) -> Dict[str, Any]:
        """
        Agrega un usuario a un grupo de Google Workspace

        Args:
            user_email: Email del usuario
            group_id: ID del grupo o email del grupo

        Returns:
            Dict con confirmación
        """
        data = {
            "primaryEmail": user_email,
            "groupId": group_id
        }
        return self._make_request('addUserToGroup', method='POST', data=data)

    def remove_user_from_group(self, user_email: str, group_id: str) -> Dict[str, Any]:
        """
        Remueve un usuario de un grupo de Google Workspace

        Args:
            user_email: Email del usuario
            group_id: ID del grupo o email del grupo

        Returns:
            Dict con confirmación
        """
        data = {
            "primaryEmail": user_email,
            "groupId": group_id
        }
        return self._make_request('removeUserFromGroup', method='POST', data=data)

    def create_google_group(
        self,
        group_email: str,
        group_name: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crea un grupo en Google Workspace

        Args:
            group_email: Email del grupo (ej: nuevo-grupo@ctcsalto.edu.uy)
            group_name: Nombre descriptivo del grupo
            description: Descripción del grupo (opcional)

        Returns:
            Dict con los datos del grupo creado
        """
        data = {
            "groupEmail": group_email,
            "groupName": group_name
        }

        if description:
            data["description"] = description

        return self._make_request('createGoogleGroup', method='POST', data=data)

    def list_google_groups(
        self,
        max_results: int = 100,
        page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lista grupos de Google Workspace

        Args:
            max_results: Número máximo de resultados (default: 100)
            page_token: Token para paginación (opcional)

        Returns:
            Dict con lista de grupos y token de siguiente página
        """
        data = {"maxResults": max_results}

        if page_token:
            data["pageToken"] = page_token

        return self._make_request('getManyGroupsGoogle', method='POST', data=data)

    def get_google_group(self, group_id: str) -> Dict[str, Any]:
        """
        Obtiene información de un grupo de Google Workspace por ID

        Args:
            group_id: ID del grupo (o email del grupo)

        Returns:
            Dict con los datos del grupo
        """
        data = {"groupId": group_id}
        return self._make_request('getGoogleGroupById', method='POST', data=data)

    def update_google_group(
        self,
        group_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Actualiza un grupo de Google Workspace

        Args:
            group_id: ID del grupo (o email del grupo)
            name: Nuevo nombre del grupo (opcional)
            description: Nueva descripción (opcional)
            email: Nuevo email del grupo (opcional)

        Returns:
            Dict con los datos del grupo actualizado
        """
        data = {"groupId": group_id}

        if name:
            data["name"] = name
        if description:
            data["description"] = description
        if email:
            data["email"] = email

        return self._make_request('updateGoogleGroup', method='POST', data=data)

    def delete_google_group(self, group_id: str) -> Dict[str, Any]:
        """
        Elimina un grupo de Google Workspace

        Args:
            group_id: ID del grupo o email del grupo a eliminar

        Returns:
            Dict con confirmación
        """
        data = {"groupId": group_id}
        return self._make_request('deleteGoogleGroup', method='POST', data=data)

    def list_group_members(self, group_email: str) -> Dict[str, Any]:
        """
        Lista los miembros de un grupo de Google Workspace

        Args:
            group_email: Email del grupo

        Returns:
            Dict con lista de miembros
        """
        data = {"groupEmail": group_email}
        return self._make_request('getMembersGroup', method='POST', data=data)


# Instancia singleton del servicio
google_workspace_service = GoogleWorkspaceService()
