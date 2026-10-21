"""
Cierre de la materia al aprobar un examen.

Con la materia aprobada, cualquier otra inscripcion a examen pendiente deja de
tener sentido: el alumno ya no tiene que rendir nada. Si quedaran en INSCRIPTO
apuntarian a una materia cerrada, saldrian en las listas del docente y contarian
como rendicion al calificarlas.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from sqlmodel import select

from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.politica_examen import PoliticaExamen
from v2.models.enums import (
    EstadoInscripcionMateria, EstadoInstanciaCursado, EstadoInscripcionExamen,
)
from v2.services.inscripcion_examen_service import InscripcionExamenService


def ahora_naive():
    tz = ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo"))
    return datetime.now(tz).replace(tzinfo=None)


@pytest.fixture(name="politica_examen")
def fixture_politica_examen(session):
    pol = PoliticaExamen(
        nombre="Examen base 100", nota_maxima=Decimal("100"),
        umbral_aprobacion=Decimal("70"), max_oportunidades=5,
    )
    session.add(pol)
    session.commit()
    session.refresh(pol)
    return pol


@pytest.fixture(name="escenario")
def fixture_escenario(session, alumno, materias_con_previaturas, politica_examen):
    """Alumno con la materia en A_EXAMEN y dos instancias de examen abiertas."""
    m1 = materias_con_previaturas["prog1"]
    m1.politica_examen_id = politica_examen.id
    session.add(m1)
    session.commit()

    ic = InstanciaCursado(
        materia_id=m1.id, anio_lectivo=2026,
        estado=EstadoInstanciaCursado.FINALIZADA,
    )
    session.add(ic)
    session.commit()
    session.refresh(ic)

    insc = InscripcionMateria(
        alumno_id=alumno.id, instancia_cursado_id=ic.id,
        estado=EstadoInscripcionMateria.A_EXAMEN,
    )
    session.add(insc)
    session.commit()
    session.refresh(insc)

    base = ahora_naive()
    instancias = []
    for i, nombre in enumerate(("Febrero", "Marzo")):
        inst = InstanciaExamen(
            materia_id=m1.id, nombre=nombre,
            fecha_inicio_inscripcion=base - timedelta(days=5),
            fecha_fin_inscripcion=base + timedelta(days=5),
            fecha_examen=base + timedelta(days=10 + i * 10),
        )
        session.add(inst)
        instancias.append(inst)
    session.commit()
    for inst in instancias:
        session.refresh(inst)

    return {"inscripcion": insc, "instancias": instancias, "politica": politica_examen}


def inscribir_a_examen(session, insc, instancia, politica):
    ie = InscripcionExamen(
        inscripcion_materia_id=insc.id,
        instancia_examen_id=instancia.id,
        estado=EstadoInscripcionExamen.INSCRIPTO,
        snapshot_politica_examen={
            "nota_maxima": float(politica.nota_maxima),
            "umbral_aprobacion": float(politica.umbral_aprobacion),
            "max_oportunidades": politica.max_oportunidades,
        },
    )
    session.add(ie)
    session.commit()
    session.refresh(ie)
    return ie


class TestAprobarPorExamen:

    def test_da_de_baja_las_otras_inscripciones_pendientes(self, session, escenario):
        insc = escenario["inscripcion"]
        feb, marzo = escenario["instancias"]

        ie_feb = inscribir_a_examen(session, insc, feb, escenario["politica"])
        ie_marzo = inscribir_a_examen(session, insc, marzo, escenario["politica"])

        InscripcionExamenService().calificar_examen(ie_feb.id, Decimal("80"), session)

        session.refresh(ie_feb)
        session.refresh(ie_marzo)
        session.refresh(insc)

        assert insc.estado == EstadoInscripcionMateria.APROBADO
        assert ie_feb.estado == EstadoInscripcionExamen.APROBADO
        assert ie_marzo.estado == EstadoInscripcionExamen.BAJA
        assert ie_marzo.fecha_baja is not None

    def test_el_examen_aprobado_no_se_da_de_baja_a_si_mismo(self, session, escenario):
        """El examen que se esta calificando ya quedo APROBADO en la sesion."""
        insc = escenario["inscripcion"]
        feb = escenario["instancias"][0]
        ie = inscribir_a_examen(session, insc, feb, escenario["politica"])

        InscripcionExamenService().calificar_examen(ie.id, Decimal("90"), session)

        session.refresh(ie)
        assert ie.estado == EstadoInscripcionExamen.APROBADO
        assert ie.fecha_baja is None
        assert ie.nota_examen == Decimal("90")

    def test_las_bajas_no_cuentan_como_rendicion(self, session, escenario):
        """
        Las rendiciones cuentan APROBADO/REPROBADO/AUSENTE. Al dar de baja las
        pendientes no se le consume una oportunidad al alumno.
        """
        insc = escenario["inscripcion"]
        feb, marzo = escenario["instancias"]
        ie_feb = inscribir_a_examen(session, insc, feb, escenario["politica"])
        inscribir_a_examen(session, insc, marzo, escenario["politica"])

        service = InscripcionExamenService()
        service.calificar_examen(ie_feb.id, Decimal("80"), session)

        # Solo el aprobado cuenta
        assert service._contar_rendiciones_previas(insc.id, session) == 1

    def test_reprobar_no_da_de_baja_las_otras(self, session, escenario):
        """Si reprueba, las otras fechas siguen vigentes para volver a rendir."""
        insc = escenario["inscripcion"]
        feb, marzo = escenario["instancias"]
        ie_feb = inscribir_a_examen(session, insc, feb, escenario["politica"])
        ie_marzo = inscribir_a_examen(session, insc, marzo, escenario["politica"])

        InscripcionExamenService().calificar_examen(ie_feb.id, Decimal("40"), session)

        session.refresh(ie_feb)
        session.refresh(ie_marzo)
        session.refresh(insc)

        assert ie_feb.estado == EstadoInscripcionExamen.REPROBADO
        assert ie_marzo.estado == EstadoInscripcionExamen.INSCRIPTO
        assert insc.estado == EstadoInscripcionMateria.A_EXAMEN

    def test_no_toca_inscripciones_de_otra_materia(
        self, session, alumno, escenario, materias_con_previaturas, politica_examen
    ):
        """La baja alcanza solo a los examenes de esa inscripcion a materia."""
        insc = escenario["inscripcion"]
        feb = escenario["instancias"][0]
        ie_feb = inscribir_a_examen(session, insc, feb, politica_examen)

        # Otra materia del alumno, tambien a examen y con inscripcion pendiente
        m2 = materias_con_previaturas["prog2"]
        ic2 = InstanciaCursado(
            materia_id=m2.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic2)
        session.commit()
        session.refresh(ic2)

        insc2 = InscripcionMateria(
            alumno_id=alumno.id, instancia_cursado_id=ic2.id,
            estado=EstadoInscripcionMateria.A_EXAMEN,
        )
        session.add(insc2)
        session.commit()
        session.refresh(insc2)

        base = ahora_naive()
        inst_m2 = InstanciaExamen(
            materia_id=m2.id, nombre="Febrero P2",
            fecha_inicio_inscripcion=base - timedelta(days=5),
            fecha_fin_inscripcion=base + timedelta(days=5),
            fecha_examen=base + timedelta(days=12),
        )
        session.add(inst_m2)
        session.commit()
        session.refresh(inst_m2)

        ie_m2 = inscribir_a_examen(session, insc2, inst_m2, politica_examen)

        InscripcionExamenService().calificar_examen(ie_feb.id, Decimal("85"), session)

        session.refresh(ie_m2)
        session.refresh(insc2)
        assert ie_m2.estado == EstadoInscripcionExamen.INSCRIPTO
        assert insc2.estado == EstadoInscripcionMateria.A_EXAMEN
