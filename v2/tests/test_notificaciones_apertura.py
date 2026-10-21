"""
Jobs de apertura de inscripcion a materias y a examenes.

Estos avisos existian implementados pero no los llamaba nadie: ningun alumno los
recibia. Los jobs buscan lo que abre HOY, no lo que esta abierto, porque un
periodo abierto dura varios dias y avisar sobre "lo abierto" mandaria el mismo
mail cada jornada.
"""
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch
import os

from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.models.periodo_inscripcion_materia import PeriodoInscripcionMateria
from v2.models.notificacion import NotificacionLog
from v2.models.enums import (
    EstadoInscripcionPrograma, EstadoInscripcionMateria,
    EstadoInstanciaCursado, TipoNotificacion,
)
from v2.services.notification_service import NotificationService
from sqlmodel import select


def tz():
    return ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo"))


@pytest.fixture(name="envio_ok")
def fixture_envio_ok():
    """Intercepta el envio real de mails y lo da por exitoso."""
    with patch(
        "v2.services.email_service.EmailService.send_single",
        return_value={"ok": True, "error": None},
    ) as mock:
        yield mock


@pytest.fixture(name="alumno_en_programa")
def fixture_alumno_en_programa(session, alumno, programa):
    insc = InscripcionPrograma(
        alumno_id=alumno.id,
        programa_id=programa.id,
        estado=EstadoInscripcionPrograma.ACTIVA,
        anio_ingreso=2026,
    )
    session.add(insc)
    session.commit()
    session.refresh(insc)
    return insc


def crear_periodo(session, programa, dias_offset=0):
    """Periodo cuyo fecha_inicio cae `dias_offset` dias respecto de hoy."""
    ahora = datetime.now(tz())
    inicio = (ahora + timedelta(days=dias_offset)).replace(hour=9, minute=0)
    periodo = PeriodoInscripcionMateria(
        programa_id=programa.id,
        anio_lectivo=2026,
        fecha_inicio=inicio,
        fecha_fin=inicio + timedelta(days=20),
        habilitado=True,
    )
    session.add(periodo)
    session.commit()
    session.refresh(periodo)
    return periodo


def logs_de(session, tipo):
    return session.exec(
        select(NotificacionLog).where(NotificacionLog.tipo == tipo)
    ).all()


class TestAperturaInscripcion:

    def test_avisa_cuando_el_periodo_abre_hoy(
        self, session, alumno_en_programa, programa, envio_ok
    ):
        crear_periodo(session, programa, dias_offset=0)

        resumen = NotificationService().notificar_aperturas_inscripcion_del_dia(session)

        assert resumen["periodos"] == 1
        assert envio_ok.call_count == 1
        assert len(logs_de(session, TipoNotificacion.APERTURA_INSCRIPCION)) == 1

    def test_no_avisa_de_un_periodo_que_abrio_antes(
        self, session, alumno_en_programa, programa, envio_ok
    ):
        """
        El caso que justifica mirar la apertura y no lo abierto: un periodo que
        empezo hace cinco dias sigue abierto, pero su aviso ya salio.
        """
        crear_periodo(session, programa, dias_offset=-5)

        resumen = NotificationService().notificar_aperturas_inscripcion_del_dia(session)

        assert resumen["periodos"] == 0
        assert envio_ok.call_count == 0

    def test_no_avisa_de_un_periodo_futuro(
        self, session, alumno_en_programa, programa, envio_ok
    ):
        crear_periodo(session, programa, dias_offset=3)

        resumen = NotificationService().notificar_aperturas_inscripcion_del_dia(session)

        assert resumen["periodos"] == 0
        assert envio_ok.call_count == 0

    def test_periodo_deshabilitado_no_avisa(
        self, session, alumno_en_programa, programa, envio_ok
    ):
        periodo = crear_periodo(session, programa, dias_offset=0)
        periodo.habilitado = False
        session.add(periodo)
        session.commit()

        resumen = NotificationService().notificar_aperturas_inscripcion_del_dia(session)

        assert resumen["periodos"] == 0
        assert envio_ok.call_count == 0

    def test_correr_el_job_dos_veces_no_duplica(
        self, session, alumno_en_programa, programa, envio_ok
    ):
        """Si el scheduler reintenta, el alumno no recibe el aviso dos veces."""
        crear_periodo(session, programa, dias_offset=0)
        service = NotificationService()

        service.notificar_aperturas_inscripcion_del_dia(session)
        service.notificar_aperturas_inscripcion_del_dia(session)

        assert envio_ok.call_count == 1
        assert len(logs_de(session, TipoNotificacion.APERTURA_INSCRIPCION)) == 1

    def test_no_avisa_a_alumno_de_otro_programa(
        self, session, otro_alumno, programa, envio_ok
    ):
        """otro_alumno no tiene inscripcion al programa."""
        crear_periodo(session, programa, dias_offset=0)

        NotificationService().notificar_aperturas_inscripcion_del_dia(session)

        assert envio_ok.call_count == 0


