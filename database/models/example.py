from sqlmodel import SQLModel, Field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # Importación condicional para evitar importación circular
    pass

class ExampleBase(SQLModel):
    name: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=3, max_length=100, unique=True)
    age: Optional[int] = Field(default=None, ge=0, le=120)

class Example(ExampleBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class ExampleCreate(ExampleBase):
    pass

class ExampleUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=100)
    email: Optional[str] = Field(default=None, min_length=3, max_length=100)
    age: Optional[int] = Field(default=None, ge=0, le=120)

class ExampleRead(ExampleBase):
    id: int
