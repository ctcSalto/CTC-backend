"""
Servicio de orquestación de notificaciones del portal académico.
Decide QUÉ enviar, renderiza templates con variables, y registra en log.

Usa EmailService para la entrega. No envía emails directamente.
"""
import os
from datetime import datetime, date, timedelta
from typing import Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlmodel import Session, select, col

from v2.services.email_service import EmailService
from v2.models.notificacion import NotificacionLog
from v2.models.enums import (
    TipoNotificacion, CanalNotificacion, EstadoNotificacion,
    EstadoInscripcionMateria, EstadoInscripcionExamen,
    EstadoInscripcionPrograma,
)
from v2.templates.email_templates import TEMPLATES
from utils.logger import ic


def _get_tz():
    return ZoneInfo(os.getenv('TIME_ZONE', 'America/Montevideo'))


def _format_fecha(dt: Optional[datetime]) -> str:
    """Formatea datetime a string legible."""
    if dt is None:
        return "No definida"
    return dt.strftime("%d/%m/%Y")


def _format_hora(hora: Optional[str]) -> str:
    return hora or "A confirmar"


# Mapeo de estado a texto legible
_ESTADO_LABELS = {
    EstadoInscripcionMateria.CURSANDO: "Cursando",
    EstadoInscripcionMateria.EXONERADO: "Exonerado",
    EstadoInscripcionMateria.A_EXAMEN: "A examen",
    EstadoInscripcionMateria.APROBADO: "Aprobado",
    EstadoInscripcionMateria.REPROBADO: "Reprobado",
    EstadoInscripcionMateria.PERDIDO_INASISTENCIA: "Perdido por inasistencia",
    EstadoInscripcionMateria.ABANDONO: "Abandono",
    EstadoInscripcionMateria.REVALIDADA: "Revalidada",
}


