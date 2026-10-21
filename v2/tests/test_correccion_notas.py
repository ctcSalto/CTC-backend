"""
Correccion de notas despues de cerrada la inscripcion.

Cerrar la materia no puede congelar las notas: un 60 tipeado en lugar de un 90
dejaba al alumno reprobado sin ninguna via de vuelta. Ahora se puede corregir,
salvo en los estados que no decidio el curso (revalida, inasistencia, abandono) y
cuando la materia se aprobo rindiendo examen, porque recalcular desde las notas
de curso pisaria ese resultado.
"""
import pytest
from decimal import Decimal

from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
from v2.models.enums import (
    EstadoInscripcionMateria, EstadoInstanciaCursado, EstadoInscripcionExamen,
)
from v2.services.calificacion_service import CalificacionService

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os


SNAPSHOT_POLITICA = {
    "nota_maxima": 100.0,
    "umbral_aprobacion": 70.0,
    "umbral_examen": 70.0,
    "umbral_exoneracion": 86.0,
}


@pytest.fixture(name="cursada")
def fixture_cursada(session, materias_con_previaturas):
    m1 = materias_con_previaturas["prog1"]
    ic = InstanciaCursado(
        materia_id=m1.id, anio_lectivo=2026,
        estado=EstadoInstanciaCursado.EN_CURSO,
    )
    session.add(ic)
    session.commit()
    session.refresh(ic)

    ev = MateriaInstanciaEvaluacion(
        instancia_cursado_id=ic.id, nombre="Parcial unico",
        peso_maximo=Decimal("100"), orden=1,
    )
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return {"ic": ic, "ev": ev, "materia": m1}


def inscribir(session, alumno, cursada, estado=EstadoInscripcionMateria.CURSANDO):
    insc = InscripcionMateria(
        alumno_id=alumno.id,
        instancia_cursado_id=cursada["ic"].id,
        estado=estado,
        snapshot_politica=SNAPSHOT_POLITICA,
        snapshot_instancias=[{
            "id": cursada["ev"].id, "nombre": cursada["ev"].nombre,
            "peso_maximo": 100.0,
        }],
    )
    session.add(insc)
    session.commit()
    session.refresh(insc)
    return insc


def calificar(session, insc, cursada, nota):
    return CalificacionService().guardar_calificacion(
        cargado_por_id=1, inscripcion_id=insc.id,
        instancia_evaluacion_id=cursada["ev"].id, nota=Decimal(str(nota)),
        session=session, instancia_cursado_id=cursada["ic"].id,
    )


class TestCorreccionDeNotas:

    def test_se_corrige_un_reprobado_por_error_de_tipeo(
        self, session, alumno, cursada
    ):
        """El caso que motiva el cambio: 60 en vez de 90."""
        insc = inscribir(session, alumno, cursada)

        calificar(session, insc, cursada, 60)
        session.refresh(insc)
        assert insc.estado == EstadoInscripcionMateria.REPROBADO

        calificar(session, insc, cursada, 90)
        session.refresh(insc)
        assert insc.estado == EstadoInscripcionMateria.EXONERADO
        assert insc.nota_curso == Decimal("90")
        assert insc.creditos_obtenidos == cursada["materia"].creditos

    def test_se_corrige_hacia_abajo(self, session, alumno, cursada):
        """Tambien al reves: de exonerado a reprobado."""
        insc = inscribir(session, alumno, cursada)

        calificar(session, insc, cursada, 90)
        session.refresh(insc)
        assert insc.estado == EstadoInscripcionMateria.EXONERADO
        assert insc.creditos_obtenidos > 0

        calificar(session, insc, cursada, 50)
        session.refresh(insc)
        assert insc.estado == EstadoInscripcionMateria.REPROBADO
        assert insc.creditos_obtenidos == 0

    def test_la_fecha_de_cierre_se_limpia_al_reabrir(self, session, alumno, cursada):
        """
        Si la correccion devuelve la inscripcion a un estado abierto, la fecha de
        cierre vieja no puede quedar: figuraria cerrada y abierta a la vez.
        """
        insc = inscribir(session, alumno, cursada)

        calificar(session, insc, cursada, 50)
        session.refresh(insc)
        assert insc.estado == EstadoInscripcionMateria.REPROBADO
        assert insc.fecha_cierre is not None

        # 70 alcanza el umbral de examen: vuelve a un estado abierto
        calificar(session, insc, cursada, 70)
        session.refresh(insc)
        assert insc.estado == EstadoInscripcionMateria.A_EXAMEN
        assert insc.fecha_cierre is None

    def test_la_fecha_de_cierre_original_se_conserva(self, session, alumno, cursada):
        """Corregir dentro de estados cerrados no reescribe la fecha del cierre."""
        insc = inscribir(session, alumno, cursada)

        calificar(session, insc, cursada, 50)
        session.refresh(insc)
        primera_fecha = insc.fecha_cierre

        calificar(session, insc, cursada, 40)
        session.refresh(insc)
        assert insc.estado == EstadoInscripcionMateria.REPROBADO
        assert insc.fecha_cierre == primera_fecha


