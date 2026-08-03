import os
import pathlib
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from scalar_fastapi import get_scalar_api_reference, Layout

from contextlib import asynccontextmanager

from routes import auth, career, testimony, news
from routes.moodle import moodle_user, moodle_category, moodle_course, moodle_enrolment
from routes.mercadopago import mercadopago
from routes.google import google_test, google_analytics
V2_ENABLED = os.getenv("V2_ENABLED", "false").lower() == "true"

if V2_ENABLED:
    from v2.routes import auth_google as v2_auth_google
    from v2.routes import (
        politicas_calificacion as v2_politicas_calificacion,
        politicas_examen as v2_politicas_examen,
        programas as v2_programas,
        materias as v2_materias,
        previaturas as v2_previaturas,
        instancias_evaluacion as v2_instancias_evaluacion,
        instancias_cursado as v2_instancias_cursado,
        docentes_materia as v2_docentes_materia,
        periodos_inscripcion as v2_periodos_inscripcion,
        estudiante as v2_estudiante,
        admin_inscripciones as v2_admin_inscripciones,
        docente as v2_docente,
        instancias_examen as v2_instancias_examen,
        admin_examenes as v2_admin_examenes,
        admin_documentos as v2_admin_documentos,
        admin_notificaciones as v2_admin_notificaciones,
        admin_usuarios as v2_admin_usuarios,
        admin_excepciones as v2_admin_excepciones,
        inicio as v2_inicio,
    )

from pages.welcome import html
from database.database import create_db_and_tables

from zoneinfo import ZoneInfo
from datetime import datetime

try:
    from dotenv import load_dotenv
    # Solo carga .env si existe el archivo
    if os.path.exists('.env'):
        load_dotenv(override=True)
        print("[OK] Variables de entorno cargadas desde .env")
    else:
        print("[INFO] Usando variables del sistema (producción)")
except ImportError:
    # En producción donde python-dotenv no está instalado
    print("[INFO] python-dotenv no disponible, usando variables del sistema")
except Exception as e:
    print(f"[WARN] Error cargando .env: {e}")

from routes.test import test_filters
from utils.logger import show

def get_uruguay_tz():
    """Lee la variable cada vez que se llama"""
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)

