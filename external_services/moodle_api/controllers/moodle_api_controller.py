from external_services.moodle_api.controllers.moodle_user_controller import UserController
from external_services.moodle_api.controllers.moodle_course_controller import CourseController
from external_services.moodle_api.controllers.moodle_category_controller import CategoryController
from external_services.moodle_api.controllers.moodle_enrolment_controller import EnrolmentController
from external_services.moodle_api.moodle_config import MoodleConfig
from external_services.moodle_api.moodle_config import EnrolmentRole
from typing import Dict

class MoodleController:
    def __init__(self, config: MoodleConfig = None):
        if config is None:
            config = MoodleConfig.from_env()
        
        self.users = UserController(config)
        self.courses = CourseController(config)
        self.categories = CategoryController(config)
        self.enrolments = EnrolmentController(config)
    
    def enrol_student(self, user_id: int, course_id: int) -> Dict:
        """Inscribir como estudiante"""
        return self.enrolments.enrol_user(user_id, course_id, EnrolmentRole.STUDENT)
    
    def enrol_teacher(self, user_id: int, course_id: int) -> Dict:
        """Inscribir como profesor"""
        return self.enrolments.enrol_user(user_id, course_id, EnrolmentRole.TEACHER)
    
    def create_course_with_category(self, course_name: str, course_short: str, 
                                  category_name: str, category_description: str = "") -> Dict:
        """Crear curso en una categoría específica, creando la categoría si no existe"""
        # Obtener o crear la categoría
        category = self.categories.get_or_create_category(
            name=category_name, 
            description=category_description
        )
        
        if not category or 'id' not in category:
            raise Exception(f"No se pudo crear/obtener la categoría: {category_name}")
        
        # Crear el curso en la categoría
        course = Course(
            fullname=course_name,
            shortname=course_short,
            categoryid=category['id']
        )
        
        return self.courses.create_course(course)