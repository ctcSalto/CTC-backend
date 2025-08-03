from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import date, datetime
from enum import Enum
import re
from pydantic import field_validator

if TYPE_CHECKING:
    from database.models.career import Career
    from database.models.testimony import Testimony
    from database.models.news import News

class UserRole(str, Enum):
    ADMIN = "admin"
    STUDENT = "student"

class User(SQLModel, table=True):
    userId: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    name: str = Field(max_length=50)
    lastname: str = Field(max_length=50)
    phone: str
    document: str = Field(unique=True)
    rol: UserRole
    confirmed: bool = Field(default=False)
    creationDate: date = Field(default_factory=date.today)
    modificationDate: Optional[date] = None
    lastAccess: Optional[date] = None
    password: str 
    active: bool = Field(default=True)
    
        # Relaciones - Careers
    created_careers: List["Career"] = Relationship(
        back_populates="creator_user",
        sa_relationship_kwargs={"foreign_keys": "[Career.creator]"}
    )
    modified_careers: List["Career"] = Relationship(
        back_populates="modifier_user",
        sa_relationship_kwargs={"foreign_keys": "[Career.modifier]"}
    )
    
    # Relaciones - Testimonies
    created_testimonies: List["Testimony"] = Relationship(
        back_populates="creator_user",
        sa_relationship_kwargs={"foreign_keys": "[Testimony.creator]"}
    )
    modified_testimonies: List["Testimony"] = Relationship(
        back_populates="modifier_user",
        sa_relationship_kwargs={"foreign_keys": "[Testimony.modifier]"}
    )
    
    # Relaciones - News
    created_news: List["News"] = Relationship(
        back_populates="creator_user",
        sa_relationship_kwargs={"foreign_keys": "[News.creator]"}
    )
    modified_news: List["News"] = Relationship(
        back_populates="modifier_user",
        sa_relationship_kwargs={"foreign_keys": "[News.modifier]"}
    )

class UserBase(SQLModel):
    email: str
    name: str = Field(max_length=50)
    lastname: str = Field(max_length=50)
    phone: str
    document: str

class UserCreate(UserBase):
    password: str
    rol: UserRole = Field(default=UserRole.STUDENT)
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str):
        errors = []
        if len(v) < 8:
            errors.append('– al menos 8 caracteres')
        if not any(c.isupper() for c in v):
            errors.append('– al menos una letra mayúscula')
        if not any(c.isdigit() for c in v):
            errors.append('– al menos un número')
        if not any(c in '@.*$' for c in v):
            errors.append('– al menos un carácter especial (@, ., *, $)')

        if errors:
            msg = 'La contraseña debe contener:\n' + '\n'.join(errors)
            raise ValueError(msg)
        
        # Regex final opcional para evitar otros caracteres
        pattern = r'^[A-Za-z\d@\.\*\$]+$'
        if not re.fullmatch(pattern, v):
            raise ValueError(
                'La contraseña solo puede contener letras, números y los caracteres @ . * $'
            )
        return v

class UserUpdate(SQLModel):
    email: Optional[str] = None
    name: Optional[str] = Field(None, max_length=50)
    lastname: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = None
    document: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[UserRole] = None
    confirmed: Optional[bool] = None
    active: Optional[bool] = None
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str]):
        if v is not None:
            errors = []
            if len(v) < 8:
                errors.append('– al menos 8 caracteres')
            if not any(c.isupper() for c in v):
                errors.append('– al menos una letra mayúscula')
            if not any(c.isdigit() for c in v):
                errors.append('– al menos un número')
            if not any(c in '@.*$' for c in v):
                errors.append('– al menos un carácter especial (@, ., *, $)')

            if errors:
                msg = 'La contraseña debe contener:\n' + '\n'.join(errors)
                raise ValueError(msg)
            
            # Regex final opcional para evitar otros caracteres
            pattern = r'^[A-Za-z\d@\.\*\$]+$'
            if not re.fullmatch(pattern, v):
                raise ValueError(
                    'La contraseña solo puede contener letras, números y los caracteres @ . * $'
                )
        return v

class UserRead(UserBase):
    userId: int
    rol: UserRole
    confirmed: bool
    creationDate: date
    modificationDate: Optional[date] = None
    lastAccess: Optional[date] = None
    active: bool
    
class UserReadFilters(SQLModel):
    """Schema para filtros de búsqueda de usuarios"""    
    userId: Optional[int] = None
    email: Optional[str] = None
    name: Optional[str] = None
    lastname: Optional[str] = None
    phone: Optional[str] = None
    document: Optional[str] = None
    rol: Optional[UserRole] = None
    confirmed: Optional[bool] = None
    active: Optional[bool] = None
    
    def to_dict(self) -> dict:
        """Convertir a diccionario, omitiendo campos None"""
        return {k: v for k, v in self.model_dump().items() if v is not None}

class UserLogin(SQLModel):
    email: str
    password: str

class Token(SQLModel):
    access_token: str
    token_type: str
    expires_in: Optional[int] = None

class TokenData(SQLModel):
    email: Optional[str] = None
    jti: Optional[str] = None

# Modelo adicional para respuestas públicas (sin información sensible)
class UserPublic(SQLModel):
    userId: int
    email: str
    name: str
    lastname: str
    rol: UserRole
    confirmed: bool
    active: bool