from fastapi import APIRouter, HTTPException, Depends
from external_services.moodle_api.models.enrolment import MoodleEnrolmentCreate, MoodleEnrolmentRead, MoodleBulkEnrolmentCreate, MoodleBulkEnrolmentRead, MoodleUnenrolmentCreate, MoodleUnenrolmentRead, EnrolledUser, CourseEnrolledUsers
from external_services.moodle_api.controllers.moodle_api_controller import MoodleController
from external_services.moodle_api.moodle_config import MoodleConfig, EnrolmentRole
from typing import List

router = APIRouter(prefix="/moodle", tags=["Moodle Enrolments"])

config = MoodleConfig.from_env()
moodle_controller = MoodleController(config)

@router.post("/enrolments", response_model=MoodleEnrolmentRead)
async def create_enrolment(enrolment: MoodleEnrolmentCreate):
    """
    Inscribir un usuario en un curso con un rol específico
    
    - **courseid**: ID del curso en Moodle
    - **userid**: ID del usuario en Moodle  
    - **roleid**: ID del rol (1=Manager, 3=Teacher, 4=EditingTeacher, 5=Student)
    
    Ejemplo de solicitud:
    ```json
    {
        "courseid": 1,
        "userid": 123,
        "roleid": 5
    }
    ```
    """
    try:
        result = moodle_controller.enrolments.enrol_user(enrolment)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
            
        return result
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

@router.get("/enrolments/roles")
async def get_available_roles():
    """Obtener los roles disponibles para inscripción"""
    return {
        "roles": [
            {"id": role.value, "name": role.name.replace("_", " ").title()}
            for role in EnrolmentRole
        ]
    }

@router.post("/enrolments/bulk", response_model=MoodleBulkEnrolmentRead)
async def create_bulk_enrolments(enrolments: MoodleBulkEnrolmentCreate):
    """
    Inscribir múltiples usuarios en cursos con roles específicos
    
    Permite inscribir varios usuarios de una vez en diferentes cursos y con diferentes roles.
    
    - **enrolments**: Lista de inscripciones
    
    Ejemplo de solicitud:
    ```json
        {
        "courseid": 3,
        "userid": 4,
        "roleid": 5
        }
    ```
    """
    try:
        result = moodle_controller.enrolments.enrol_users_bulk(enrolments)
        
        if result.failed_enrolments > 0:
            # Si hay fallos pero también éxitos, devolver código 207 (Multi-Status)
            # Si todos fallaron, devolver error 400
            if result.successful_enrolments == 0:
                raise HTTPException(status_code=400, detail=result.message)
        
        return result
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@router.delete("/enrolments", response_model=MoodleUnenrolmentRead)
async def remove_enrolment(unenrolment: MoodleUnenrolmentCreate):
    """
    Desinscribir un usuario de un curso
    
    - **courseid**: ID del curso en Moodle
    - **userid**: ID del usuario en Moodle
    
    Ejemplo de solicitud:
    ```json
        {
        "courseid": 1,
        "userid": 1
        }
    ```
    """
    try:
        result = moodle_controller.enrolments.unenrol_user(unenrolment)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


@router.get("/enrolments/course/{course_id}", response_model=CourseEnrolledUsers)
async def get_course_enrolled_users(course_id: int):
    """
    Obtener todos los usuarios inscritos en un curso específico
    
    - **course_id**: ID del curso en Moodle
    
    Ejemplo de solicitud:
    ```json
        {
        "course_id": 1
        }
    ```
    
    Retorna la lista completa de usuarios inscritos con su información básica y roles.
    """
    try:
        result = moodle_controller.enrolments.get_enrolled_users(course_id)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")