class TestEstadosQueNoSeEditan:

    def test_revalidada(self, session, alumno, cursada):
        insc = inscribir(session, alumno, cursada,
                         estado=EstadoInscripcionMateria.REVALIDADA)

        with pytest.raises(ValueError, match="revalidada por administracion"):
            calificar(session, insc, cursada, 90)

    def test_perdido_por_inasistencia(self, session, alumno, cursada):
        insc = inscribir(session, alumno, cursada,
                         estado=EstadoInscripcionMateria.PERDIDO_INASISTENCIA)

        with pytest.raises(ValueError, match="inasistencia"):
            calificar(session, insc, cursada, 90)

    def test_abandono(self, session, alumno, cursada):
        insc = inscribir(session, alumno, cursada,
                         estado=EstadoInscripcionMateria.ABANDONO)

        with pytest.raises(ValueError, match="dada de baja"):
            calificar(session, insc, cursada, 90)

    def test_aprobada_rindiendo_examen(self, session, alumno, cursada):
        """
        Recalcular desde las notas de curso pisaria el resultado del examen y
        dejaria la inscripcion a examen colgada. Se deriva a corregir el examen.
        """
        insc = inscribir(session, alumno, cursada,
                         estado=EstadoInscripcionMateria.APROBADO)

        ahora = datetime.now(ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo")))
        inst_examen = InstanciaExamen(
            materia_id=cursada["materia"].id, nombre="Febrero",
            fecha_inicio_inscripcion=ahora.replace(tzinfo=None) - timedelta(days=30),
            fecha_fin_inscripcion=ahora.replace(tzinfo=None) - timedelta(days=20),
            fecha_examen=ahora.replace(tzinfo=None) - timedelta(days=10),
        )
        session.add(inst_examen)
        session.commit()
        session.refresh(inst_examen)

        session.add(InscripcionExamen(
            inscripcion_materia_id=insc.id,
            instancia_examen_id=inst_examen.id,
            estado=EstadoInscripcionExamen.APROBADO,
            nota_examen=Decimal("75"),
        ))
        session.commit()

        with pytest.raises(ValueError, match="rindiendo examen"):
            calificar(session, insc, cursada, 90)

    def test_aprobada_por_curso_si_se_edita(self, session, alumno, cursada):
        """
        Una APROBADO sin examen rendido (curso corto) si se puede corregir: el
        bloqueo es solo para las que vienen de un examen.
        """
        insc = inscribir(session, alumno, cursada,
                         estado=EstadoInscripcionMateria.APROBADO)

        calificar(session, insc, cursada, 95)
        session.refresh(insc)
        assert insc.estado == EstadoInscripcionMateria.EXONERADO


class TestNotaFinalDirecta:

    def test_se_corrige_una_nota_final_directa(self, session, alumno, cursada):
        service = CalificacionService()
        insc = inscribir(session, alumno, cursada)

        service.cargar_nota_final_directa(
            cargado_por_id=1, inscripcion_id=insc.id, nota=Decimal("55"),
            session=session, instancia_cursado_id=cursada["ic"].id,
        )
        session.refresh(insc)
        assert insc.estado == EstadoInscripcionMateria.REPROBADO

        service.cargar_nota_final_directa(
            cargado_por_id=1, inscripcion_id=insc.id, nota=Decimal("88"),
            session=session, instancia_cursado_id=cursada["ic"].id,
        )
        session.refresh(insc)
        assert insc.estado == EstadoInscripcionMateria.EXONERADO
        assert insc.nota_final_directa == Decimal("88")

    def test_no_se_corrige_una_revalidada(self, session, alumno, cursada):
        insc = inscribir(session, alumno, cursada,
                         estado=EstadoInscripcionMateria.REVALIDADA)

        with pytest.raises(ValueError, match="revalidada"):
            CalificacionService().cargar_nota_final_directa(
                cargado_por_id=1, inscripcion_id=insc.id, nota=Decimal("90"),
                session=session, instancia_cursado_id=cursada["ic"].id,
            )
