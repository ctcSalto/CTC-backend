from fastapi import APIRouter, HTTPException, Depends
from external_services.moodle_api.models.course import MoodleCourseCreate, MoodleCourseRead, MoodleCourseUpdate, MoodleCourseUpdateResponse, DeleteResponseCourse
from external_services.moodle_api.controllers.moodle_api_controller import MoodleController
from external_services.moodle_api.moodle_config import MoodleConfig
from typing import List
from utils.logger import show

router = APIRouter(prefix="/moodle", tags=["Moodle Courses"])

config = MoodleConfig.from_env()
moodle_controller = MoodleController(config)

@router.post("/courses", response_model=MoodleCourseRead)
async def create_course(course: MoodleCourseCreate):
    """
    Crea un curso en Moodle
    
    - **name**: Nombre del curso
    - **shortname**: Nombre corto del curso
    - **categoryid**: ID de la categoría
    - **startdate**: Fecha de inicio
    - **enddate**: Fecha de finalización
    - **visible**: Visibilidad del curso
    
    Ejemplo de solicitud:
    ```json
        {
        "fullname": "Programación 1",
        "shortname": "Prog 1",
        "categoryid": 2,
        "summary": "Esto es un curso de programación",
        "format": "topics",
        "numsections": 10,
        "visible": 1,
        "startdate": 0,
        "enddate": 0
        }
    ```
    """
    try:
        moodle_course_payload = course.to_moodle_course()
        response = moodle_controller.courses.create_course(moodle_course_payload)
        return MoodleCourseRead.from_moodle_response(response, course)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/courses", response_model=List[MoodleCourseRead])
async def get_courses():
    """
    Obtiene todos los cursos de Moodle
    """
    try:
        moodle_courses = moodle_controller.courses.get_courses()
        return moodle_courses
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/courses/{course_id}", response_model=MoodleCourseRead)
async def get_course(course_id: int):
    """
    Obtiene un curso específico de Moodle
    
    - **course_id**: ID del curso en Moodle
    """
    try:
        moodle_course = moodle_controller.courses.get_course(course_id)
        return MoodleCourseRead.from_moodle_response(moodle_course)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/courses/{course_id}", response_model=MoodleCourseUpdateResponse)
async def update_course(course_id: int, course_update: MoodleCourseUpdate):
    """
    Actualiza un curso específico en Moodle
    
    - **course_id**: ID del curso en Moodle
    
    Ejemplo de solicitud:
    ```json
        {
        "fullname": "Programación 2",
        "shortname": "Prog 2",
        "categoryid": 2,
        "summary": "Esto es un curso de programación",
        "format": "topics",
        "numsections": 10,
        "visible": 1,
        "startdate": 0,
        "enddate": 0
        }
    ```
    """
    try:
        show(f"Actualizando curso {course_id} con: {course_update}")
        
        # Actualizar en Moodle
        moodle_response = moodle_controller.courses.update_course(course_id, course_update)
        show(f"Respuesta de Moodle: {moodle_response}")
        
        # Procesar respuesta
        update_response = MoodleCourseUpdateResponse.from_moodle_response(moodle_response, course_id)
        
        if not update_response.success:
            # Si hay errores serios, lanzar excepción
            error_messages = [w.message for w in update_response.warnings]
            raise HTTPException(status_code=400, detail=f"Error actualizando curso: {'; '.join(error_messages)}")
        
        return update_response
        
    except Exception as e:
        show(f"Error en update: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/courses/{course_id}", response_model=DeleteResponseCourse)
async def delete_course(course_id: int):
    """
    Elimina un curso específico de Moodle
    
    - **course_id**: ID del curso en Moodle
    """
    try:
        moodle_course = moodle_controller.courses.delete_course(course_id)
        return DeleteResponseCourse(
            success=True,
            message="Curso eliminado correctamente",
            id=course_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

