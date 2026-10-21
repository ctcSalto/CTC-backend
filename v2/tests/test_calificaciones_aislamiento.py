"""
Tests de aislamiento de calificaciones.

Cubre dos agujeros que permitian escribir notas donde no correspondia:

1. El permiso de la ruta es sobre la cursada del path, pero la inscripcion y la
   instancia de evaluacion vienen en el body. Sin validar que coincidan, un
   docente asignado a una sola cursada podia calificar a cualquier alumno.

2. El snapshot congela las reglas al inscribirse, pero la suma de notas no lo
   respetaba: una evaluacion creada despues sumaba igual y podia mover el estado.
"""
import pytest
from decimal import Decimal
from sqlmodel import select

from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
from v2.models.calificacion import Calificacion
from v2.models.enums import EstadoInscripcionMateria, EstadoInstanciaCursado
from v2.services.calificacion_service import CalificacionService


SNAPSHOT_POLITICA = {
    "nota_maxima": 100.0,
    "tipo_nota": "numerica",
    "umbral_aprobacion": 60.0,
    "umbral_examen": 40.0,
    "umbral_exoneracion": 86.0,
}


def crear_cursada_con_evaluacion(session, materia, peso=Decimal("100")):
    """Instancia de cursado con una evaluacion, para armar escenarios cruzados."""
    ic = InstanciaCursado(
        materia_id=materia.id, anio_lectivo=2026,
        estado=EstadoInstanciaCursado.EN_CURSO,
    )
    session.add(ic)
    session.commit()
    session.refresh(ic)

    ev = MateriaInstanciaEvaluacion(
        instancia_cursado_id=ic.id, nombre=f"Parcial {materia.codigo}",
        peso_maximo=peso, orden=1,
    )
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return ic, ev


def inscribir(session, alumno, ic, evaluaciones):
    insc = InscripcionMateria(
        alumno_id=alumno.id,
        instancia_cursado_id=ic.id,
        estado=EstadoInscripcionMateria.CURSANDO,
        snapshot_politica=SNAPSHOT_POLITICA,
        snapshot_instancias=[
            {"id": ev.id, "nombre": ev.nombre, "peso_maximo": float(ev.peso_maximo)}
            for ev in evaluaciones
        ],
    )
    session.add(insc)
    session.commit()
    session.refresh(insc)
    return insc


class TestAislamientoEntreCursadas:

    def test_no_se_puede_calificar_con_evaluacion_de_otra_cursada(
        self, session, otro_alumno, materias_con_previaturas
    ):
        """La evaluacion tiene que ser de la misma cursada que la inscripcion."""
        ic_a, ev_a = crear_cursada_con_evaluacion(
            session, materias_con_previaturas["prog1"]
        )
        ic_b, ev_b = crear_cursada_con_evaluacion(
            session, materias_con_previaturas["prog2"]
        )
        insc_b = inscribir(session, otro_alumno, ic_b, [ev_b])

        with pytest.raises(ValueError, match="no pertenece a la cursada"):
            CalificacionService().guardar_calificacion(
                cargado_por_id=1,
                inscripcion_id=insc_b.id,
                instancia_evaluacion_id=ev_a.id,   # evaluacion de la otra materia
                nota=Decimal("99"),
                session=session,
            )

        # Y no quedo ninguna calificacion escrita
        assert session.exec(select(Calificacion)).first() is None

    def test_no_se_puede_calificar_inscripcion_de_otra_cursada(
        self, session, otro_alumno, materias_con_previaturas
    ):
        """
        El docente tiene permiso sobre la cursada A (la del path) y manda una
        inscripcion de la cursada B. Tiene que ser rechazado.
        """
        ic_a, ev_a = crear_cursada_con_evaluacion(
            session, materias_con_previaturas["prog1"]
        )
        ic_b, ev_b = crear_cursada_con_evaluacion(
            session, materias_con_previaturas["prog2"]
        )
        insc_b = inscribir(session, otro_alumno, ic_b, [ev_b])

        with pytest.raises(ValueError, match="no pertenece a la instancia de cursado"):
            CalificacionService().guardar_calificacion(
                cargado_por_id=1,
                inscripcion_id=insc_b.id,
                instancia_evaluacion_id=ev_b.id,
                nota=Decimal("99"),
                session=session,
                instancia_cursado_id=ic_a.id,   # permiso sobre la otra cursada
            )

    def test_nota_final_directa_respeta_la_cursada(
        self, session, otro_alumno, materias_con_previaturas
    ):
        """La nota final directa tenia el mismo agujero."""
        ic_a, _ = crear_cursada_con_evaluacion(
            session, materias_con_previaturas["prog1"]
        )
        ic_b, ev_b = crear_cursada_con_evaluacion(
            session, materias_con_previaturas["prog2"]
        )
        insc_b = inscribir(session, otro_alumno, ic_b, [ev_b])

        with pytest.raises(ValueError, match="no pertenece a la instancia de cursado"):
            CalificacionService().cargar_nota_final_directa(
                cargado_por_id=1,
                inscripcion_id=insc_b.id,
                nota=Decimal("90"),
                session=session,
                instancia_cursado_id=ic_a.id,
            )

    def test_calificar_su_propia_cursada_sigue_funcionando(
        self, session, alumno, materias_con_previaturas
    ):
        """El camino legitimo no se rompe con las validaciones nuevas."""
        ic, ev = crear_cursada_con_evaluacion(session, materias_con_previaturas["prog1"])
        insc = inscribir(session, alumno, ic, [ev])

        cal = CalificacionService().guardar_calificacion(
            cargado_por_id=1,
            inscripcion_id=insc.id,
            instancia_evaluacion_id=ev.id,
            nota=Decimal("90"),
            session=session,
            instancia_cursado_id=ic.id,
        )

        assert cal.nota == Decimal("90")
        session.refresh(insc)
        assert insc.nota_curso == Decimal("90")
        assert insc.estado == EstadoInscripcionMateria.EXONERADO


