from dataclasses import dataclass
from enum import Enum
import os
import dotenv
try:
    from dotenv import load_dotenv
    # Solo carga .env si existe el archivo
    if os.path.exists('.env'):
        load_dotenv(override=True)
        print("✅ Variables de entorno cargadas desde .env")
    else:
        print("ℹ️ Usando variables del sistema (producción)")
except ImportError:
    # En producción donde python-dotenv no está instalado
    print("ℹ️ python-dotenv no disponible, usando variables del sistema")
except Exception as e:
    print(f"⚠️ Error cargando .env: {e}")

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