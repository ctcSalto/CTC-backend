import requests
import json
from external_services.moodle_api.moodle_config import MoodleConfig
from typing import Dict

from utils.logger import show

class BaseMoodleController:
    def __init__(self, config: MoodleConfig):
        self.config = config
        self._validate_config()
    
    def _validate_config(self):
        if not self.config.token:
            raise ValueError("Token de Moodle no configurado")
        if not self.config.base_url:
            raise ValueError("URL de Moodle no configurada")
    
    def _generate_request_url(self, function: str) -> str:
        show(f"URL Base: {self.config.base_url}")
        show(f"Token: {self.config.token}")
        show(f"Función: {function}")
        show(f"Formato: {self.config.format_type}")
        return (f"{self.config.base_url}/webservice/rest/server.php?wstoken={self.config.token}"
                f"&wsfunction={function}&moodlewsrestformat={self.config.format_type}")
    
    def _make_request(self, function: str, payload: Dict) -> Dict:
        url = self._generate_request_url(function)
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if isinstance(result, dict) and 'exception' in result:
                raise Exception(f"Error de Moodle: {result.get('message', 'Error desconocido')}")
                
            return result
        except requests.RequestException as e:
            raise Exception(f"Error de conexión: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Error al decodificar respuesta JSON: {str(e)}")