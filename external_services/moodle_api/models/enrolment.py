from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Any, Dict

class MoodleEnrolmentCreate(BaseModel):
    courseid: int = Field(..., description="ID del curso")
    userid: int = Field(..., description="ID del usuario")
    roleid: int = Field(..., description="ID del rol (1=Manager, 3=Teacher, 4=EditingTeacher, 5=Student)")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "courseid": 1,
                "userid": 123,
                "roleid": 5
            }
        }
    }

class MoodleEnrolmentRead(BaseModel):
    success: bool
    courseid: int
    userid: int
    roleid: int
    message: str = None


class MoodleBulkEnrolmentCreate(BaseModel):
    enrolments: List[MoodleEnrolmentCreate] = Field(..., description="Lista de inscripciones")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "enrolments": [
                    {"courseid": 1, "userid": 123, "roleid": 5},
                    {"courseid": 1, "userid": 124, "roleid": 5},
                    {"courseid": 2, "userid": 123, "roleid": 3}
                ]
            }
        }
    }

class MoodleBulkEnrolmentRead(BaseModel):
    total_enrolments: int
    successful_enrolments: int
    failed_enrolments: int
    results: List[MoodleEnrolmentRead]
    message: str

class MoodleUnenrolmentCreate(BaseModel):
    courseid: int = Field(..., description="ID del curso")
    userid: int = Field(..., description="ID del usuario")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "courseid": 1,
                "userid": 123
            }
        }
    }

class MoodleUnenrolmentRead(BaseModel):
    success: bool
    courseid: int
    userid: int
    message: str = None

class EnrolledUser(BaseModel):
    id: int
    username: str
    firstname: str
    lastname: str
    email: str
    roles: List[Dict[str, Any]] = []

class CourseEnrolledUsers(BaseModel):
    courseid: int
    total_users: int
    users: List[EnrolledUser]
