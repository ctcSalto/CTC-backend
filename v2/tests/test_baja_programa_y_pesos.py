"""
Baja de un alumno de un programa, y validacion de la suma de pesos.

La baja no existia: InscripcionPrograma tenia fecha_baja y motivo_baja desde
Fase 1 pero ningun servicio los escribia, y por eso notificar_baja_procesada
habia quedado implementada sin llamador.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch
from sqlmodel import select

from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.materia_instancia_evaluacion import (
    MateriaInstanciaEvaluacion, InstanciaEvaluacionCreate, InstanciaEvaluacionUpdate,
)
from v2.models.enums import (
    EstadoInscripcionPrograma, EstadoInscripcionMateria, EstadoInstanciaCursado,
)
from v2.services.inscripcion_programa_service import InscripcionProgramaService
from v2.services.instancia_evaluacion_service import InstanciaEvaluacionService


@pytest.fixture(name="sin_mails")
def fixture_sin_mails():
    with patch(
        "v2.services.email_service.EmailService.send_single",
        return_value={"ok": True, "error": None},
    ) as mock:
        yield mock


@pytest.fixture(name="inscripto")
def fixture_inscripto(session, alumno, programa):
    insc = InscripcionPrograma(
        alumno_id=alumno.id, programa_id=programa.id,
        estado=EstadoInscripcionPrograma.ACTIVA, anio_ingreso=2026,
    )
    session.add(insc)
    session.commit()
    session.refresh(insc)
    return insc


def cursar(session, alumno, materia, estado=EstadoInscripcionMateria.CURSANDO):
    ic = InstanciaCursado(
        materia_id=materia.id, anio_lectivo=2026,
        estado=EstadoInstanciaCursado.EN_CURSO,
    )
    session.add(ic)
    session.commit()
    session.refresh(ic)

    insc = InscripcionMateria(
        alumno_id=alumno.id, instancia_cursado_id=ic.id, estado=estado,
    )
    session.add(insc)
    session.commit()
    session.refresh(insc)
    return insc


class TestBajaDePrograma:

    def test_registra_fecha_y_motivo(self, session, inscripto, sin_mails):
        resultado = InscripcionProgramaService().dar_de_baja(
            inscripto.id, "Se muda de ciudad", session
        )

        assert resultado.estado == EstadoInscripcionPrograma.BAJA
        assert resultado.fecha_baja is not None
        assert resultado.motivo_baja == "Se muda de ciudad"

    def test_cierra_las_materias_en_curso(
        self, session, alumno, inscripto, materias_con_previaturas, sin_mails
    ):
        insc_materia = cursar(session, alumno, materias_con_previaturas["prog1"])

        resultado = InscripcionProgramaService().dar_de_baja(
            inscripto.id, "Abandona la carrera", session
        )

        session.refresh(insc_materia)
        assert insc_materia.estado == EstadoInscripcionMateria.ABANDONO
        assert insc_materia.fecha_baja is not None
        assert "Baja del programa" in insc_materia.motivo_cierre
        assert resultado.materias_cerradas == 1

    def test_no_toca_materias_ya_cerradas(
        self, session, alumno, inscripto, materias_con_previaturas, sin_mails
    ):
        """Una materia aprobada queda como estaba: la baja no borra el historial."""
        aprobada = cursar(session, alumno, materias_con_previaturas["prog1"],
                          estado=EstadoInscripcionMateria.APROBADO)

        InscripcionProgramaService().dar_de_baja(inscripto.id, "Motivo", session)

        session.refresh(aprobada)
        assert aprobada.estado == EstadoInscripcionMateria.APROBADO
        assert aprobada.fecha_baja is None

    def test_cerrar_materias_desactivable(
        self, session, alumno, inscripto, materias_con_previaturas, sin_mails
    ):
        insc_materia = cursar(session, alumno, materias_con_previaturas["prog1"])

        resultado = InscripcionProgramaService().dar_de_baja(
            inscripto.id, "Pase administrativo", session, cerrar_materias=False
        )

        session.refresh(insc_materia)
        assert insc_materia.estado == EstadoInscripcionMateria.CURSANDO
        assert resultado.materias_cerradas == 0

    def test_motivo_obligatorio(self, session, inscripto, sin_mails):
        with pytest.raises(ValueError, match="motivo de la baja es obligatorio"):
            InscripcionProgramaService().dar_de_baja(inscripto.id, "   ", session)

    def test_no_se_puede_dar_de_baja_dos_veces(self, session, inscripto, sin_mails):
        service = InscripcionProgramaService()
        service.dar_de_baja(inscripto.id, "Primera", session)

        with pytest.raises(ValueError, match="ya está dada de baja"):
            service.dar_de_baja(inscripto.id, "Segunda", session)

    def test_no_se_puede_dar_de_baja_a_un_egresado(
        self, session, inscripto, sin_mails
    ):
        inscripto.estado = EstadoInscripcionPrograma.COMPLETADA
        session.add(inscripto)
        session.commit()

        with pytest.raises(ValueError, match="egresó"):
            InscripcionProgramaService().dar_de_baja(inscripto.id, "Motivo", session)

    def test_envia_la_notificacion(self, session, inscripto, sin_mails):
        """notificar_baja_procesada estaba implementada y nadie la llamaba."""
        InscripcionProgramaService().dar_de_baja(inscripto.id, "Motivo", session)

        assert sin_mails.call_count == 1
        asunto = sin_mails.call_args[0][1]
        assert "Baja procesada" in asunto

    def test_la_notificacion_caida_no_tumba_la_baja(self, session, inscripto):
        """La baja ya quedo registrada: el mail no puede revertirla."""
        with patch(
            "v2.services.email_service.EmailService.send_single",
            side_effect=RuntimeError("webhook caido"),
        ):
            resultado = InscripcionProgramaService().dar_de_baja(
                inscripto.id, "Motivo", session
            )

        assert resultado.estado == EstadoInscripcionPrograma.BAJA


class TestSumaDePesos:

    def _cursada(self, session, materia):
        ic = InstanciaCursado(
            materia_id=materia.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.EN_CURSO,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)
        return ic

    def test_los_pesos_no_pueden_pasarse_de_la_nota_maxima(
        self, session, materias_con_previaturas
    ):
        """La politica base100 tiene nota_maxima=100."""
        ic = self._cursada(session, materias_con_previaturas["prog1"])
        service = InstanciaEvaluacionService()

        service.create(InstanciaEvaluacionCreate(
            instancia_cursado_id=ic.id, nombre="Primer Parcial",
            peso_maximo=Decimal("60"), orden=1,
        ), session)

        with pytest.raises(ValueError, match="sumarian"):
            service.create(InstanciaEvaluacionCreate(
                instancia_cursado_id=ic.id, nombre="Segundo Parcial",
                peso_maximo=Decimal("50"), orden=2,
            ), session)

    def test_el_plan_completo_de_cien_entra(self, session, materias_con_previaturas):
        """Primer parcial, segundo parcial, obligatorio y nota de clase = 100."""
        ic = self._cursada(session, materias_con_previaturas["prog1"])
        service = InstanciaEvaluacionService()

        plan = [
            ("Primer Parcial", Decimal("25"), False),
            ("Segundo Parcial", Decimal("25"), False),
            ("Obligatorio", Decimal("30"), True),
            ("Nota de clase", Decimal("20"), False),
        ]
        for orden, (nombre, peso, grupal) in enumerate(plan, start=1):
            service.create(InstanciaEvaluacionCreate(
                instancia_cursado_id=ic.id, nombre=nombre,
                peso_maximo=peso, orden=orden, es_grupal=grupal,
            ), session)

        total = sum(
            ev.peso_maximo for ev in session.exec(
                select(MateriaInstanciaEvaluacion).where(
                    MateriaInstanciaEvaluacion.instancia_cursado_id == ic.id
                )
            ).all()
        )
        assert total == Decimal("100")

    def test_update_no_puede_pasarse(self, session, materias_con_previaturas):
        ic = self._cursada(session, materias_con_previaturas["prog1"])
        service = InstanciaEvaluacionService()

        service.create(InstanciaEvaluacionCreate(
            instancia_cursado_id=ic.id, nombre="Primer Parcial",
            peso_maximo=Decimal("50"), orden=1,
        ), session)
        segunda = service.create(InstanciaEvaluacionCreate(
            instancia_cursado_id=ic.id, nombre="Segundo Parcial",
            peso_maximo=Decimal("50"), orden=2,
        ), session)

        with pytest.raises(ValueError, match="sumarian"):
            service.update(
                segunda.id,
                InstanciaEvaluacionUpdate(peso_maximo=Decimal("70")),
                session,
            )

    def test_update_que_baja_el_peso_pasa(self, session, materias_con_previaturas):
        """Al editar, el peso viejo de esa misma evaluacion no debe contarse dos veces."""
        ic = self._cursada(session, materias_con_previaturas["prog1"])
        service = InstanciaEvaluacionService()

        service.create(InstanciaEvaluacionCreate(
            instancia_cursado_id=ic.id, nombre="Primer Parcial",
            peso_maximo=Decimal("50"), orden=1,
        ), session)
        segunda = service.create(InstanciaEvaluacionCreate(
            instancia_cursado_id=ic.id, nombre="Segundo Parcial",
            peso_maximo=Decimal("50"), orden=2,
        ), session)

        actualizada = service.update(
            segunda.id,
            InstanciaEvaluacionUpdate(peso_maximo=Decimal("40")),
            session,
        )
        assert actualizada.peso_maximo == Decimal("40")
