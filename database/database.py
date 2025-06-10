from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv
import os

from .models.example import Example
from .models.user import User

from .services.example_service import ExampleService
from .services.user_service import UserService

load_dotenv()   

engine = create_engine(
    "sqlite:///./test.db"
    #os.getenv("DATABASE_URL")
)

class Services:
    def __init__(self):
        self.exampleService = ExampleService()
        self.userService = UserService()

_services_instance: Services | None = None

def get_engine():
    return engine

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

def init_services():
    return Services()

def get_services():
    global _services_instance
    if _services_instance is None:
        _services_instance = init_services()
    return _services_instance