class NotificationService:
    """Orquesta las notificaciones del portal académico."""

    def __init__(self):
        self.email_service = EmailService()

    # ── Helpers internos ─────────────────────────────────────────────────────

    def _get_email_destinatario(self, usuario) -> str:
        """Retorna email_personal si existe, sino email institucional."""
        return usuario.email_personal or usuario.email

    def _renderizar(self, template_key: str, variables: dict) -> str:
        """Renderiza un template HTML con las variables dadas."""
        template = TEMPLATES.get(template_key)
        if not template:
            raise ValueError(f"Template no encontrado: {template_key}")
        return template.format(**variables)

    def _registrar_log(
        self,
        tipo: TipoNotificacion,
        usuario_id: int,
        email_destino: str,
        asunto: str,
        session: Session,
        referencia_id: Optional[int] = None,
        referencia_tipo: Optional[str] = None,
        estado: EstadoNotificacion = EstadoNotificacion.ENVIADA,
        error_detalle: Optional[str] = None,
        enviado_por_id: Optional[int] = None,
    ) -> NotificacionLog:
        """Registra una notificación en el log."""
        log = NotificacionLog(
            tipo=tipo,
            canal=CanalNotificacion.EMAIL,
            usuario_id=usuario_id,
            email_destino=email_destino,
            asunto=asunto,
            referencia_id=referencia_id,
            referencia_tipo=referencia_tipo,
            estado=estado,
            error_detalle=error_detalle,
            enviado_por_id=enviado_por_id,
            fecha_envio=datetime.now(_get_tz()),
            id_rastreo=str(uuid4()),
        )
        session.add(log)
        session.flush()
        return log

    def _ya_enviada_hoy(
        self,
        tipo: TipoNotificacion,
        usuario_id: int,
        referencia_id: int,
        session: Session,
    ) -> bool:
        """Verifica si ya se envió una notificación del mismo tipo hoy (prevención duplicados)."""
        hoy = date.today()
        inicio_dia = datetime.combine(hoy, datetime.min.time()).replace(tzinfo=_get_tz())
        stmt = (
            select(NotificacionLog)
            .where(NotificacionLog.tipo == tipo)
            .where(NotificacionLog.usuario_id == usuario_id)
            .where(NotificacionLog.referencia_id == referencia_id)
            .where(NotificacionLog.estado == EstadoNotificacion.ENVIADA)
            .where(col(NotificacionLog.fecha_envio) >= inicio_dia)
        )
        return session.exec(stmt).first() is not None

    def _enviar_y_loguear(
        self,
        tipo: TipoNotificacion,
        usuario_id: int,
        email: str,
        asunto: str,
        html: str,
        session: Session,
        referencia_id: Optional[int] = None,
        referencia_tipo: Optional[str] = None,
        enviado_por_id: Optional[int] = None,
    ) -> dict:
        """Envía email y registra en log. Retorna resultado (incluye id_rastreo del log)."""
        resultado = self.email_service.send_single(email, asunto, html)

        estado = EstadoNotificacion.ENVIADA if resultado["ok"] else EstadoNotificacion.ERROR
        error = resultado.get("error") if not resultado["ok"] else None

        log = self._registrar_log(
            tipo=tipo,
            usuario_id=usuario_id,
            email_destino=email,
            asunto=asunto,
            session=session,
            referencia_id=referencia_id,
            referencia_tipo=referencia_tipo,
            estado=estado,
            error_detalle=error,
            enviado_por_id=enviado_por_id,
        )

        return {**resultado, "id_rastreo": log.id_rastreo}

    # ── Notificaciones automáticas ───────────────────────────────────────────

    def notificar_inscripcion_materia(
        self, inscripcion, usuario, materia, programa_nombre: str, anio_lectivo: int, session: Session
    ):
        """Notifica al estudiante que su inscripción a materia fue confirmada."""
        email = self._get_email_destinatario(usuario)
        asunto = f"Inscripción confirmada: {materia.nombre}"
        html = self._renderizar("inscripcion_materia", {
            "nombre": usuario.nombre,
            "materia": materia.nombre,
            "programa": programa_nombre,
            "anio_lectivo": anio_lectivo,
        })
        return self._enviar_y_loguear(
            tipo=TipoNotificacion.INSCRIPCION_MATERIA,
            usuario_id=usuario.id,
            email=email,
            asunto=asunto,
            html=html,
            session=session,
            referencia_id=inscripcion.id,
            referencia_tipo="inscripcion_materia",
        )

    def notificar_inscripcion_examen(
        self, inscripcion_examen, usuario, materia, instancia_examen, session: Session
    ):
        """Notifica al estudiante que su inscripción a examen fue confirmada."""
        email = self._get_email_destinatario(usuario)
        asunto = f"Inscripción a examen: {materia.nombre}"
        html = self._renderizar("inscripcion_examen", {
            "nombre": usuario.nombre,
            "materia": materia.nombre,
            "fecha_examen": _format_fecha(instancia_examen.fecha_examen),
            "hora": _format_hora(instancia_examen.hora),
            "salon": instancia_examen.salon or "A confirmar",
            "numero_rendicion": inscripcion_examen.numero_rendicion,
        })
        return self._enviar_y_loguear(
            tipo=TipoNotificacion.INSCRIPCION_EXAMEN,
            usuario_id=usuario.id,
            email=email,
            asunto=asunto,
            html=html,
            session=session,
            referencia_id=inscripcion_examen.id,
            referencia_tipo="inscripcion_examen",
        )

    def notificar_recordatorio_examen(self, session: Session):
        """
        Job del scheduler: busca exámenes próximos y envía recordatorio a inscriptos.
        Solo envía si no se envió recordatorio hoy para ese usuario+examen.
        """
        from v2.models.instancia_examen import InstanciaExamen
        from v2.models.inscripcion_examen import InscripcionExamen
        from v2.models.inscripcion_materia import InscripcionMateria
        from v2.models.usuario import Usuario
        from v2.models.materia import Materia

        dias = int(os.getenv("NOTIF_EXAM_REMINDER_DAYS", "3"))
        ahora = datetime.now(_get_tz())
        fecha_objetivo = ahora + timedelta(days=dias)
        inicio_dia = fecha_objetivo.replace(hour=0, minute=0, second=0, microsecond=0)
        fin_dia = fecha_objetivo.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Buscar exámenes en X días
        stmt = (
            select(InstanciaExamen)
            .where(col(InstanciaExamen.fecha_examen) >= inicio_dia)
            .where(col(InstanciaExamen.fecha_examen) <= fin_dia)
            .where(InstanciaExamen.habilitado == True)
        )
        examenes = session.exec(stmt).all()

        for examen in examenes:
            materia = session.get(Materia, examen.materia_id)
            if not materia:
                continue

            # Buscar inscriptos en estado INSCRIPTO
            stmt_insc = (
                select(InscripcionExamen)
                .where(InscripcionExamen.instancia_examen_id == examen.id)
                .where(InscripcionExamen.estado == EstadoInscripcionExamen.INSCRIPTO)
            )
            inscripciones = session.exec(stmt_insc).all()

            for insc_examen in inscripciones:
                insc_materia = session.get(InscripcionMateria, insc_examen.inscripcion_materia_id)
                if not insc_materia:
                    continue
                usuario = session.get(Usuario, insc_materia.usuario_id)
                if not usuario:
                    continue

                # Prevenir duplicados
                if self._ya_enviada_hoy(
                    TipoNotificacion.RECORDATORIO_EXAMEN, usuario.id, examen.id, session
                ):
                    continue

                email = self._get_email_destinatario(usuario)
                asunto = f"Recordatorio: examen de {materia.nombre} en {dias} día(s)"
                try:
                    html = self._renderizar("recordatorio_examen", {
                        "nombre": usuario.nombre,
                        "materia": materia.nombre,
                        "fecha_examen": _format_fecha(examen.fecha_examen),
                        "hora": _format_hora(examen.hora),
                        "salon": examen.salon or "A confirmar",
                        "dias_restantes": dias,
                    })
                    self._enviar_y_loguear(
                        tipo=TipoNotificacion.RECORDATORIO_EXAMEN,
                        usuario_id=usuario.id,
                        email=email,
                        asunto=asunto,
                        html=html,
                        session=session,
                        referencia_id=examen.id,
                        referencia_tipo="instancia_examen",
                    )
                except Exception as e:
                    ic(f"Error enviando recordatorio a {usuario.email}: {e}")

    def notificar_apertura_inscripcion(
        self, periodo, programa, session: Session
    ):
        """Notifica a todos los estudiantes activos del programa que se abrió inscripción."""
        from v2.models.inscripcion_programa import InscripcionPrograma
        from v2.models.alumno import Alumno
        from v2.models.usuario import Usuario

        # Buscar alumnos activos en el programa
        stmt = (
            select(InscripcionPrograma)
            .where(InscripcionPrograma.programa_id == programa.id)
            .where(InscripcionPrograma.estado == EstadoInscripcionPrograma.ACTIVA)
        )
        inscripciones = session.exec(stmt).all()

        for insc_prog in inscripciones:
            alumno = session.get(Alumno, insc_prog.alumno_id)
            if not alumno:
                continue
            usuario = session.get(Usuario, alumno.usuario_id)
            if not usuario or not usuario.activo:
                continue

            email = self._get_email_destinatario(usuario)
            asunto = f"Inscripción abierta: {programa.nombre}"
            try:
                html = self._renderizar("apertura_inscripcion", {
                    "nombre": usuario.nombre,
                    "programa": programa.nombre,
                    "anio_lectivo": periodo.anio_lectivo,
                    "fecha_inicio": _format_fecha(periodo.fecha_inicio),
                    "fecha_fin": _format_fecha(periodo.fecha_fin),
                })
                self._enviar_y_loguear(
                    tipo=TipoNotificacion.APERTURA_INSCRIPCION,
                    usuario_id=usuario.id,
                    email=email,
                    asunto=asunto,
                    html=html,
                    session=session,
                    referencia_id=periodo.id,
                    referencia_tipo="periodo_inscripcion_materia",
                )
            except Exception as e:
                ic(f"Error notificando apertura a {usuario.email}: {e}")

    def notificar_apertura_examen(
        self, instancia_examen, materia, session: Session
    ):
        """Notifica a estudiantes en estado A_EXAMEN para esa materia."""
        from v2.models.inscripcion_materia import InscripcionMateria
        from v2.models.instancia_cursado import InstanciaCursado
        from v2.models.usuario import Usuario

        # Buscar inscripciones en A_EXAMEN para esta materia
        stmt = (
            select(InscripcionMateria)
            .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .where(InstanciaCursado.materia_id == materia.id)
            .where(InscripcionMateria.estado == EstadoInscripcionMateria.A_EXAMEN)
        )
        inscripciones = session.exec(stmt).all()

        for insc in inscripciones:
            usuario = session.get(Usuario, insc.usuario_id)
            if not usuario or not usuario.activo:
                continue

            email = self._get_email_destinatario(usuario)
            asunto = f"Examen disponible: {materia.nombre}"
            try:
                html = self._renderizar("apertura_examen", {
                    "nombre": usuario.nombre,
                    "materia": materia.nombre,
                    "fecha_examen": _format_fecha(instancia_examen.fecha_examen),
                    "fecha_fin_inscripcion": _format_fecha(instancia_examen.fecha_fin_inscripcion),
                })
                self._enviar_y_loguear(
                    tipo=TipoNotificacion.APERTURA_EXAMEN,
                    usuario_id=usuario.id,
                    email=email,
                    asunto=asunto,
                    html=html,
                    session=session,
                    referencia_id=instancia_examen.id,
                    referencia_tipo="instancia_examen",
                )
            except Exception as e:
                ic(f"Error notificando examen a {usuario.email}: {e}")

    def notificar_cierre_inscripcion_proximo(self, session: Session):
        """Job del scheduler: busca períodos cerrando pronto y avisa a estudiantes del programa."""
        from v2.models.periodo_inscripcion_materia import PeriodoInscripcionMateria
        from v2.models.programa import Programa

        dias = int(os.getenv("NOTIF_ENROLLMENT_CLOSING_DAYS", "2"))
        ahora = datetime.now(_get_tz())
        fecha_objetivo = ahora + timedelta(days=dias)
        inicio_dia = fecha_objetivo.replace(hour=0, minute=0, second=0, microsecond=0)
        fin_dia = fecha_objetivo.replace(hour=23, minute=59, second=59, microsecond=999999)

        stmt = (
            select(PeriodoInscripcionMateria)
            .where(col(PeriodoInscripcionMateria.fecha_fin) >= inicio_dia)
            .where(col(PeriodoInscripcionMateria.fecha_fin) <= fin_dia)
            .where(PeriodoInscripcionMateria.habilitado == True)
        )
        periodos = session.exec(stmt).all()

        for periodo in periodos:
            programa = session.get(Programa, periodo.programa_id)
            if not programa:
                continue

            # Reusar la lógica de apertura pero con template de cierre
            from v2.models.inscripcion_programa import InscripcionPrograma
            from v2.models.alumno import Alumno
            from v2.models.usuario import Usuario

            stmt_insc = (
                select(InscripcionPrograma)
                .where(InscripcionPrograma.programa_id == programa.id)
                .where(InscripcionPrograma.estado == EstadoInscripcionPrograma.ACTIVA)
            )
            inscripciones = session.exec(stmt_insc).all()

            for insc_prog in inscripciones:
                alumno = session.get(Alumno, insc_prog.alumno_id)
                if not alumno:
                    continue
                usuario = session.get(Usuario, alumno.usuario_id)
                if not usuario or not usuario.activo:
                    continue

                if self._ya_enviada_hoy(
                    TipoNotificacion.CIERRE_INSCRIPCION, usuario.id, periodo.id, session
                ):
                    continue

                email = self._get_email_destinatario(usuario)
                asunto = f"Cierre de inscripción: {programa.nombre} en {dias} día(s)"
                try:
                    html = self._renderizar("cierre_inscripcion", {
                        "nombre": usuario.nombre,
                        "programa": programa.nombre,
                        "fecha_fin": _format_fecha(periodo.fecha_fin),
                        "dias_restantes": dias,
                    })
                    self._enviar_y_loguear(
                        tipo=TipoNotificacion.CIERRE_INSCRIPCION,
                        usuario_id=usuario.id,
                        email=email,
                        asunto=asunto,
                        html=html,
                        session=session,
                        referencia_id=periodo.id,
                        referencia_tipo="periodo_inscripcion_materia",
                    )
                except Exception as e:
                    ic(f"Error notificando cierre a {usuario.email}: {e}")

    def notificar_reprobado_rendiciones(
        self, inscripcion_materia, usuario, materia, rendiciones_usadas: int, max_rendiciones: int, session: Session
    ):
        """Notifica al estudiante que agotó las rendiciones de examen."""
        email = self._get_email_destinatario(usuario)
        asunto = f"Rendiciones agotadas: {materia.nombre}"
        html = self._renderizar("reprobado_rendiciones", {
            "nombre": usuario.nombre,
            "materia": materia.nombre,
            "rendiciones_usadas": rendiciones_usadas,
            "max_rendiciones": max_rendiciones,
        })
        self._enviar_y_loguear(
            tipo=TipoNotificacion.REPROBADO_RENDICIONES,
            usuario_id=usuario.id,
            email=email,
            asunto=asunto,
            html=html,
            session=session,
            referencia_id=inscripcion_materia.id,
            referencia_tipo="inscripcion_materia",
        )

    def notificar_baja_procesada(
        self, inscripcion_programa, usuario, programa, session: Session
    ):
        """Notifica al estudiante que su baja del programa fue procesada."""
        email = self._get_email_destinatario(usuario)
        asunto = f"Baja procesada: {programa.nombre}"
        html = self._renderizar("baja_procesada", {
            "nombre": usuario.nombre,
            "programa": programa.nombre,
            "fecha_baja": _format_fecha(inscripcion_programa.fecha_baja),
            "motivo": inscripcion_programa.motivo_baja or "No especificado",
        })
        self._enviar_y_loguear(
            tipo=TipoNotificacion.BAJA_PROCESADA,
            usuario_id=usuario.id,
            email=email,
            asunto=asunto,
            html=html,
            session=session,
            referencia_id=inscripcion_programa.id,
            referencia_tipo="inscripcion_programa",
        )

    # ── Semi-automáticas (admin-triggered) ───────────────────────────────────

    def notificar_calificacion(self, inscripcion_id: int, admin_id: int, session: Session):
        """
        Admin envía notificación de calificación disponible.
        Marca notificacion_calificacion_enviada = True.
        """
        from v2.models.inscripcion_materia import InscripcionMateria
        from v2.models.instancia_cursado import InstanciaCursado
        from v2.models.materia import Materia
        from v2.models.usuario import Usuario

        inscripcion = session.get(InscripcionMateria, inscripcion_id)
        if not inscripcion:
            raise ValueError(f"Inscripción {inscripcion_id} no encontrada")

        usuario = session.get(Usuario, inscripcion.usuario_id)
        instancia = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
        materia = session.get(Materia, instancia.materia_id) if instancia else None

        if not usuario or not materia:
            raise ValueError("No se pudo obtener datos del estudiante o materia")

        # Determinar si es exoneración
        es_exoneracion = inscripcion.estado == EstadoInscripcionMateria.EXONERADO
        template_key = "exoneracion" if es_exoneracion else "calificacion_disponible"
        tipo = TipoNotificacion.EXONERACION if es_exoneracion else TipoNotificacion.CALIFICACION_DISPONIBLE

        nota_str = str(inscripcion.nota_curso or inscripcion.nota_final_directa or "N/A")
        estado_str = _ESTADO_LABELS.get(inscripcion.estado, inscripcion.estado.value)

        email = self._get_email_destinatario(usuario)

        if es_exoneracion:
            asunto = f"¡Exoneración lograda! {materia.nombre}"
            html = self._renderizar(template_key, {
                "nombre": usuario.nombre,
                "materia": materia.nombre,
                "nota": nota_str,
                "creditos": inscripcion.creditos_obtenidos,
            })
        else:
            asunto = f"Calificación disponible: {materia.nombre}"
            html = self._renderizar(template_key, {
                "nombre": usuario.nombre,
                "materia": materia.nombre,
                "nota": nota_str,
                "estado": estado_str,
            })

        resultado = self._enviar_y_loguear(
            tipo=tipo,
            usuario_id=usuario.id,
            email=email,
            asunto=asunto,
            html=html,
            session=session,
            referencia_id=inscripcion.id,
            referencia_tipo="inscripcion_materia",
            enviado_por_id=admin_id,
        )

        # Marcar como notificada
        if resultado["ok"]:
            inscripcion.notificacion_calificacion_enviada = True
            session.add(inscripcion)
            session.flush()

        return resultado

    # ── Manuales ─────────────────────────────────────────────────────────────

    def enviar_individual(
        self, usuario_id: int, asunto: str, mensaje_html: str, admin_id: int, session: Session
    ):
        """Admin envía email individual a un estudiante."""
        from v2.models.usuario import Usuario
        from v2.templates.email_templates import BASE_TEMPLATE

        usuario = session.get(Usuario, usuario_id)
        if not usuario:
            raise ValueError(f"Usuario {usuario_id} no encontrado")

        email = self._get_email_destinatario(usuario)
        html = BASE_TEMPLATE.format(contenido=mensaje_html)

        return self._enviar_y_loguear(
            tipo=TipoNotificacion.MANUAL_INDIVIDUAL,
            usuario_id=usuario.id,
            email=email,
            asunto=asunto,
            html=html,
            session=session,
            enviado_por_id=admin_id,
        )

    def enviar_masivo(
        self, filtro: dict, asunto: str, mensaje_html: str, admin_id: int, session: Session
    ) -> dict:
        """
        Admin envía email masivo a un grupo de estudiantes.

        filtro: {programa_id?, instancia_cursado_id?}
        Al menos uno debe estar presente.
        """
        from v2.models.inscripcion_materia import InscripcionMateria
        from v2.models.inscripcion_programa import InscripcionPrograma
        from v2.models.alumno import Alumno
        from v2.models.usuario import Usuario
        from v2.templates.email_templates import BASE_TEMPLATE

        usuarios = set()

        # Filtrar por instancia_cursado (estudiantes inscritos en una materia específica)
        instancia_cursado_id = filtro.get("instancia_cursado_id")
        if instancia_cursado_id:
            stmt = (
                select(InscripcionMateria)
                .where(InscripcionMateria.instancia_cursado_id == instancia_cursado_id)
                .where(InscripcionMateria.estado == EstadoInscripcionMateria.CURSANDO)
            )
            for insc in session.exec(stmt).all():
                usuario = session.get(Usuario, insc.usuario_id)
                if usuario and usuario.activo:
                    usuarios.add(usuario)

        # Filtrar por programa (todos los alumnos activos)
        programa_id = filtro.get("programa_id")
        if programa_id and not instancia_cursado_id:
            stmt = (
                select(InscripcionPrograma)
                .where(InscripcionPrograma.programa_id == programa_id)
                .where(InscripcionPrograma.estado == EstadoInscripcionPrograma.ACTIVA)
            )
            for insc_prog in session.exec(stmt).all():
                alumno = session.get(Alumno, insc_prog.alumno_id)
                if not alumno:
                    continue
                usuario = session.get(Usuario, alumno.usuario_id)
                if usuario and usuario.activo:
                    usuarios.add(usuario)

        if not usuarios:
            return {"enviados": 0, "errores": [], "total_destinatarios": 0}

        html = BASE_TEMPLATE.format(contenido=mensaje_html)
        enviados = 0
        errores = []

        for usuario in usuarios:
            email = self._get_email_destinatario(usuario)
            resultado = self._enviar_y_loguear(
                tipo=TipoNotificacion.MANUAL_MASIVO,
                usuario_id=usuario.id,
                email=email,
                asunto=asunto,
                html=html,
                session=session,
                enviado_por_id=admin_id,
            )
            if resultado["ok"]:
                enviados += 1
            else:
                errores.append({"email": email, "error": resultado.get("error", "")})

        return {"enviados": enviados, "errores": errores, "total_destinatarios": len(usuarios)}

    # ── Consultas ────────────────────────────────────────────────────────────

    def get_pendientes_calificacion(self, session: Session) -> list:
        """
        Retorna inscripciones con estado final que aún no fueron notificadas.
        Estos son los "pendientes" que admin ve en el dashboard.
        """
        from v2.models.inscripcion_materia import InscripcionMateria
        from v2.models.instancia_cursado import InstanciaCursado
        from v2.models.materia import Materia
        from v2.models.usuario import Usuario

        estados_finales = [
            EstadoInscripcionMateria.EXONERADO,
            EstadoInscripcionMateria.A_EXAMEN,
            EstadoInscripcionMateria.APROBADO,
            EstadoInscripcionMateria.REPROBADO,
        ]

        stmt = (
            select(InscripcionMateria)
            .where(col(InscripcionMateria.estado).in_(estados_finales))
            .where(InscripcionMateria.notificacion_calificacion_enviada == False)
        )
        inscripciones = session.exec(stmt).all()

        resultado = []
        for insc in inscripciones:
            usuario = session.get(Usuario, insc.usuario_id)
            instancia = session.get(InstanciaCursado, insc.instancia_cursado_id)
            materia = session.get(Materia, instancia.materia_id) if instancia else None

            resultado.append({
                "inscripcion_id": insc.id,
                "usuario_id": insc.usuario_id,
                "nombre_estudiante": f"{usuario.nombre} {usuario.apellido}" if usuario else "N/A",
                "email": self._get_email_destinatario(usuario) if usuario else "N/A",
                "materia": materia.nombre if materia else "N/A",
                "nota_curso": float(insc.nota_curso) if insc.nota_curso else None,
                "nota_final_directa": float(insc.nota_final_directa) if insc.nota_final_directa else None,
                "estado": insc.estado.value,
                "estado_label": _ESTADO_LABELS.get(insc.estado, insc.estado.value),
                "fecha_cierre": insc.fecha_cierre.isoformat() if insc.fecha_cierre else None,
            })

        return resultado

    def get_historial(
        self,
        session: Session,
        page: int = 1,
        per_page: int = 50,
        tipo: Optional[TipoNotificacion] = None,
        usuario_id: Optional[int] = None,
        estado: Optional[EstadoNotificacion] = None,
    ) -> dict:
        """Historial paginado de notificaciones enviadas."""
        from v2.models.notificacion import NotificacionLogRead

        stmt = select(NotificacionLog).order_by(col(NotificacionLog.fecha_envio).desc())

        if tipo:
            stmt = stmt.where(NotificacionLog.tipo == tipo)
        if usuario_id:
            stmt = stmt.where(NotificacionLog.usuario_id == usuario_id)
        if estado:
            stmt = stmt.where(NotificacionLog.estado == estado)

        # Contar total
        from sqlmodel import func
        count_stmt = select(func.count()).select_from(NotificacionLog)
        if tipo:
            count_stmt = count_stmt.where(NotificacionLog.tipo == tipo)
        if usuario_id:
            count_stmt = count_stmt.where(NotificacionLog.usuario_id == usuario_id)
        if estado:
            count_stmt = count_stmt.where(NotificacionLog.estado == estado)
        total = session.exec(count_stmt).one()

        # Paginar
        offset = (page - 1) * per_page
        stmt = stmt.offset(offset).limit(per_page)
        logs = session.exec(stmt).all()

        return {
            "items": [NotificacionLogRead.model_validate(log) for log in logs],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if total > 0 else 0,
        }

    def get_por_rastreo(self, id_rastreo: str, session: Session) -> Optional[NotificacionLog]:
        """Busca una notificación puntual por su número de rastreo (UUID)."""
        from v2.models.notificacion import NotificacionLogRead

        stmt = select(NotificacionLog).where(NotificacionLog.id_rastreo == id_rastreo)
        log = session.exec(stmt).first()
        return NotificacionLogRead.model_validate(log) if log else None

    def get_estado_operacion(
        self, referencia_tipo: str, referencia_id: int, session: Session
    ) -> dict:
        """
        Reconciliación: dado el id de una operación de negocio (inscripcion_materia,
        inscripcion_examen, etc.), retorna si la operación existe y el estado de
        todas las notificaciones asociadas a ella.
        """
        from v2.models.notificacion import NotificacionLogRead

        stmt = (
            select(NotificacionLog)
            .where(NotificacionLog.referencia_tipo == referencia_tipo)
            .where(NotificacionLog.referencia_id == referencia_id)
            .order_by(col(NotificacionLog.fecha_envio).desc())
        )
        logs = session.exec(stmt).all()

        notificaciones = [NotificacionLogRead.model_validate(log) for log in logs]
        tiene_error_sin_resolver = any(
            n.estado == EstadoNotificacion.ERROR for n in notificaciones
        ) and not any(
            n.estado == EstadoNotificacion.ENVIADA for n in notificaciones
        )

        return {
            "referencia_tipo": referencia_tipo,
            "referencia_id": referencia_id,
            "operacion_encontrada": self._operacion_existe(referencia_tipo, referencia_id, session),
            "notificaciones": notificaciones,
            "tiene_notificacion_exitosa": any(
                n.estado == EstadoNotificacion.ENVIADA for n in notificaciones
            ),
            "tiene_error_sin_resolver": tiene_error_sin_resolver,
        }

    def _operacion_existe(self, referencia_tipo: str, referencia_id: int, session: Session) -> bool:
        """Verifica si la entidad de negocio referenciada todavía existe."""
        modelos = {
            "inscripcion_materia": "v2.models.inscripcion_materia.InscripcionMateria",
            "inscripcion_examen": "v2.models.inscripcion_examen.InscripcionExamen",
            "inscripcion_programa": "v2.models.inscripcion_programa.InscripcionPrograma",
            "instancia_examen": "v2.models.instancia_examen.InstanciaExamen",
            "periodo_inscripcion_materia": "v2.models.periodo_inscripcion_materia.PeriodoInscripcionMateria",
        }
        ruta = modelos.get(referencia_tipo)
        if not ruta:
            return False
        modulo, clase = ruta.rsplit(".", 1)
        import importlib
        Modelo = getattr(importlib.import_module(modulo), clase)
        return session.get(Modelo, referencia_id) is not None
