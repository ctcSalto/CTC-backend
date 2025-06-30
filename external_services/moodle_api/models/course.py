from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union, Any
from external_services.moodle_api.payloads.moodle_course import Course

class MoodleCourseCreate(BaseModel):
    fullname: str = Field(..., description="Nombre completo del curso")
    shortname: str = Field(..., description="Nombre corto del curso")
    categoryid: int = 1 
    summary: str = ""
    format: str = "topics"
    numsections: int = 10
    visible: int = 1
    startdate: Optional[int] = None
    enddate: Optional[int] = None

    def to_moodle_course(self) -> 'Course':
        return Course(
            fullname=self.fullname,
            shortname=self.shortname,
            categoryid=self.categoryid,
            summary=self.summary,
            format=self.format,
            numsections=self.numsections,
            visible=self.visible,
            startdate=self.startdate,
            enddate=self.enddate
        )

    def to_dict(self) -> Dict[str, Union[str, int]]:
        """Convertir a diccionario para actualizaciones"""
        data = self.model_dump(exclude_none=True)
        return {k: v for k, v in data.items() if v is not None}

class MoodleCourseRead(BaseModel):
    id: int
    fullname: str
    shortname: str
    categoryid: int
    summary: str
    format: str
    numsections: int
    visible: int
    startdate: Optional[int]
    enddate: Optional[int]

    @classmethod
    def from_moodle_response(cls, response: List, original_course: 'MoodleCourseCreate' = None) -> 'MoodleCourseRead':
        if not response or len(response) == 0:
            raise ValueError("Respuesta vacía de Moodle")
        
        course_data = response[0]
        
        # Manejar tanto enum como string
        format_fallback = "topics"
        if original_course and original_course.format:
            if isinstance(original_course.format, str):
                format_fallback = original_course.format
            else:
                format_fallback = original_course.format.value
        
        return cls(
            id=course_data.get('id'),
            fullname=course_data.get('fullname') or (original_course.fullname if original_course else ""),
            shortname=course_data.get('shortname') or (original_course.shortname if original_course else ""),
            categoryid=course_data.get('categoryid') or (original_course.categoryid if original_course else 1),
            summary=course_data.get('summary') or (original_course.summary if original_course else ""),
            format=course_data.get('format') or format_fallback,
            numsections=course_data.get('numsections') or (original_course.numsections if original_course else 10),
            visible=course_data.get('visible') or (original_course.visible if original_course else 1),
            startdate=course_data.get('startdate') or (original_course.startdate if original_course else None),
            enddate=course_data.get('enddate') or (original_course.enddate if original_course else None)
        )


class MoodleCourseUpdate(BaseModel):
    """Modelo para actualizar cursos en Moodle"""
    fullname: Optional[str] = None
    shortname: Optional[str] = None
    categoryid: Optional[int] = None
    idnumber: Optional[str] = None
    summary: Optional[str] = None
    summaryformat: Optional[int] = 1  # 1 = HTML
    format: Optional[str] = None  # 'topics', 'weeks', etc.
    showgrades: Optional[int] = None
    newsitems: Optional[int] = None
    startdate: Optional[int] = None
    enddate: Optional[int] = None
    numsections: Optional[int] = None
    maxbytes: Optional[int] = None
    showreports: Optional[int] = None
    visible: Optional[int] = None
    hiddensections: Optional[int] = None
    groupmode: Optional[int] = None
    groupmodeforce: Optional[int] = None
    defaultgroupingid: Optional[int] = None
    enablecompletion: Optional[int] = None
    completionnotify: Optional[int] = None
    lang: Optional[str] = None
    forcetheme: Optional[str] = None

    def to_moodle_payload(self, course_id: int) -> Dict[str, Any]:
        """Convierte el modelo a payload para Moodle"""
        payload = {"courses[0][id]": course_id}
        
        # Solo incluir campos que no sean None
        for field_name, field_value in self.model_dump(exclude_none=True).items():
            payload[f"courses[0][{field_name}]"] = field_value
            
        return payload

class MoodleWarning(BaseModel):
    """Modelo para warnings de Moodle"""
    item: str
    itemid: int
    warningcode: str
    message: str

class MoodleUpdateResponse(BaseModel):
    """Respuesta de operaciones de update en Moodle"""
    warnings: List[MoodleWarning] = []
    
    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0
    
    @property
    def success(self) -> bool:
        # Si no hay warnings o solo warnings menores, consideramos éxito
        serious_warnings = [w for w in self.warnings if w.warningcode not in ['courseidnotfound']]
        return len(serious_warnings) == 0

class MoodleCourseUpdateResponse(BaseModel):
    """Respuesta específica para actualización de cursos"""
    success: bool
    warnings: List[MoodleWarning] = []
    updated_course: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_moodle_response(cls, moodle_response: Dict[str, Any], course_id: int) -> 'MoodleCourseUpdateResponse':
        """Crear respuesta desde respuesta de Moodle"""
        warnings = []
        
        if 'warnings' in moodle_response:
            warnings = [
                MoodleWarning(**warning) 
                for warning in moodle_response['warnings']
            ]
        
        # Determinar si fue exitoso
        success = len([w for w in warnings if w.warningcode not in ['courseidnotfound']]) == 0
        
        return cls(
            success=success,
            warnings=warnings,
            updated_course=None  # Moodle update no retorna el curso actualizado
        )

class DeleteResponseCourse(BaseModel):
    """Respuesta de eliminación de curso en Moodle"""
    success: bool = Field(..., description="Indica si la operación fue exitosa")
    message: str = Field(..., description="Mensaje de respuesta")
    id: int = Field(..., description="ID del curso eliminado")
    

    
