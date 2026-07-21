"""
Tests para el sistema de notificaciones (Fase 5).
- EmailService: delivery via webhook
- NotificationService: templates, log, pendientes
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("TIME_ZONE", "America/Montevideo")

from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy.pool import StaticPool

from v2.models.usuario import Usuario
from v2.models.programa import Programa
from v2.models.materia import Materia
from v2.models.politica_calificacion import PoliticaCalificacion
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.notificacion import NotificacionLog
from v2.models.enums import (
    RolUsuario, TipoPrograma, AreaPrograma, TipoNota,
    EstadoInstanciaCursado, EstadoInscripcionMateria,
    TipoNotificacion, EstadoNotificacion, CanalNotificacion,
)
from v2.services.email_service import EmailService
from v2.services.notification_service import NotificationService
from v2.templates.email_templates import TEMPLATES


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(name="engine")
def fixture_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def fixture_session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="usuario_est")
def fixture_usuario_est(session):
    user = Usuario(
        google_id="google_test_001",
        email="estudiante@ctcsalto.edu.uy",
        email_personal="juan@gmail.com",
        nombre="Juan",
        apellido="Perez",
        rol=RolUsuario.ESTUDIANTE,
        activo=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="alumno_est")
def fixture_alumno_est(session, usuario_est):
    """Perfil de alumno del usuario estudiante (las inscripciones lo referencian)."""
    from v2.models.alumno import Alumno
    alumno = Alumno(usuario_id=usuario_est.id)
    session.add(alumno)
    session.commit()
    session.refresh(alumno)
    return alumno


@pytest.fixture(name="usuario_admin")
def fixture_usuario_admin(session):
    user = Usuario(
        google_id="google_admin_001",
        email="admin@ctcsalto.edu.uy",
        nombre="Carlos",
        apellido="Lopez",
        rol=RolUsuario.ADMINISTRATIVO,
        activo=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="programa")
def fixture_programa(session):
    prog = Programa(
        nombre="Analista Programador Test",
        tipo=TipoPrograma.CARRERA,
        area=AreaPrograma.INFORMATICA,
        duracion_semestres=4,
        creditos_requeridos=200,
        activo=True,
    )
    session.add(prog)
    session.commit()
    session.refresh(prog)
    return prog


@pytest.fixture(name="materia")
def fixture_materia(session, programa):
    pol = PoliticaCalificacion(
        nombre="Base 100",
        nota_maxima=Decimal("100"),
        tipo_nota=TipoNota.NUMERICA,
        umbral_aprobacion=Decimal("60"),
        umbral_examen=Decimal("25"),
        umbral_exoneracion=Decimal("86"),
        activo=True,
    )
    session.add(pol)
    session.commit()
    session.refresh(pol)

    mat = Materia(
        programa_id=programa.id,
        nombre="Programacion 1",
        codigo="P1",
        semestre=1,
        creditos=10,
        politica_id=pol.id,
        activo=True,
    )
    session.add(mat)
    session.commit()
    session.refresh(mat)
    return mat


@pytest.fixture(name="inscripcion_exonerado")
def fixture_inscripcion_exonerado(session, alumno_est, materia):
    """Inscripcion con estado EXONERADO, sin notificar."""
    ic = InstanciaCursado(
        materia_id=materia.id,
        anio_lectivo=2026,
        estado=EstadoInstanciaCursado.EN_CURSO,
    )
    session.add(ic)
    session.commit()
    session.refresh(ic)

    insc = InscripcionMateria(
        alumno_id=alumno_est.id,
        instancia_cursado_id=ic.id,
        estado=EstadoInscripcionMateria.EXONERADO,
        nota_curso=Decimal("90"),
        creditos_obtenidos=10,
        notificacion_calificacion_enviada=False,
    )
    session.add(insc)
    session.commit()
    session.refresh(insc)
    return insc


# ── Tests EmailService ──────────────────────────────────────────────────────

class TestEmailService:

    def test_send_single_sin_webhook(self):
        """Si N8N_EMAIL_WEBHOOK_URL no está configurada, retorna error."""
        service = EmailService()
        service.webhook_url = None
        resultado = service.send_single("test@test.com", "Asunto", "<p>Hola</p>")
        assert resultado["ok"] is False
        assert "no configurada" in resultado["error"]

    @patch("v2.services.email_service.requests.post")
    def test_send_single_exitoso(self, mock_post):
        """Envío exitoso retorna ok=True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        service = EmailService()
        service.webhook_url = "https://n8n.test/webhook/email"
        resultado = service.send_single("test@test.com", "Asunto", "<p>Hola</p>")

        assert resultado["ok"] is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["to"] == "test@test.com"
        assert payload["subject"] == "Asunto"

    @patch("v2.services.email_service.requests.post")
    def test_send_single_error_webhook(self, mock_post):
        """Si el webhook retorna error, retorna ok=False."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        service = EmailService()
        service.webhook_url = "https://n8n.test/webhook/email"
        resultado = service.send_single("test@test.com", "Asunto", "<p>Hola</p>")

        assert resultado["ok"] is False
        assert "500" in resultado["error"]

    @patch("v2.services.email_service.requests.post")
    def test_send_batch(self, mock_post):
        """Envío masivo procesa todos los destinatarios."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        service = EmailService()
        service.webhook_url = "https://n8n.test/webhook/email"

        destinatarios = [
            {"email": "a@test.com", "variables": {"nombre": "Ana"}},
            {"email": "b@test.com", "variables": {"nombre": "Bruno"}},
        ]
        resultado = service.send_batch(destinatarios, "Hola", "<p>Hola {nombre}</p>")

        assert resultado["enviados"] == 2
        assert len(resultado["errores"]) == 0
        assert mock_post.call_count == 2


