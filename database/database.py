from sqlmodel import SQLModel, create_engine, Session
from contextlib import contextmanager
from dotenv import load_dotenv
import os

from .models.user import User
from .models.career import Career
from .models.testimony import Testimony
from .models.news import News

from .services.user_service import UserService
from .services.carrer_service import CareerService
from .services.testimony_service import TestimonyService
from .services.news_services import NewsService

from .services.supabase.image_service import SupabaseService
from .services.redis.redis import RedisService

#-------------------MERCADO PAGO------------------------------

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
    os.getenv("DATABASE_URL"),
    pool_pre_ping=True,
    pool_recycle=3600,  # 1 hora
    echo=False
)

class Services:
    def __init__(self):
        # Entity Services
        self.userService = UserService()
        self.careerService = CareerService()
        self.testimonyService = TestimonyService()
        self.newsService = NewsService()
        
        # Utils Services
        self.supabaseService = SupabaseService()
        self.mercadoPagoController = MercadoPagoController(
            access_token=os.getenv("MERCADOPAGO_ACESS_TOKEN")
        )
        self.redisService = RedisService()

_services_instance: Services | None = None

def get_engine():
    return engine

def create_db_and_tables():
    """
    Crea las tablas solo si no existen.
    SQLAlchemy verifica automáticamente la existencia.
    """
    try:
        # SQLAlchemy solo crea las tablas que NO existen
        SQLModel.metadata.create_all(bind=engine, checkfirst=True)
        print("✅ Verificación de tablas completada")
    except Exception as e:
        print(f"❌ Error creando/verificando tablas: {e}")
        raise

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
    """Dependency para FastAPI que maneja la sesión correctamente"""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
        

@contextmanager
def get_db_session():
    """Para uso fuera de FastAPI"""
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

def init_services():
    return Services()

def get_services():
    global _services_instance
    if _services_instance is None:
        _services_instance = init_services()
    return _services_instance