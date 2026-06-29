"""
Jobs del scheduler para notificaciones automáticas.
- Recordatorio de exámenes próximos (diario 8:00 AM)
- Recordatorio de cierre de inscripción (diario 9:00 AM)
"""
from utils.logger import show


def recordatorio_examenes():
    """
    Job diario: busca exámenes en X días y envía recordatorio a inscriptos.
    Usa get_db_session() porque corre fuera de contexto de request.
    """
    try:
        show("NOTIF", "Iniciando job de recordatorio de exámenes próximos", "info")
        from database.database import get_db_session
        from v2.services import get_v2_services

        with get_db_session() as session:
            get_v2_services().notificationService.notificar_recordatorio_examen(session)
            session.commit()

        show("NOTIF", "Job de recordatorio de exámenes completado", "success")
    except Exception as e:
        show("NOTIF", f"Error en job recordatorio exámenes: {e}", "error")
        import traceback
        traceback.print_exc()


def recordatorio_cierre_inscripcion():
    """
    Job diario: busca períodos de inscripción cerrando pronto y avisa a estudiantes.
    """
    try:
        show("NOTIF", "Iniciando job de recordatorio de cierre de inscripción", "info")
        from database.database import get_db_session
        from v2.services import get_v2_services

        with get_db_session() as session:
            get_v2_services().notificationService.notificar_cierre_inscripcion_proximo(session)
            session.commit()

        show("NOTIF", "Job de recordatorio de cierre completado", "success")
    except Exception as e:
        show("NOTIF", f"Error en job recordatorio cierre: {e}", "error")
        import traceback
        traceback.print_exc()