# ── Tests Templates ─────────────────────────────────────────────────────────

class TestTemplates:

    def test_todos_los_templates_existen(self):
        """Verifica que los 12 templates están definidos."""
        expected = [
            "inscripcion_materia", "inscripcion_examen", "recordatorio_examen",
            "apertura_inscripcion", "apertura_examen", "cierre_inscripcion",
            "calificacion_disponible", "exoneracion", "reprobado_rendiciones",
            "baja_procesada", "manual_individual", "manual_masivo",
        ]
        for key in expected:
            assert key in TEMPLATES, f"Template '{key}' no encontrado"

    def test_template_inscripcion_materia_renderiza(self):
        """Verifica que el template de inscripción renderiza correctamente."""
        html = TEMPLATES["inscripcion_materia"].format(
            nombre="Juan",
            materia="Programacion 1",
            programa="Analista Programador",
            anio_lectivo=2026,
        )
        assert "Juan" in html
        assert "Programacion 1" in html
        assert "2026" in html
        assert "Centro de Tecnolog" in html  # header CTC

    def test_template_calificacion_renderiza(self):
        """Verifica template de calificación."""
        html = TEMPLATES["calificacion_disponible"].format(
            nombre="Maria",
            materia="Base de Datos",
            nota="85",
            estado="A examen",
        )
        assert "Maria" in html
        assert "85" in html
        assert "A examen" in html


# ── Tests NotificationService ───────────────────────────────────────────────