class TestSnapshotCongelaLasReglas:

    def test_evaluacion_posterior_a_la_inscripcion_es_rechazada(
        self, session, alumno, materias_con_previaturas
    ):
        """Una evaluacion que no estaba en el snapshot no se puede calificar."""
        ic, ev1 = crear_cursada_con_evaluacion(
            session, materias_con_previaturas["prog1"], peso=Decimal("50")
        )
        insc = inscribir(session, alumno, ic, [ev1])

        # Evaluacion creada DESPUES de que el alumno se inscribio
        ev2 = MateriaInstanciaEvaluacion(
            instancia_cursado_id=ic.id, nombre="Parcial 2 (nuevo)",
            peso_maximo=Decimal("50"), orden=2,
        )
        session.add(ev2)
        session.commit()
        session.refresh(ev2)

        with pytest.raises(ValueError, match="no estaba vigente"):
            CalificacionService().guardar_calificacion(
                cargado_por_id=1,
                inscripcion_id=insc.id,
                instancia_evaluacion_id=ev2.id,
                nota=Decimal("50"),
                session=session,
                instancia_cursado_id=ic.id,
            )

    def test_nota_fuera_del_snapshot_no_suma_al_recalcular(
        self, session, alumno, materias_con_previaturas
    ):
        """
        Aunque quede una calificacion fuera del snapshot en la base (datos
        viejos, cargados antes de la validacion), no debe alterar el estado.
        """
        service = CalificacionService()
        ic, ev1 = crear_cursada_con_evaluacion(
            session, materias_con_previaturas["prog1"], peso=Decimal("50")
        )
        insc = inscribir(session, alumno, ic, [ev1])

        service.guardar_calificacion(
            cargado_por_id=1, inscripcion_id=insc.id,
            instancia_evaluacion_id=ev1.id, nota=Decimal("45"), session=session,
        )
        session.refresh(insc)
        assert insc.nota_curso == Decimal("45")
        assert insc.estado == EstadoInscripcionMateria.A_EXAMEN

        # Calificacion fuera del snapshot insertada directamente en la base,
        # como quedaria un dato cargado antes de la validacion
        ev2 = MateriaInstanciaEvaluacion(
            instancia_cursado_id=ic.id, nombre="Parcial 2 (nuevo)",
            peso_maximo=Decimal("50"), orden=2,
        )
        session.add(ev2)
        session.commit()
        session.refresh(ev2)

        session.add(Calificacion(
            inscripcion_id=insc.id,
            instancia_evaluacion_id=ev2.id,
            nota=Decimal("50"),
            cargado_por_id=1,
        ))
        session.commit()

        # Forzar un recalculo re-guardando la nota valida
        service.guardar_calificacion(
            cargado_por_id=1, inscripcion_id=insc.id,
            instancia_evaluacion_id=ev1.id, nota=Decimal("45"), session=session,
        )
        session.refresh(insc)

        assert insc.nota_curso == Decimal("45"), (
            "La nota de una evaluacion fuera del snapshot no debe sumar"
        )
        assert insc.estado == EstadoInscripcionMateria.A_EXAMEN
