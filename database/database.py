from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv
import os

from .models.example import Example
from .models.user import User

from .services.example_service import ExampleService
from .services.user_service import UserService
from .services.supabase.image_service import SupabaseService

#-------------------TEST------------------------------
from .models.test.author import Author
from .models.test.post import Post
from .models.test.profile import Profile

from database.services.filter.filters import BaseServiceWithFilters
from .services.test.test_services import AuthorService, PostService

from external_services.mercadopago_api.controllers.mercadopago import MercadoPagoController

try:
    from dotenv import load_dotenv
    # Solo carga .env si existe el archivo
    if os.path.exists('.env'):
        load_dotenv(override=True)
        print("✅ Variables de entorno cargadas desde .env")
    else:
        print("ℹ️ Usando variables del sistema (producción)")
except ImportError:
    # En producción donde python-dotenv no está instalado
    print("ℹ️ python-dotenv no disponible, usando variables del sistema")
except Exception as e:
    print(f"⚠️ Error cargando .env: {e}")

engine = create_engine(
    os.getenv("DATABASE_URL")
)

class Services:
    def __init__(self):
        self.exampleService = ExampleService()
        self.userService = UserService()
        self.supabaseService = SupabaseService()

        self.authorService = AuthorService()
        self.postService = PostService()
        
        self.mercadoPagoController = MercadoPagoController(
            access_token=os.getenv("MERCADOPAGO_ACESS_TOKEN")
        )

_services_instance: Services | None = None

def get_engine():
    return engine

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def reset_database():
    """
    Elimina todas las tablas de la base de datos y las vuelve a crear.
    Útil para testing cuando necesitas un estado limpio.
    """
    # Eliminar todas las tablas
    SQLModel.metadata.drop_all(engine)
    # Volver a crear todas las tablas
    create_db_and_tables()
    print("Base de datos reseteada exitosamente")

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