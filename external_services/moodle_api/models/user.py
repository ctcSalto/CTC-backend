from pydantic import BaseModel, Field
from typing import TYPE_CHECKING, Dict, Any, Optional

if TYPE_CHECKING:
    from moodle_api.payloads.moodle_user import User

class MoodleUserCreate(BaseModel):
    username: str = Field(..., description="Nombre de usuario")
    password: str = Field(..., description="Contraseña")
    firstname: str = Field(..., description="Nombre")
    lastname: str = Field(..., description="Apellido")
    email: str = Field(..., description="Correo electrónico")

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "testuser",
                "password": "testpass",
                "firstname": "Test",
                "lastname": "User",
                "email": "test@example.com"
            }
        }
    }

    def to_moodle_user(self) -> 'User':
        """Convierte MoodleUserCreate a User para la API de Moodle"""
        from moodle_api.payloads.moodle_user import User
        
        return User(
            username=self.username,
            firstname=self.firstname,
            lastname=self.lastname,
            email=self.email,
            password=self.password
        )

class MoodleUserUpdate(BaseModel):
    """Modelo para actualizar usuarios - todos los campos son opcionales"""
    username: Optional[str] = None
    password: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[str] = None
    
    def to_update_dict(self) -> Dict[str, str]:
        """Convierte a diccionario excluyendo campos None"""
        return {k: v for k, v in self.model_dump().items() if v is not None}

class MoodleUserRead(BaseModel):
    id: int
    username: str
    firstname: str
    lastname: str
    email: str
    
    @classmethod
    def from_moodle_response(cls, moodle_response: Dict[str, Any], original_user: MoodleUserCreate = None) -> 'MoodleUserRead':
        """
        Crea MoodleUserRead desde la respuesta de Moodle
        
        Args:
            moodle_response: Respuesta de la API de Moodle
            original_user: Usuario original (opcional, para crear usuarios)
        """
        # Moodle generalmente devuelve una lista con el usuario creado
        if isinstance(moodle_response, list) and len(moodle_response) > 0:
            user_data = moodle_response[0]
            return cls(
                id=user_data['id'],
                username=user_data.get('username', original_user.username if original_user else ''),
                firstname=user_data.get('firstname', original_user.firstname if original_user else ''),
                lastname=user_data.get('lastname', original_user.lastname if original_user else ''),
                email=user_data.get('email', original_user.email if original_user else '')
            )
        # Si la respuesta tiene formato diferente
        elif isinstance(moodle_response, dict):
            return cls(
                id=moodle_response.get('id'),
                username=moodle_response.get('username', original_user.username if original_user else ''),
                firstname=moodle_response.get('firstname', original_user.firstname if original_user else ''),
                lastname=moodle_response.get('lastname', original_user.lastname if original_user else ''),
                email=moodle_response.get('email', original_user.email if original_user else '')
            )
        else:
            raise ValueError("Formato de respuesta de Moodle no reconocido")
    
    @classmethod
    def from_moodle_get_response(cls, moodle_response: Dict[str, Any]) -> 'MoodleUserRead':
        """
        Crea MoodleUserRead específicamente desde respuesta de GET
        """
        # Validar que hay respuesta
        if not moodle_response:
            raise ValueError("Usuario no encontrado")
        
        # core_user_get_users_by_field devuelve una lista
        if isinstance(moodle_response, list) and len(moodle_response) > 0:
            user_data = moodle_response[0]
        # core_user_get_users devuelve dict con 'users'
        elif isinstance(moodle_response, dict) and 'users' in moodle_response:
            if len(moodle_response['users']) == 0:
                raise ValueError("Usuario no encontrado")
            user_data = moodle_response['users'][0]
        else:
            raise ValueError("Usuario no encontrado")
        
        return cls(
            id=user_data['id'],
            username=user_data['username'],
            firstname=user_data['firstname'],
            lastname=user_data['lastname'],
            email=user_data['email']
        )

    @classmethod
    def from_user_data(cls, user_data: Dict[str, Any]) -> 'MoodleUserRead':
        """Crear MoodleUserRead desde datos de usuario directos"""
        return cls(
            id=user_data['id'],
            username=user_data['username'],
            firstname=user_data['firstname'],
            lastname=user_data['lastname'],
            email=user_data['email']
        )
    
    @classmethod
    def from_user_payload(cls, user_payload: 'User', user_id: int) -> 'MoodleUserRead':
        """
        Alternativa: crear desde User payload con ID
        """
        return cls(
            id=user_id,
            username=user_payload.username,
            firstname=user_payload.firstname,
            lastname=user_payload.lastname,
            email=user_payload.email
        )

class DeleteUserResponse(BaseModel):
    message: str = Field(..., description="Mensaje de respuesta")
    user_id: int = Field(..., description="ID del usuario eliminado")