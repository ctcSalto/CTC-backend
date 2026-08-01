"""
Scheduler para tareas programadas del sistema.

Configuración de cron jobs para ejecutar tareas automáticas.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pytz import timezone
import requests
import os
from utils.logger import show

# Timezone de Uruguay
URUGUAY_TZ = timezone('America/Montevideo')

# Crear scheduler global
scheduler = BackgroundScheduler(timezone=URUGUAY_TZ)


def supabase_keepalive():
    """
    Consulta mínima diaria a Supabase para evitar que el proyecto free tier sea pausado.
    Supabase pausa proyectos gratuitos tras 1 semana sin actividad.
    """
    try:
        from database.database import get_services
        services = get_services()
        services.supabaseService.client.storage.list_buckets()
        show("CRON", "Supabase keepalive OK", "info")
    except Exception as e:
        show("CRON", f"Supabase keepalive error: {e}", "warning")


def actualizar_fotos_perfil_moodle():
    """
    Tarea programada para actualizar fotos de perfil en Moodle.
    Se ejecuta semanalmente a las 2am (hora de Montevideo).
    """
    try:
        show("CRON", "Iniciando actualización programada de fotos de perfil en Moodle", "info")

        # Determinar la URL base del servidor
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        endpoint = f"{base_url}/api/moodle/usuarios/actualizar-fotos-perfil"

        # Hacer request al endpoint
        response = requests.post(endpoint, timeout=30.0)

        if response.status_code == 200:
            show("CRON", f"✅ Actualización de fotos iniciada exitosamente: {response.json()}", "success")
        else:
            show("CRON", f"⚠️ Error al iniciar actualización: {response.status_code} - {response.text}", "warning")

    except Exception as e:
        show("CRON", f"❌ Error ejecutando tarea programada: {e}", "error")
        import traceback
        traceback.print_exc()


def start_scheduler():
    """
    Inicia el scheduler y configura todas las tareas programadas.
    Debe ser llamado durante el startup de la aplicación.

    IMPORTANTE: Solo se ejecuta en entorno de producción.
    """
    try:
        # Verificar si estamos en producción
        environment = os.getenv("ENVIRONMENT", "development").lower()

        if environment != "production":
            show("SCHEDULER", f"⚠️ Scheduler deshabilitado en entorno '{environment}' (solo se ejecuta en production)", "warning")
            return

        # Configurar tarea: Actualizar fotos de perfil cada semana a las 2am
        scheduler.add_job(
            actualizar_fotos_perfil_moodle,
            trigger=CronTrigger(
                day_of_week='sun',  # Domingo
                hour=2,              # 2 AM
                minute=0,            # En punto
                timezone=URUGUAY_TZ
            ),
            id='actualizar_fotos_perfil_moodle',
            name='Actualizar fotos de perfil en Moodle',
            replace_existing=True
        )

        # Configurar tarea: Pre-fetch de datos de Google Analytics cada 2 horas
        from utils.jobs.analytics_prefetch import prefetch_analytics_data
        scheduler.add_job(
            prefetch_analytics_data,
            trigger=IntervalTrigger(hours=4, timezone=URUGUAY_TZ),
            id='prefetch_analytics_data',
            name='Pre-fetch datos de Google Analytics',
            replace_existing=True
        )

        # Configurar tarea: Notificaciones de apertura (diario, antes de los recordatorios)
        from utils.jobs.notificaciones_jobs import (
            recordatorio_examenes, recordatorio_cierre_inscripcion,
            apertura_inscripcion, apertura_examen,
        )
        scheduler.add_job(
            apertura_inscripcion,
            trigger=CronTrigger(
                hour=7,
                minute=0,
                timezone=URUGUAY_TZ
            ),
            id='apertura_inscripcion',
            name='Aviso de apertura de inscripcion a materias',
            replace_existing=True
        )

        scheduler.add_job(
            apertura_examen,
            trigger=CronTrigger(
                hour=7,
                minute=30,
                timezone=URUGUAY_TZ
            ),
            id='apertura_examen',
            name='Aviso de apertura de inscripcion a examenes',
            replace_existing=True
        )

        # Configurar tarea: Recordatorio de exámenes próximos (diario 8:00 AM)
        scheduler.add_job(
            recordatorio_examenes,
            trigger=CronTrigger(
                hour=8,
                minute=0,
                timezone=URUGUAY_TZ
            ),
            id='recordatorio_examenes',
            name='Recordatorio de examenes proximos',
            replace_existing=True
        )

        # Configurar tarea: Recordatorio cierre de inscripción (diario 9:00 AM)
        scheduler.add_job(
            recordatorio_cierre_inscripcion,
            trigger=CronTrigger(
                hour=9,
                minute=0,
                timezone=URUGUAY_TZ
            ),
            id='recordatorio_cierre_inscripcion',
            name='Recordatorio de cierre de inscripcion',
            replace_existing=True
        )

        # Configurar tarea: Supabase keepalive diario (00:30 AM) para evitar pausa del proyecto free
        scheduler.add_job(
            supabase_keepalive,
            trigger=CronTrigger(
                hour=0,
                minute=30,
                timezone=URUGUAY_TZ
            ),
            id='supabase_keepalive',
            name='Supabase keepalive diario',
            replace_existing=True
        )

        # Iniciar el scheduler
        scheduler.start()

        show("SCHEDULER", "Scheduler iniciado correctamente en PRODUCCION", "success")
        show("SCHEDULER", f"Proxima actualizacion de fotos: {scheduler.get_job('actualizar_fotos_perfil_moodle').next_run_time}", "info")

    except Exception as e:
        show("SCHEDULER", f"❌ Error iniciando scheduler: {e}", "error")
        import traceback
        traceback.print_exc()


def stop_scheduler():
    """
    Detiene el scheduler.
    Debe ser llamado durante el shutdown de la aplicación.
    """
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            show("SCHEDULER", "✅ Scheduler detenido correctamente", "success")
    except Exception as e:
        show("SCHEDULER", f"⚠️ Error deteniendo scheduler: {e}", "warning")
