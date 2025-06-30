from external_services.moodle_api.controllers.moodle_base_controller import BaseMoodleController
from external_services.moodle_api.payloads.moodle_category import Category
from typing import List, Optional, Dict, Union

class CategoryController(BaseMoodleController):
    
    def create_category(self, category: Category) -> Dict:
        """Crear una categoría de curso"""
        payload = category.to_payload()
        return self._make_request("core_course_create_categories", payload)
    
    def create_categories(self, categories: List[Category]) -> Dict:
        """Crear múltiples categorías"""
        payload = {}
        for i, category in enumerate(categories):
            payload.update(category.to_payload(i))
        return self._make_request("core_course_create_categories", payload)
    
    def get_categories(self, criteria: Optional[List[Dict]] = None) -> Dict:
        """Obtener categorías. Criterios pueden incluir 'key' y 'value' para filtrar"""
        payload = {}
        if criteria:
            for i, criterion in enumerate(criteria):
                payload[f"criteria[{i}][key]"] = criterion.get("key", "")
                payload[f"criteria[{i}][value]"] = criterion.get("value", "")
        return self._make_request("core_course_get_categories", payload)
    
    def update_category(self, category_id: int, updates: Dict[str, Union[str, int]]) -> Dict:
        """Actualizar categoría existente"""
        payload = {"categories[0][id]": category_id}
        for key, value in updates.items():
            payload[f"categories[0][{key}]"] = value
        return self._make_request("core_course_update_categories", payload)
    
    def delete_category(self, category_id: int, recursive: bool = True) -> Dict:
        payload = {
            "categories[0][id]": category_id,
            "categories[0][recursive]": 1 if recursive else 0,
            "categories[0][newparent]": 0  
        }
        return self._make_request("core_course_delete_categories", payload)
    
    def get_category_by_name(self, name: str) -> Optional[Dict]:
        """Buscar categoría por nombre"""
        criteria = [{"key": "name", "value": name}]
        result = self.get_categories(criteria)
        
        if result and len(result) > 0:
            # Buscar coincidencia exacta
            for category in result:
                if category.get("name", "").lower() == name.lower():
                    return category
        return None

    def get_or_create_category(self, name: str, parent_id: int = 0, description: str = "") -> Dict:
        """Obtener categoría existente o crearla si no existe"""
        existing = self.get_category_by_name(name)
        if existing:
            return existing
        
        new_category = Category(
            name=name,
            parent=parent_id,
            description=description
        )
        result = self.create_category(new_category)
        return result[0] if result and len(result) > 0 else {}

    def get_category_by_id(self, category_id: int) -> Optional[Dict]:
        """Buscar categoría por ID"""
        criteria = [{"key": "id", "value": category_id}]
        result = self.get_categories(criteria)
        
        if result and len(result) > 0:
            return result[0]
        return None