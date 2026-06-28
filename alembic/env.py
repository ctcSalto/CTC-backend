from logging.config import fileConfig
import sys
import os
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import engine_from_config, pool
from alembic import context
from sqlmodel import SQLModel

try:
    from dotenv import load_dotenv
    # Solo carga .env si existe el archivo
    if os.path.exists('.env'):
        load_dotenv(override=True)
        print("[OK] Variables de entorno cargadas desde .env")
    else:
        print("[INFO] Usando variables del sistema (produccion)")
except ImportError:
    # En producción donde python-dotenv no está instalado
    print("[INFO] python-dotenv no disponible, usando variables del sistema")
except Exception as e:
    print(f"[WARN] Error cargando .env: {e}")

# Importa todos tus modelos aquí para que Alembic los detecte
# IMPORTANTE: Asegúrate de que estas importaciones sean correctas según tu estructura
try:
    from database.models.example import Example
    from database.models.user import User
    from database.models.career import Career
    from database.models.testimony import Testimony
    from database.models.testimony_video import TestimonyVideo
    from database.models.news import News
    # Modelos v2 - Portal Académico
    import v2.models  # noqa: F401 - Registra todos los modelos v2 en SQLModel.metadata
    print("[OK] Modelos v1 y v2 importados correctamente")
except ImportError as e:
    print(f"[ERROR] Error importando modelos: {e}")
    print("Estructura actual del directorio:")
    print(f"   - Directorio actual: {os.getcwd()}")
    print(f"   - Directorio del script: {Path(__file__).parent}")
    print(f"   - Directorio raíz del proyecto: {project_root}")
    
    # Listar archivos para debug
    try:
        db_path = project_root / "database" / "models"
        if db_path.exists():
            print(f"   - Archivos en {db_path}:")
            for file in db_path.iterdir():
                print(f"     * {file.name}")
    except Exception:
        pass
    
    raise e

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = SQLModel.metadata

def get_database_url():
    """Obtener URL de base de datos desde variables de entorno o configuración"""
    # Intentar obtener desde variables de entorno primero
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        print("[OK] Usando DATABASE_URL desde variables de entorno")
        return database_url
    
    # Fallback a la configuración del alembic.ini
    url = config.get_main_option("sqlalchemy.url")
    if url:
        print("[OK] Usando URL desde alembic.ini")
        return url
    
    # URL por defecto para desarrollo
    default_url = "sqlite:///./database.db"
    print(f"[WARN] Usando URL por defecto: {default_url}")
    return default_url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # Comparar tipos de columnas
        compare_server_default=True,  # Comparar valores por defecto
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Obtener configuración
    config_section = config.get_section(config.config_ini_section, {})
    
    # Sobrescribir la URL de base de datos
    config_section["sqlalchemy.url"] = get_database_url()
    
    connectable = engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True,  # Comparar tipos de columnas
            compare_server_default=True,  # Comparar valores por defecto
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
