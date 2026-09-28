"""
Avance de un alumno en una carrera (v2/services/avance_service.py).

Plan de test: Programacion 1 -> 2 -> 3 (cada una requiere la anterior
aprobada), mas Base de Datos sin previas.
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from v2.models.enums import (
    EstadoInscripcionExamen, EstadoInscripcionMateria as EM, EstadoInscripcionPrograma, TipoPrograma,
)
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.models.materia import Materia
from v2.models.politica_examen import PoliticaExamen
from v2.models.programa import Programa
from v2.services.avance_service import AvanceService


@pytest.fixture(name="plan")
def fixture_plan(session, programa, materias_con_previaturas, politica_base100):
    examen = PoliticaExamen(nombre="Examen test", nota_maxima=Decimal("100"),
                            umbral_aprobacion=Decimal("70"), max_oportunidades=5)
    session.add(examen)
    session.flush()
    bd = Materia(programa_id=programa.id, nombre="Base de Datos", codigo="BD_T", semestre=1,
                 creditos=10, politica_id=politica_base100.id, activo=True)
    vieja = Materia(programa_id=programa.id, nombre="Materia vieja", codigo="VIEJA_T", semestre=1,
                    creditos=10, politica_id=politica_base100.id, activo=False)
    session.add_all([bd, vieja])
    for m in materias_con_previaturas.values():
        if isinstance(m, Materia):
            m.politica_examen_id = examen.id
            session.add(m)
    bd.politica_examen_id = examen.id
    session.commit()
    return {**materias_con_previaturas, "bd": bd, "vieja": vieja, "examen": examen}


def inscribir(session, alumno, materia, anio, estado, **campos):
    cursada = InstanciaCursado(materia_id=materia.id, anio_lectivo=anio)
    session.add(cursada)
    session.flush()
    insc = InscripcionMateria(alumno_id=alumno.id, instancia_cursado_id=cursada.id, estado=estado, **campos)
    session.add(insc)
    session.commit()
    return insc


def codigos(items):
    return [i.codigo for i in items]


class TestListas:
    def test_cada_materia_en_una_sola_lista(self, session, alumno, programa, plan):
        inscribir(session, alumno, plan["prog1"], 2025, EM.EXONERADO, nota_final=Decimal("90"), creditos_obtenidos=10)
        inscribir(session, alumno, plan["prog2"], 2026, EM.CURSANDO, faltas=2)
        r = AvanceService().avance(alumno.id, programa.id, session)

        assert codigos(r.aprobadas) == ["P1_T"]
        assert codigos(r.cursando) == ["P2_T"]
        assert r.cursando[0].faltas == 2
        assert sorted(codigos(r.pendientes)) == ["BD_T", "P3_T"]
        assert r.a_examen == []
        # La materia inactiva no es parte del plan vigente
        assert "VIEJA_T" not in codigos(r.aprobadas + r.cursando + r.a_examen + r.pendientes)
        assert (r.resumen.materias_totales, r.resumen.aprobadas, r.resumen.pendientes) == (4, 1, 2)
        assert (r.resumen.creditos_obtenidos, r.resumen.creditos_requeridos) == (10, 200)

    def test_una_aprobacion_gana_sobre_una_recursada_posterior(self, session, alumno, programa, plan):
        inscribir(session, alumno, plan["prog1"], 2024, EM.REPROBADO)
        inscribir(session, alumno, plan["prog1"], 2025, EM.APROBADO, nota_final=Decimal("75"))
        inscribir(session, alumno, plan["prog1"], 2026, EM.CURSANDO)
        r = AvanceService().avance(alumno.id, programa.id, session)
        assert codigos(r.aprobadas) == ["P1_T"]
        assert r.aprobadas[0].anio_lectivo == 2025
        assert "P1_T" not in codigos(r.cursando)

    def test_a_examen_con_oportunidades_usadas(self, session, alumno, programa, plan):
        insc = inscribir(session, alumno, plan["bd"], 2025, EM.A_EXAMEN, nota_curso=Decimal("75"))
        for estado in (EstadoInscripcionExamen.REPROBADO, EstadoInscripcionExamen.AUSENTE,
                       EstadoInscripcionExamen.BAJA):
            session.add(InscripcionExamen(inscripcion_materia_id=insc.id, estado=estado,
                                          **_instancia_examen(session, plan["bd"])))
        session.commit()
        r = AvanceService().avance(alumno.id, programa.id, session)
        assert codigos(r.a_examen) == ["BD_T"]
        item = r.a_examen[0]
        # Reprobado y ausente gastan oportunidad; la baja no
        assert (item.rendiciones_usadas, item.max_oportunidades) == (2, 5)
        assert item.nota_curso == Decimal("75")


def _instancia_examen(session, materia):
    """Una instancia de examen minima para colgar una rendicion."""
    ahora = datetime.now()
    inst = InstanciaExamen(materia_id=materia.id, nombre="Examen test",
                           fecha_inicio_inscripcion=ahora - timedelta(days=5),
                           fecha_fin_inscripcion=ahora - timedelta(days=2),
                           fecha_examen=ahora - timedelta(days=1))
    session.add(inst)
    session.flush()
    return {"instancia_examen_id": inst.id}


class TestPendientes:
    def test_dice_si_cumple_las_previaturas(self, session, alumno, programa, plan):
        inscribir(session, alumno, plan["prog1"], 2025, EM.APROBADO)
        r = AvanceService().avance(alumno.id, programa.id, session)
        por_codigo = {i.codigo: i for i in r.pendientes}
        assert por_codigo["P2_T"].cumple_previaturas is True
        assert por_codigo["P3_T"].cumple_previaturas is False
        assert por_codigo["P3_T"].previaturas_faltantes
        assert por_codigo["BD_T"].cumple_previaturas is True

    def test_trae_el_ultimo_estado(self, session, alumno, programa, plan):
        inscribir(session, alumno, plan["bd"], 2025, EM.ABANDONO)
        r = AvanceService().avance(alumno.id, programa.id, session)
        bd = next(i for i in r.pendientes if i.codigo == "BD_T")
        assert bd.estado == "abandono"
        nunca = next(i for i in r.pendientes if i.codigo == "P3_T")
        assert nunca.estado is None and nunca.inscripcion_id is None


class TestOtrosPlanes:
    def test_lo_aprobado_en_otro_plan_va_aparte(self, session, alumno, politica_base100):
        vigente = Programa(nombre="Carrera X (Plan 2022)", tipo=TipoPrograma.CARRERA)
        viejo = Programa(nombre="Carrera X (Plan 2020)", tipo=TipoPrograma.CARRERA, activo=False)
        otra = Programa(nombre="Otra carrera", tipo=TipoPrograma.CARRERA)
        session.add_all([vigente, viejo, otra])
        session.flush()
        nueva = Materia(programa_id=vigente.id, nombre="Programacion 1", codigo="PX1", semestre=1,
                        creditos=1, politica_id=politica_base100.id)
        antigua = Materia(programa_id=viejo.id, nombre="Programacion 1", codigo="PX1-2020", semestre=1,
                          creditos=1, politica_id=politica_base100.id)
        ajena = Materia(programa_id=otra.id, nombre="Ajena", codigo="AJ", semestre=1,
                        creditos=1, politica_id=politica_base100.id)
        session.add_all([nueva, antigua, ajena])
        session.commit()
        inscribir(session, alumno, antigua, 2021, EM.APROBADO)
        inscribir(session, alumno, ajena, 2021, EM.APROBADO)

        r = AvanceService().avance(alumno.id, vigente.id, session)
        assert codigos(r.aprobadas_otros_planes) == ["PX1-2020"]
        assert r.aprobadas_otros_planes[0].programa == "Carrera X (Plan 2020)"
        # No descuenta pendientes: no hay equivalencias definidas
        assert codigos(r.pendientes) == ["PX1"]


class TestRuta:
    def test_solo_si_esta_inscripto_al_programa(self, session, alumno, programa, plan):
        from v2.routes.estudiante import mi_avance
        from v2.services import get_v2_services

        def llamar():
            return asyncio.run(mi_avance(programa_id=programa.id, current_usuario=None, alumno=alumno,
                                         v2_services=get_v2_services(), session=session))

        with pytest.raises(HTTPException) as error:
            llamar()
        assert error.value.status_code == 403

        # Con la carrera suspendida tambien lo ve
        session.add(InscripcionPrograma(alumno_id=alumno.id, programa_id=programa.id, anio_ingreso=2024,
                                        estado=EstadoInscripcionPrograma.SUSPENDIDA))
        session.commit()
        assert llamar().programa_id == programa.id
