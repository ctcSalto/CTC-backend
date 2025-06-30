from dataclasses import dataclass
from enum import Enum
import os
import dotenv
# Cargar .env en desarrollo, usar variables del sistema en producción
try:
    import dotenv
    dotenv.load_dotenv(override=True)
except Exception:
    pass  # En producción no existe .env, usa variables del sistema

@dataclass
class MoodleConfig:
    token: str
    base_url: str
    format_type: str = 'json'
    
    @classmethod
    def from_env(cls):
        return cls(
            token=os.getenv('MOODLE_TOKEN'),
            base_url=os.getenv('MOODLE_URL')
        )

class AuthMethod(Enum):
    MANUAL = "manual"
    LDAP = "ldap"
    EMAIL = "email"

class UserField(Enum):
    ID = "id"
    USERNAME = "username"
    EMAIL = "email"
    IDNUMBER = "idnumber"

class CourseFormat(Enum):
    WEEKS = "weeks"
    TOPICS = "topics"
    SOCIAL = "social"
    SITE = "site"

class EnrolmentRole(Enum):
    STUDENT = 5
    TEACHER = 3
    EDITING_TEACHER = 4
    MANAGER = 1