# Resultado del arranque del scheduler, para reportarlo en /health.
#
# Distingue tres situaciones que no son lo mismo: "corriendo", "deshabilitado
# a proposito" (el scheduler solo corre en produccion) y "fallo". Un unico
# booleano diria ok=True en desarrollo, donde en realidad no hay ningun job
# programado, y ese campo tiene que ser confiable para servir de algo.
ESTADO_SCHEDULER = {"estado": "sin_iniciar", "error": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    startup_success = False
    try:
        # Antes que nada: configuracion critica. Si falta SECRET_KEY en produccion
        # no se arranca, en vez de servir firmando tokens con el literal publico
        # del repositorio.
        from utils.config_guard import exigir_configuracion_critica
        exigir_configuracion_critica()

        print("[..] [STARTUP] Iniciando configuración de base de datos...")
        from database.database import engine, get_services, get_db_session
        from sqlalchemy import text

        print("[..] [STARTUP] Probando conexión a PostgreSQL...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("[OK] [STARTUP] Conexión a PostgreSQL exitosa")

        print("[..] [STARTUP] Creando tablas...")
        create_db_and_tables()
        print("[OK] [STARTUP] Base de datos y tablas creadas/verificadas")

        # Cache warmup for careers
        print("[..] [STARTUP] Iniciando precarga de cache para carreras...")
        try:
            services = get_services()
            with get_db_session() as session:
                warmup_result = services.cacheService.warmup_published_careers(
                    session=session,
                    career_service=services.careerService
                )
                if warmup_result:
                    print("[OK] [STARTUP] Cache de carreras precargado exitosamente")
                else:
                    print("[WARN] [STARTUP] No se encontraron carreras para precargar en cache")
        except Exception as cache_error:
            print(f"[WARN] [STARTUP] Error precargando cache (no crítico): {cache_error}")
            # No lanzamos el error porque el cache no es crítico para el startup

        # Iniciar scheduler para tareas programadas
        print("[..] [STARTUP] Iniciando scheduler de tareas programadas...")
        try:
            from utils.scheduler import start_scheduler, scheduler
            start_scheduler()
            # start_scheduler() sale sin hacer nada fuera de produccion, y sin
            # error. Se consulta el scheduler real para no reportar "ok" cuando
            # en verdad no hay ningun job programado.
            if scheduler.running:
                ESTADO_SCHEDULER.update({"estado": "corriendo", "error": None})
                print(f"[OK] [STARTUP] Scheduler corriendo con {len(scheduler.get_jobs())} tareas")
            else:
                ESTADO_SCHEDULER.update({"estado": "deshabilitado", "error": None})
                print("[..] [STARTUP] Scheduler deshabilitado (solo corre en production)")
        except Exception as scheduler_error:
            # NO es "no crítico". Este mensaje decía eso y por eso faltó
            # apscheduler en requirements durante tres meses sin que nadie lo
            # notara: la app respondía sana y ningún job corría, incluido el
            # keepalive que evita que se pause el proyecto de Supabase.
            #
            # No se corta el arranque —la API sirve igual sin jobs— pero el fallo
            # queda registrado y se expone en /health, que es lo que mira el
            # monitoreo.
            ESTADO_SCHEDULER.update({"estado": "error", "error": str(scheduler_error)})
            print("=" * 70)
            print("[ERROR] [STARTUP] EL SCHEDULER NO ARRANCO. LAS TAREAS")
            print("[ERROR] [STARTUP] PROGRAMADAS NO VAN A EJECUTARSE.")
            print(f"[ERROR] [STARTUP] Motivo: {scheduler_error}")
            print("[ERROR] [STARTUP] Sin jobs quedan sin correr, entre otros, el")
            print("[ERROR] [STARTUP] keepalive de Supabase y los recordatorios a alumnos.")
            print("[ERROR] [STARTUP] Ver GET /health -> scheduler")
            print("=" * 70)

        # Pre-fetch inicial de datos de Google Analytics (en thread para no bloquear startup)
        try:
            import threading
            from utils.jobs.analytics_prefetch import prefetch_analytics_data
            threading.Thread(target=prefetch_analytics_data, daemon=True).start()
            print("[..] [STARTUP] Pre-fetch de analytics iniciado en background")
        except Exception as prefetch_error:
            print(f"[WARN] [STARTUP] Error iniciando pre-fetch de analytics (no crítico): {prefetch_error}")

        startup_success = True
        print("[OK] [STARTUP] TODO EL STARTUP COMPLETADO EXITOSAMENTE")

    except Exception as e:
        print(f"[ERROR] [STARTUP] ERROR CRÍTICO: {e}")
        print(f"[ERROR] [STARTUP] Tipo: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        raise e  # Esto hará que falle el startup

    if startup_success:
        print("[OK] [LIFESPAN] Aplicación lista para recibir requests")

    yield  # La aplicación funciona aquí

    # Shutdown
    print("[..] [SHUTDOWN] Iniciando proceso de cierre...")

    # Detener scheduler
    try:
        from utils.scheduler import stop_scheduler
        stop_scheduler()
    except Exception as e:
        print(f"[WARN] [SHUTDOWN] Error deteniendo scheduler: {e}")

    # Cerrar conexión a base de datos
    try:
        from database.database import engine
        engine.dispose()
        print("[OK] [SHUTDOWN] Recursos liberados correctamente")
    except Exception as e:
        print(f"[WARN] [SHUTDOWN] Error: {e}")

    print("👋 [SHUTDOWN] Aplicación cerrada")

    
app = FastAPI(
    title="Backend CTC",
    description="Backend para la aplicación CTC",
    version="0.0.15",
    lifespan=lifespan  # Para iniciar la base de datos y cache
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

@app.get("/health")
async def health():
    # `status` se mantiene en OK aunque el scheduler este caido: si devolviera
    # error, el health check del orquestador reiniciaria el contenedor en loop
    # por algo que no impide servir la API. El detalle va en su propio campo,
    # que es donde el monitoreo lo puede ver sin tirar abajo el deploy.
    return {
        "status": "OK",
        "version": app.version,
        "time": datetime.now(get_uruguay_tz()).isoformat(),
        "timezone": os.getenv('TIME_ZONE', 'UTC'),
        # estado: corriendo | deshabilitado | error | sin_iniciar
        "scheduler": dict(ESTADO_SCHEDULER),
    }

@app.get("/scheduler/status")
async def scheduler_status():
    """Endpoint para verificar el estado del scheduler y las tareas programadas"""
    try:
        from utils.scheduler import scheduler

        if not scheduler.running:
            return {
                "status": "stopped",
                "message": "El scheduler no está corriendo"
            }

        jobs = []
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })

        return {
            "status": "running",
            "jobs": jobs,
            "timezone": str(scheduler.timezone)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
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

# Google Workspace
app.include_router(google_test.router)

# Google Analytics
app.include_router(google_analytics.router)

# v2 - Portal Academico (solo si V2_ENABLED=true)
if V2_ENABLED:
    app.include_router(v2_auth_google.router)
    app.include_router(v2_politicas_calificacion.router)
    app.include_router(v2_politicas_examen.router)
    app.include_router(v2_programas.router)
    app.include_router(v2_materias.router)
    app.include_router(v2_previaturas.router)
    app.include_router(v2_instancias_evaluacion.router)
    app.include_router(v2_instancias_cursado.router)
    app.include_router(v2_docentes_materia.router)
    app.include_router(v2_periodos_inscripcion.router)
    app.include_router(v2_estudiante.router)
    app.include_router(v2_admin_inscripciones.router)
    app.include_router(v2_docente.router)
    app.include_router(v2_instancias_examen.router)
    app.include_router(v2_admin_examenes.router)
    app.include_router(v2_admin_documentos.router)
    app.include_router(v2_admin_notificaciones.router)
    app.include_router(v2_admin_usuarios.router)
    app.include_router(v2_admin_excepciones.router)
    app.include_router(v2_inicio.router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware (requerido por authlib para OAuth state)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "your-secret-key-change-in-production"),
)

# Proxy headers middleware (Easypanel/Traefik termina SSL, necesario para OAuth redirect HTTPS)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# ── Frontend SvelteKit (admin panel) ─────────────────────────────────────────
frontend_build = pathlib.Path(__file__).parent / "frontend" / "build"
if frontend_build.exists():
    app.mount("/admin/_app", StaticFiles(directory=frontend_build / "_app"), name="svelte_assets")

    @app.get("/admin/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(frontend_build / "index.html")

    @app.get("/admin")
    async def serve_spa_root():
        return FileResponse(frontend_build / "index.html")

# ── Frontend Test Login (prueba OAuth Google) ────────────────────────────────
test_login_build = pathlib.Path(__file__).parent / "frontend-test-login" / "build"
if test_login_build.exists():
    app.mount("/test-login/_app", StaticFiles(directory=test_login_build / "_app"), name="test_login_assets")

    @app.get("/test-login/{full_path:path}")
    async def serve_test_login(full_path: str):
        return FileResponse(test_login_build / "index.html")

    @app.get("/test-login")
    async def serve_test_login_root():
        return FileResponse(test_login_build / "index.html")

if __name__ == "__main__":
    # run command -> python main.py
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", port=port, host="0.0.0.0")