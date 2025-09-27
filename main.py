from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference, Layout

from contextlib import asynccontextmanager

from routes import auth, career, testimony, news
from routes.moodle import moodle_user, moodle_category, moodle_course, moodle_enrolment
from routes.mercadopago import mercadopago

from pages.welcome import html
from database.database import reset_database, create_db_and_tables

import os
from zoneinfo import ZoneInfo
from datetime import datetime

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

from routes.test import test_filters
from utils.logger import show

uruguay_tz = ZoneInfo(os.getenv('TIME_ZONE')) if os.getenv('TIME_ZONE') else ZoneInfo('America/Montevideo')


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    startup_success = False
    try:
        print("🔄 [STARTUP] Iniciando configuración de base de datos...")
        from database.database import engine
        from sqlalchemy import text
        
        print("🔄 [STARTUP] Probando conexión a PostgreSQL...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ [STARTUP] Conexión a PostgreSQL exitosa")
        
        print("🔄 [STARTUP] Creando tablas...")
        create_db_and_tables()
        print("✅ [STARTUP] Base de datos y tablas creadas/verificadas")
        
        startup_success = True
        print("🎉 [STARTUP] TODO EL STARTUP COMPLETADO EXITOSAMENTE")
        
    except Exception as e:
        print(f"❌ [STARTUP] ERROR CRÍTICO: {e}")
        print(f"❌ [STARTUP] Tipo: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        raise e  # Esto hará que falle el startup
    
    if startup_success:
        print("🚀 [LIFESPAN] Aplicación lista para recibir requests")
    
    yield  # La aplicación funciona aquí
    
    # Shutdown
    print("🔄 [SHUTDOWN] Iniciando proceso de cierre...")
    try:
        from database.database import engine
        engine.dispose()
        print("✅ [SHUTDOWN] Recursos liberados correctamente")
    except Exception as e:
        print(f"⚠️ [SHUTDOWN] Error: {e}")
    
    print("👋 [SHUTDOWN] Aplicación cerrada")

    
app = FastAPI(
    title="Backend CTC",
    description="Backend para la aplicación CTC",
    version="0.0.15",
    #lifespan=lifespan  # Para iniciar la base de datos
)

@app.get("/docs-scalar", include_in_schema=False)
async def scalar_docs():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Scalar API Docs - CTC",
        layout=Layout.MODERN,
        dark_mode=True,
        show_sidebar=True,
        default_open_all_tags=True,
        hide_download_button=True,
        hide_models=True,
    )

@app.get("/" , response_class=HTMLResponse)
def root():
    return html

@app.get("/generate-permanent-token")
def generate_permanent_token():
    return ""

@app.get("/reset-database")
def reset_db():
    reset_database()
    return {"message": "Database reset successfully"}

@app.get("/health")
async def health():
    return {
        "status": "OK", 
        "version": app.version, 
        "time": datetime.now(uruguay_tz).isoformat(),
        "timezone": os.getenv('TIME_ZONE', 'UTC')
    }

# Routers
app.include_router(auth.router)
app.include_router(career.router)
app.include_router(testimony.router)
app.include_router(news.router)

app.include_router(moodle_user.router)
app.include_router(moodle_category.router)
app.include_router(moodle_course.router)
app.include_router(moodle_enrolment.router)

app.include_router(mercadopago.router)
app.include_router(test_filters.router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    # run command -> python main.py
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", port=port, host="0.0.0.0")