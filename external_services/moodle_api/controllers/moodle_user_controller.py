from external_services.moodle_api.controllers.moodle_base_controller import BaseMoodleController
from external_services.moodle_api.moodle_config import UserField
from external_services.moodle_api.payloads.moodle_user import User
from typing import List, Dict

class UserController(BaseMoodleController):
    
    def create_user(self, user: User) -> Dict:
        """Crear un usuario en Moodle"""
        payload = user.to_payload()
        return self._make_request("core_user_create_users", payload)
    
    def create_users(self, users: List[User]) -> Dict:
        """Crear múltiples usuarios"""
        payload = {}
        for i, user in enumerate(users):
            payload.update(user.to_payload(i))
        return self._make_request("core_user_create_users", payload)
    
    def get_user(self, value: str, field: UserField = UserField.EMAIL) -> Dict:
        """Obtener usuario por campo específico"""
        payload = {
            "field": field.value,
            "values[0]": value
        }
        return self._make_request("core_user_get_users_by_field", payload)

    def get_user_by_id(self, user_id: int) -> Dict:
        """Obtener usuario por ID específicamente"""
        payload = {
            "field": "id",
            "values[0]": str(user_id)
        }
        return self._make_request("core_user_get_users_by_field", payload)

    def get_users_by_ids(self, user_ids: List[int]) -> Dict:
        """Obtener múltiples usuarios por sus IDs"""
        payload = {}
        for i, user_id in enumerate(user_ids):
            payload[f"userids[{i}]"] = str(user_id)
        return self._make_request("core_user_get_users", payload)

    def get_users(self, criteria: List[Dict[str, str]] = None) -> Dict:
        if criteria is None:
            criteria = [{"key": "auth", "value": "manual"}]

        payload: Dict[str, Any] = {}
        for idx, crit in enumerate(criteria):
            payload[f"criteria[{idx}][key]"] = crit["key"]
            payload[f"criteria[{idx}][value]"] = crit["value"]

        return self._make_request("core_user_get_users", payload)
    
    def update_user(self, user_id: int, updates: Dict[str, str]) -> Dict:
        """Actualizar usuario existente"""
        payload = {"users[0][id]": str(user_id)}
        for key, value in updates.items():
            payload[f"users[0][{key}]"] = value
        return self._make_request("core_user_update_users", payload)
    
    def delete_user(self, user_id: int) -> Dict:
        """Eliminar usuario"""
        payload = {"userids[0]": str(user_id)}
        return self._make_request("core_user_delete_users", payload)