class TestNotificationService:

    @patch("v2.services.email_service.requests.post")
    def test_notificar_inscripcion_materia(self, mock_post, session, usuario_est, alumno_est, materia, programa):
        """Notificación de inscripción crea log en BD."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        ic = InstanciaCursado(
            materia_id=materia.id,
            anio_lectivo=2026,
            estado=EstadoInstanciaCursado.EN_CURSO,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        insc = InscripcionMateria(
            alumno_id=alumno_est.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.CURSANDO,
        )
        session.add(insc)
        session.commit()
        session.refresh(insc)

        service = NotificationService()
        service.email_service.webhook_url = "https://n8n.test/webhook/email"

        service.notificar_inscripcion_materia(
            insc, usuario_est, materia, programa.nombre, 2026, session
        )
        session.commit()

        # Verificar log
        logs = session.exec(select(NotificacionLog)).all()
        assert len(logs) == 1
        assert logs[0].tipo == TipoNotificacion.INSCRIPCION_MATERIA
        assert logs[0].usuario_id == usuario_est.id
        assert logs[0].email_destino == "juan@gmail.com"  # email_personal
        assert logs[0].estado == EstadoNotificacion.ENVIADA
        assert logs[0].referencia_id == insc.id

    @patch("v2.services.email_service.requests.post")
    def test_notificar_calificacion_marca_enviada(
        self, mock_post, session, usuario_est, usuario_admin, inscripcion_exonerado
    ):
        """Notificación de calificación marca notificacion_calificacion_enviada=True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        service = NotificationService()
        service.email_service.webhook_url = "https://n8n.test/webhook/email"

        resultado = service.notificar_calificacion(
            inscripcion_exonerado.id, usuario_admin.id, session
        )
        session.commit()

        assert resultado["ok"] is True

        # Verificar que se marcó como enviada
        session.refresh(inscripcion_exonerado)
        assert inscripcion_exonerado.notificacion_calificacion_enviada is True

        # Verificar log con tipo exoneración
        logs = session.exec(select(NotificacionLog)).all()
        assert len(logs) == 1
        assert logs[0].tipo == TipoNotificacion.EXONERACION
        assert logs[0].enviado_por_id == usuario_admin.id

    def test_get_pendientes_calificacion(self, session, usuario_est, inscripcion_exonerado):
        """Pendientes retorna inscripciones sin notificar."""
        service = NotificationService()
        pendientes = service.get_pendientes_calificacion(session)

        assert len(pendientes) == 1
        assert pendientes[0]["inscripcion_id"] == inscripcion_exonerado.id
        assert pendientes[0]["estado"] == "exonerado"
        assert pendientes[0]["nombre_estudiante"] == "Juan Perez"

    @patch("v2.services.email_service.requests.post")
    def test_pendientes_vacios_despues_de_notificar(
        self, mock_post, session, usuario_est, usuario_admin, inscripcion_exonerado
    ):
        """Después de notificar, no debe aparecer en pendientes."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        service = NotificationService()
        service.email_service.webhook_url = "https://n8n.test/webhook/email"

        service.notificar_calificacion(inscripcion_exonerado.id, usuario_admin.id, session)
        session.commit()

        pendientes = service.get_pendientes_calificacion(session)
        assert len(pendientes) == 0

    def test_email_personal_preferido(self, usuario_est):
        """Si tiene email_personal, se usa ese en lugar del institucional."""
        service = NotificationService()
        email = service._get_email_destinatario(usuario_est)
        assert email == "juan@gmail.com"

    def test_email_institucional_fallback(self, session):
        """Si no tiene email_personal, se usa el institucional."""
        user = Usuario(
            google_id="google_sin_personal",
            email="sin.personal@ctcsalto.edu.uy",
            nombre="Ana",
            apellido="Test",
            rol=RolUsuario.ESTUDIANTE,
            activo=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        service = NotificationService()
        email = service._get_email_destinatario(user)
        assert email == "sin.personal@ctcsalto.edu.uy"

    @patch("v2.services.email_service.requests.post")
    def test_error_webhook_registra_en_log(self, mock_post, session, usuario_est, alumno_est, materia, programa):
        """Si el webhook falla, se registra el error en el log."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        ic = InstanciaCursado(
            materia_id=materia.id,
            anio_lectivo=2026,
            estado=EstadoInstanciaCursado.EN_CURSO,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        insc = InscripcionMateria(
            alumno_id=alumno_est.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.CURSANDO,
        )
        session.add(insc)
        session.commit()
        session.refresh(insc)

        service = NotificationService()
        service.email_service.webhook_url = "https://n8n.test/webhook/email"

        service.notificar_inscripcion_materia(
            insc, usuario_est, materia, programa.nombre, 2026, session
        )
        session.commit()

        logs = session.exec(select(NotificacionLog)).all()
        assert len(logs) == 1
        assert logs[0].estado == EstadoNotificacion.ERROR
        assert "500" in logs[0].error_detalle

    def test_get_historial_vacio(self, session):
        """Historial vacío retorna estructura correcta."""
        service = NotificationService()
        result = service.get_historial(session)
        assert result["total"] == 0
        assert result["items"] == []
        assert result["page"] == 1
