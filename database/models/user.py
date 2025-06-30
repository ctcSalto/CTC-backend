from sqlmodel import SQLModel, Field
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    # Importación condicional de la clases relacionadas para evitar importación circular
    # Ejemplo: from .example import Example
    pass

class UserRole(str, Enum):
    ADMINISTRATIVO = "admin"
    DOCENTE = "docente"
    ALUMNO = "alumno"

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True, max_length=255, min_length=5)
    password_hash: str
    full_name: Optional[str] = None
    role: UserRole = Field(default="alumno")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

class UserBase(SQLModel):
    username: str
    email: str
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(SQLModel):
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserRead(UserBase):
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime

class UserLogin(SQLModel):
    username: str
    password: str

class Token(SQLModel):
    access_token: str
    token_type: str
    expires_in: Optional[int] = None

class TokenData(SQLModel):
    username: Optional[str] = None