"""
Plazo para darse de baja de un examen: 24 horas antes (regla de bedelia,
23/09/2026; antes el default era 72).

Quien no se da de baja a tiempo y no se presenta queda AUSENTE (el NSP de
bedelia): cuenta como actividad rendida, con 0 en el promedio de la
escolaridad, y gasta una oportunidad de examen.
"""
import os
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from v2.models.enums import (
    EstadoInscripcionExamen as EE, EstadoInscripcionMateria as EM, EstadoInstanciaCursado,
)
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.services.inscripcion_examen_service import InscripcionExamenService
from v2.services import promedio_escolaridad as pe

SERVICIO = InscripcionExamenService()


def ahora_naive():
    return datetime.now(ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo"))).replace(tzinfo=None)


@pytest.fixture(name="inscripto_a")
def fixture_inscripto_a(session, alumno, materias_con_previaturas):
    """Devuelve una funcion: inscripto a un examen que es dentro de N horas."""
    p1 = materias_con_previaturas["prog1"]

    def armar(horas_hasta_el_examen: float) -> InscripcionExamen:
        ic = InstanciaCursado(materia_id=p1.id, anio_lectivo=2026, estado=EstadoInstanciaCursado.FINALIZADA)
        session.add(ic)
        session.flush()
        insc = InscripcionMateria(alumno_id=alumno.id, instancia_cursado_id=ic.id, estado=EM.A_EXAMEN)
        session.add(insc)
        session.flush()
        fecha = ahora_naive() + timedelta(hours=horas_hasta_el_examen)
        inst = InstanciaExamen(materia_id=p1.id, nombre="Examen", fecha_inicio_inscripcion=fecha - timedelta(days=10),
                               fecha_fin_inscripcion=fecha - timedelta(days=2), fecha_examen=fecha, habilitado=True)
        session.add(inst)
        session.flush()
        ie = InscripcionExamen(inscripcion_materia_id=insc.id, instancia_examen_id=inst.id, estado=EE.INSCRIPTO)
        session.add(ie)
        session.commit()
        session.refresh(ie)
        return ie
    return armar


class TestPlazoDeBaja:
    def test_se_puede_hasta_24_horas_antes(self, session, inscripto_a, monkeypatch):
        monkeypatch.delenv("PLAZO_BAJA_EXAMEN_HORAS", raising=False)
        ie = inscripto_a(25)
        SERVICIO.desinscribir_examen(ie.id, session)
        session.refresh(ie)
        assert ie.estado == EE.BAJA and ie.fecha_baja is not None

    def test_con_menos_de_24_horas_no(self, session, inscripto_a, monkeypatch):
        monkeypatch.delenv("PLAZO_BAJA_EXAMEN_HORAS", raising=False)
        ie = inscripto_a(23)
        with pytest.raises(ValueError, match="24 horas"):
            SERVICIO.desinscribir_examen(ie.id, session)
        session.refresh(ie)
        assert ie.estado == EE.INSCRIPTO

    def test_ya_no_son_72(self, session, inscripto_a, monkeypatch):
        """Con el default viejo, a 48 horas se rechazaba."""
        monkeypatch.delenv("PLAZO_BAJA_EXAMEN_HORAS", raising=False)
        ie = inscripto_a(48)
        SERVICIO.desinscribir_examen(ie.id, session)
        session.refresh(ie)
        assert ie.estado == EE.BAJA

    def test_se_puede_configurar(self, session, inscripto_a, monkeypatch):
        monkeypatch.setenv("PLAZO_BAJA_EXAMEN_HORAS", "72")
        ie = inscripto_a(48)
        with pytest.raises(ValueError, match="72 horas"):
            SERVICIO.desinscribir_examen(ie.id, session)


class TestNSP:
    def test_el_ausente_cuenta_cero_y_gasta_una_oportunidad(self, session, inscripto_a):
        """No se dio de baja y no se presento: NSP."""
        ie = inscripto_a(-2)          # el examen fue hace dos horas
        SERVICIO.marcar_ausente(ie.id, session)
        session.refresh(ie)
        assert ie.estado == EE.AUSENTE

        act = pe.actividad_de_examen(ie, "PROGRAMACION 1", None)
        assert (act.resultado, act.nota_promedio, act.peso) == ("NSP", 0.0, 1)
        assert SERVICIO._contar_rendiciones_previas(ie.inscripcion_materia_id, session) == 1

    def test_la_baja_a_tiempo_no_es_actividad(self, session, inscripto_a):
        ie = inscripto_a(30)
        SERVICIO.desinscribir_examen(ie.id, session)
        session.refresh(ie)
        assert pe.actividad_de_examen(ie, "PROGRAMACION 1", None) is None
        assert SERVICIO._contar_rendiciones_previas(ie.inscripcion_materia_id, session) == 0