class TestAperturaExamen:

    def _materia_a_examen(self, session, alumno, materia):
        ic = InstanciaCursado(
            materia_id=materia.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        insc = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.A_EXAMEN,
        )
        session.add(insc)
        session.commit()
        return insc

    def _instancia_examen(self, session, materia, dias_offset=0):
        ahora = datetime.now(tz()).replace(tzinfo=None)
        inicio = (ahora + timedelta(days=dias_offset)).replace(hour=9, minute=0)
        inst = InstanciaExamen(
            materia_id=materia.id,
            nombre=f"Examen {materia.nombre}",
            fecha_inicio_inscripcion=inicio,
            fecha_fin_inscripcion=inicio + timedelta(days=10),
            fecha_examen=inicio + timedelta(days=20),
            habilitado=True,
        )
        session.add(inst)
        session.commit()
        session.refresh(inst)
        return inst

    def test_avisa_a_quien_tiene_la_materia_a_examen(
        self, session, alumno, materias_con_previaturas, envio_ok
    ):
        m1 = materias_con_previaturas["prog1"]
        self._materia_a_examen(session, alumno, m1)
        self._instancia_examen(session, m1, dias_offset=0)

        resumen = NotificationService().notificar_aperturas_examen_del_dia(session)

        assert resumen["instancias"] == 1
        assert envio_ok.call_count == 1
        assert len(logs_de(session, TipoNotificacion.APERTURA_EXAMEN)) == 1

    def test_no_avisa_a_quien_esta_cursando(
        self, session, alumno, materias_con_previaturas, envio_ok
    ):
        """Solo A_EXAMEN: quien esta cursando todavia no puede rendir."""
        m1 = materias_con_previaturas["prog1"]
        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.EN_CURSO,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)
        session.add(InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.CURSANDO,
        ))
        session.commit()

        self._instancia_examen(session, m1, dias_offset=0)

        NotificationService().notificar_aperturas_examen_del_dia(session)

        assert envio_ok.call_count == 0

    def test_no_avisa_de_una_inscripcion_que_abrio_antes(
        self, session, alumno, materias_con_previaturas, envio_ok
    ):
        m1 = materias_con_previaturas["prog1"]
        self._materia_a_examen(session, alumno, m1)
        self._instancia_examen(session, m1, dias_offset=-4)

        resumen = NotificationService().notificar_aperturas_examen_del_dia(session)

        assert resumen["instancias"] == 0
        assert envio_ok.call_count == 0

    def test_correr_el_job_dos_veces_no_duplica(
        self, session, alumno, materias_con_previaturas, envio_ok
    ):
        m1 = materias_con_previaturas["prog1"]
        self._materia_a_examen(session, alumno, m1)
        self._instancia_examen(session, m1, dias_offset=0)
        service = NotificationService()

        service.notificar_aperturas_examen_del_dia(session)
        service.notificar_aperturas_examen_del_dia(session)

        assert envio_ok.call_count == 1
