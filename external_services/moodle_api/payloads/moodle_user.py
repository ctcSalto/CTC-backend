from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict
from external_services.moodle_api.moodle_config import AuthMethod

@dataclass
class User:
    username: str
    firstname: str
    lastname: str
    email: str
    auth: AuthMethod = AuthMethod.MANUAL
    password: Optional[str] = None
    idnumber: Optional[str] = None
    lang: str = "es"
    timezone: str = "America/Montevideo"
    
    def to_payload(self, index: int = 0) -> Dict[str, str]:
        payload = {
            f"users[{index}][username]": self.username,
            f"users[{index}][firstname]": self.firstname,
            f"users[{index}][lastname]": self.lastname,
            f"users[{index}][email]": self.email,
            f"users[{index}][auth]": self.auth.value,
            f"users[{index}][lang]": self.lang,
            f"users[{index}][timezone]": self.timezone,
        }
        
        if self.password and self.password.strip():
            payload[f"users[{index}][password]"] = self.password
        
        if self.idnumber and self.idnumber.strip():
            payload[f"users[{index}][idnumber]"] = self.idnumber
            
        return payload