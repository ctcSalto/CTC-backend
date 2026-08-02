"""
Las consultas de disponibilidad no pueden crecer con el tamanio del plan.

Las pantallas de inscripcion recorren todas las materias del programa. Cuando la
consulta se hacia materia por materia, un plan de 30 materias disparaba ~180
consultas contra una base que esta en otro servidor: segundos de espera en la
pantalla donde entran todos los alumnos el mismo dia.

Estos tests corren el mismo escenario con pocas y con muchas materias y exigen
que el numero de consultas sea identico. Si alguien vuelve a meter una consulta
dentro del bucle, fallan.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from sqlalchemy import event
from sqlmodel import select

from v2.models.materia import Materia
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.periodo_inscripcion_materia import PeriodoInscripcionMateria
from v2.models.previatura import Previatura
from v2.models.politica_examen import PoliticaExamen
from v2.models.enums import (
    EstadoInstanciaCursado, EstadoInscripcionMateria, TipoPreviatura,
)
from v2.services.inscripcion_service import InscripcionMateriaService
from v2.services.inscripcion_examen_service import InscripcionExamenService


POCAS = 3
MUCHAS = 25


def tz():
    return ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo"))


class ContadorDeConsultas:
    """Cuenta las sentencias que salen hacia la base."""

    def __init__(self, engine):
        self.engine = engine
        self.n = 0
        event.listen(engine, "before_cursor_execute", self._sumar)

    def _sumar(self, *args, **kwargs):
        self.n += 1

    def __enter__(self):
        self.n = 0
        return self

    def __exit__(self, *args):
        event.remove(self.engine, "before_cursor_execute", self._sumar)


def armar_plan(session, programa, politica_base100, n_materias,
               politica_examen=None, desde=0, con_periodo=True):
    """
    Plan de n materias encadenadas por previaturas, todas dictandose este anio y
    con una fecha de examen abierta en cada una.

    `desde` desplaza la numeracion: los tests amplian el plan en dos tandas y los
    codigos de materia son unicos.
    """
    ahora = datetime.now(tz())
    if con_periodo:
        session.add(PeriodoInscripcionMateria(
            programa_id=programa.id, anio_lectivo=2026,
            fecha_inicio=ahora - timedelta(days=5),
            fecha_fin=ahora + timedelta(days=5),
            habilitado=True,
        ))
        session.commit()

    anterior = None
    for offset in range(n_materias):
        i = desde + offset
        materia = Materia(
            programa_id=programa.id, nombre=f"Materia {i:02d}", codigo=f"MX{i:02d}",
            semestre=(i % 4) + 1, creditos=10, politica_id=politica_base100.id,
            politica_examen_id=politica_examen.id if politica_examen else None,
            activo=True,
        )
        session.add(materia)
        session.commit()
        session.refresh(materia)

        ic = InstanciaCursado(
            materia_id=materia.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.EN_CURSO, cupo_maximo=30,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        if anterior is not None:
            session.add(Previatura(
                materia_id=materia.id, materia_previa_id=anterior.id,
                tipo_requerido=TipoPreviatura.APROBADA,
            ))
        anterior = materia

        base = ahora.replace(tzinfo=None)
        session.add(InstanciaExamen(
            materia_id=materia.id, nombre=f"Examen {i:02d}",
            fecha_inicio_inscripcion=base - timedelta(days=2),
            fecha_fin_inscripcion=base + timedelta(days=2),
            fecha_examen=base + timedelta(days=10),
        ))
        session.commit()

    return anterior


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


def contar(engine, fn):
    with ContadorDeConsultas(engine) as contador:
        fn()
        return contador.n


class TestMateriasHabilitadas:

    def test_no_crece_con_el_tamanio_del_plan(
        self, engine, session, alumno, programa, politica_base100
    ):
        service = InscripcionMateriaService()

        armar_plan(session, programa, politica_base100, POCAS)
        pocas = contar(engine, lambda: service.get_materias_habilitadas(
            alumno.id, programa.id, session))

        armar_plan(session, programa, politica_base100, MUCHAS - POCAS,
                   desde=POCAS, con_periodo=False)
        muchas = contar(engine, lambda: service.get_materias_habilitadas(
            alumno.id, programa.id, session))

        assert pocas == muchas, (
            f"Con {POCAS} materias hace {pocas} consultas y con {MUCHAS} hace "
            f"{muchas}: volvio a haber una consulta dentro del bucle"
        )

    def test_devuelve_las_materias_del_plan(
        self, engine, session, alumno, programa, politica_base100
    ):
        """El conteo constante no sirve si dejo de devolver lo que corresponde."""
        armar_plan(session, programa, politica_base100, POCAS)

        res = InscripcionMateriaService().get_materias_habilitadas(
            alumno.id, programa.id, session
        )

        assert res["periodo_inscripcion"]["abierto"] is True
        assert len(res["materias"]) == POCAS
        # La primera no tiene previas; el resto arrastra la cadena
        primera = next(m for m in res["materias"] if m["nombre"] == "Materia 00")
        assert primera["puede_inscribirse"] is True
        segunda = next(m for m in res["materias"] if m["nombre"] == "Materia 01")
        assert segunda["puede_inscribirse"] is False
        assert any("Materia 00" in m for m in segunda["previaturas_faltantes"])


class TestMateriasDisponiblesLegacy:

    def test_no_crece_con_el_tamanio_del_plan(
        self, engine, session, alumno, programa, politica_base100
    ):
        service = InscripcionMateriaService()

        armar_plan(session, programa, politica_base100, POCAS)
        pocas = contar(engine, lambda: service.get_materias_disponibles(
            alumno.id, programa.id, 2026, session))

        armar_plan(session, programa, politica_base100, MUCHAS - POCAS,
                   desde=POCAS, con_periodo=False)
        muchas = contar(engine, lambda: service.get_materias_disponibles(
            alumno.id, programa.id, 2026, session))

        assert pocas == muchas


class TestExamenesHabilitados:

    def _dejar_a_examen(self, session, alumno):
        instancias = session.exec(select(InstanciaCursado)).all()
        existentes = {
            i.instancia_cursado_id for i in session.exec(
                select(InscripcionMateria).where(
                    InscripcionMateria.alumno_id == alumno.id
                )
            ).all()
        }
        for ic in instancias:
            if ic.id in existentes:
                continue
            session.add(InscripcionMateria(
                alumno_id=alumno.id, instancia_cursado_id=ic.id,
                estado=EstadoInscripcionMateria.A_EXAMEN,
            ))
        session.commit()

    def test_no_crece_con_la_cantidad_de_materias(
        self, engine, session, alumno, programa, politica_base100, politica_examen
    ):
        service = InscripcionExamenService()

        armar_plan(session, programa, politica_base100, POCAS, politica_examen)
        self._dejar_a_examen(session, alumno)
        pocas = contar(engine, lambda: service.get_examenes_habilitados(
            alumno.id, programa.id, session))

        armar_plan(session, programa, politica_base100, MUCHAS - POCAS,
                   politica_examen, desde=POCAS, con_periodo=False)
        self._dejar_a_examen(session, alumno)
        muchas = contar(engine, lambda: service.get_examenes_habilitados(
            alumno.id, programa.id, session))

        assert pocas == muchas, (
            f"{pocas} consultas con {POCAS} materias y {muchas} con {MUCHAS}"
        )

    def test_devuelve_los_examenes_abiertos(
        self, engine, session, alumno, programa, politica_base100, politica_examen
    ):
        armar_plan(session, programa, politica_base100, POCAS, politica_examen)
        self._dejar_a_examen(session, alumno)

        res = InscripcionExamenService().get_examenes_habilitados(
            alumno.id, programa.id, session
        )

        assert len(res) == POCAS
        assert all(e["puede_inscribirse"] for e in res)
        assert all(e["rendiciones_previas"] == 0 for e in res)
