from external_services.moodle_api.controllers.moodle_base_controller import BaseMoodleController
from external_services.moodle_api.payloads.moodle_course import Course
from external_services.moodle_api.models.course import MoodleCourseUpdate
from typing import List, Optional, Dict, Union
from utils.logger import show

class CourseController(BaseMoodleController):
    
    def create_course(self, course: Course) -> Dict:
        """Crear un curso"""
        payload = course.to_payload()
        return self._make_request("core_course_create_courses", payload)
    
    def create_courses(self, courses: List[Course]) -> Dict:
        """Crear múltiples cursos"""
        payload = {}
        for i, course in enumerate(courses):
            payload.update(course.to_payload(i))
        return self._make_request("core_course_create_courses", payload)
    
    def get_courses(self, course_ids: Optional[List[int]] = None) -> Dict:
        """Obtener cursos. Si no se especifican IDs, obtiene todos"""
        payload = {}
        if course_ids:
            for i, course_id in enumerate(course_ids):
                payload[f"options[ids][{i}]"] = course_id
        return self._make_request("core_course_get_courses", payload)

    def get_course(self, course_id: int) -> Dict:
        """Obtener un curso específico"""
        payload = {"options[ids][0]": course_id}
        return self._make_request("core_course_get_courses", payload)
    
    def get_courses_by_category(self, category_id: int) -> Dict:
        """Obtener cursos de una categoría específica"""
        payload = {f"options[categoryid]": category_id}
        return self._make_request("core_course_get_courses", payload)
    
    def update_course(self, course_id: int, course_update: MoodleCourseUpdate) -> Dict:
        """Actualizar curso existente"""
        payload = course_update.to_moodle_payload(course_id)
        show(f"Payload para update: {payload}")  # Debug
        return self._make_request("core_course_update_courses", payload)
    
    def delete_course(self, course_id: int) -> Dict:
        """Eliminar curso"""
        payload = {"courseids[0]": str(course_id)}
        return self._make_request("core_course_delete_courses", payload)
