"""
Calificacion de evaluaciones grupales.

Una evaluacion grupal se corrige una vez y vale para todo el equipo. Antes la nota
se guardaba en una sola inscripcion y el equipo_id quedaba de adorno, asi que el
docente terminaba cargando la misma nota integrante por integrante.
"""
import pytest
from decimal import Decimal
from sqlmodel import select

from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
from v2.models.calificacion import Calificacion
from v2.models.equipo import Equipo, EquipoMiembro
from v2.models.enums import EstadoInscripcionMateria, EstadoInstanciaCursado
from v2.services.calificacion_service import CalificacionService


SNAPSHOT_POLITICA = {
    "nota_maxima": 100.0,
    "umbral_aprobacion": 70.0,
    "umbral_examen": 70.0,
    "umbral_exoneracion": 86.0,
}


@pytest.fixture(name="obligatorio")
def fixture_obligatorio(session, materias_con_previaturas):
    """Cursada con una evaluacion grupal, como el obligatorio."""
    m1 = materias_con_previaturas["prog1"]
    ic = InstanciaCursado(
        materia_id=m1.id, anio_lectivo=2026,
        estado=EstadoInstanciaCursado.EN_CURSO,
    )
    session.add(ic)
    session.commit()
    session.refresh(ic)

    ev = MateriaInstanciaEvaluacion(
        instancia_cursado_id=ic.id, nombre="Obligatorio",
        peso_maximo=Decimal("100"), orden=1, es_grupal=True,
    )
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return {"instancia_cursado": ic, "evaluacion": ev}


def inscribir(session, alumno, ic, ev):
    insc = InscripcionMateria(
        alumno_id=alumno.id,
        instancia_cursado_id=ic.id,
        estado=EstadoInscripcionMateria.CURSANDO,
        snapshot_politica=SNAPSHOT_POLITICA,
        snapshot_instancias=[{"id": ev.id, "nombre": ev.nombre,
                              "peso_maximo": float(ev.peso_maximo)}],
    )
    session.add(insc)
    session.commit()
    session.refresh(insc)
    return insc


def armar_equipo(session, ev, alumnos, nombre="Equipo 1"):
    equipo = Equipo(instancia_evaluacion_id=ev.id, nombre=nombre)
    session.add(equipo)
    session.commit()
    session.refresh(equipo)

    for a in alumnos:
        session.add(EquipoMiembro(equipo_id=equipo.id, alumno_id=a.id))
    session.commit()
    return equipo


def notas_de(session, ev_id):
    return {
        c.inscripcion_id: c.nota
        for c in session.exec(
            select(Calificacion).where(Calificacion.instancia_evaluacion_id == ev_id)
        ).all()
    }


class TestPropagacionGrupal:

    def test_la_nota_llega_a_todos_los_integrantes(
        self, session, alumno, otro_alumno, obligatorio
    ):
        ic, ev = obligatorio["instancia_cursado"], obligatorio["evaluacion"]
        insc_a = inscribir(session, alumno, ic, ev)
        insc_b = inscribir(session, otro_alumno, ic, ev)
        equipo = armar_equipo(session, ev, [alumno, otro_alumno])

        CalificacionService().guardar_calificacion(
            cargado_por_id=1,
            inscripcion_id=insc_a.id,
            instancia_evaluacion_id=ev.id,
            nota=Decimal("88"),
            session=session,
            equipo_id=equipo.id,
            instancia_cursado_id=ic.id,
        )

        notas = notas_de(session, ev.id)
        assert notas == {insc_a.id: Decimal("88"), insc_b.id: Decimal("88")}

    def test_el_estado_se_recalcula_para_todos(
        self, session, alumno, otro_alumno, obligatorio
    ):
        """No alcanza con escribir la nota: cada inscripcion tiene que recalcularse."""
        ic, ev = obligatorio["instancia_cursado"], obligatorio["evaluacion"]
        insc_a = inscribir(session, alumno, ic, ev)
        insc_b = inscribir(session, otro_alumno, ic, ev)
        equipo = armar_equipo(session, ev, [alumno, otro_alumno])

        CalificacionService().guardar_calificacion(
            cargado_por_id=1, inscripcion_id=insc_a.id,
            instancia_evaluacion_id=ev.id, nota=Decimal("90"),
            session=session, equipo_id=equipo.id, instancia_cursado_id=ic.id,
        )

        session.refresh(insc_a)
        session.refresh(insc_b)
        # 90 supera el umbral de exoneracion (86) y es la unica evaluacion
        assert insc_a.estado == EstadoInscripcionMateria.EXONERADO
        assert insc_b.estado == EstadoInscripcionMateria.EXONERADO

    def test_equipo_de_un_solo_integrante(self, session, alumno, obligatorio):
        """El obligatorio puede ser de una sola persona."""
        ic, ev = obligatorio["instancia_cursado"], obligatorio["evaluacion"]
        insc = inscribir(session, alumno, ic, ev)
        equipo = armar_equipo(session, ev, [alumno], nombre="Equipo individual")

        CalificacionService().guardar_calificacion(
            cargado_por_id=1, inscripcion_id=insc.id,
            instancia_evaluacion_id=ev.id, nota=Decimal("75"),
            session=session, equipo_id=equipo.id, instancia_cursado_id=ic.id,
        )

        assert notas_de(session, ev.id) == {insc.id: Decimal("75")}

    def test_recalificar_actualiza_a_todo_el_equipo(
        self, session, alumno, otro_alumno, obligatorio
    ):
        """
        Corregir la nota del obligatorio la corrige para todos.

        Se usa 70 como nota inicial y no una nota baja a proposito: con 70 la
        inscripcion queda en A_EXAMEN, que todavia admite calificar. Una nota por
        debajo del umbral de examen la cierra como REPROBADO y el sistema ya no
        deja corregirla (ver test_no_se_puede_corregir_una_inscripcion_cerrada).
        """
        ic, ev = obligatorio["instancia_cursado"], obligatorio["evaluacion"]
        insc_a = inscribir(session, alumno, ic, ev)
        insc_b = inscribir(session, otro_alumno, ic, ev)
        equipo = armar_equipo(session, ev, [alumno, otro_alumno])
        service = CalificacionService()

        service.guardar_calificacion(
            cargado_por_id=1, inscripcion_id=insc_a.id,
            instancia_evaluacion_id=ev.id, nota=Decimal("70"),
            session=session, equipo_id=equipo.id, instancia_cursado_id=ic.id,
        )
        service.guardar_calificacion(
            cargado_por_id=1, inscripcion_id=insc_a.id,
            instancia_evaluacion_id=ev.id, nota=Decimal("95"),
            session=session, equipo_id=equipo.id, instancia_cursado_id=ic.id,
        )

        notas = notas_de(session, ev.id)
        assert notas == {insc_a.id: Decimal("95"), insc_b.id: Decimal("95")}
        assert len(notas) == 2, "no debe duplicar calificaciones al recalificar"

    def test_se_corrige_el_obligatorio_de_un_equipo_ya_cerrado(
        self, session, alumno, otro_alumno, obligatorio
    ):
        """Corregir un obligatorio mal cargado reabre a todo el equipo, no a uno."""
        ic, ev = obligatorio["instancia_cursado"], obligatorio["evaluacion"]
        insc_a = inscribir(session, alumno, ic, ev)
        insc_b = inscribir(session, otro_alumno, ic, ev)
        equipo = armar_equipo(session, ev, [alumno, otro_alumno])
        service = CalificacionService()

        service.guardar_calificacion(
            cargado_por_id=1, inscripcion_id=insc_a.id,
            instancia_evaluacion_id=ev.id, nota=Decimal("60"),
            session=session, equipo_id=equipo.id, instancia_cursado_id=ic.id,
        )
        session.refresh(insc_a)
        session.refresh(insc_b)
        assert insc_a.estado == EstadoInscripcionMateria.REPROBADO
        assert insc_b.estado == EstadoInscripcionMateria.REPROBADO

        service.guardar_calificacion(
            cargado_por_id=1, inscripcion_id=insc_a.id,
            instancia_evaluacion_id=ev.id, nota=Decimal("95"),
            session=session, equipo_id=equipo.id, instancia_cursado_id=ic.id,
        )
        session.refresh(insc_a)
        session.refresh(insc_b)
        assert insc_a.estado == EstadoInscripcionMateria.EXONERADO
        assert insc_b.estado == EstadoInscripcionMateria.EXONERADO

    def test_integrante_que_abandono_no_recibe_nota(
        self, session, alumno, otro_alumno, obligatorio
    ):
        """Si un integrante cerro la materia, se lo saltea sin abortar al resto."""
        ic, ev = obligatorio["instancia_cursado"], obligatorio["evaluacion"]
        insc_a = inscribir(session, alumno, ic, ev)
        insc_b = inscribir(session, otro_alumno, ic, ev)
        insc_b.estado = EstadoInscripcionMateria.ABANDONO
        session.add(insc_b)
        session.commit()

        equipo = armar_equipo(session, ev, [alumno, otro_alumno])

        CalificacionService().guardar_calificacion(
            cargado_por_id=1, inscripcion_id=insc_a.id,
            instancia_evaluacion_id=ev.id, nota=Decimal("80"),
            session=session, equipo_id=equipo.id, instancia_cursado_id=ic.id,
        )

        notas = notas_de(session, ev.id)
        assert notas == {insc_a.id: Decimal("80")}


class TestValidacionesGrupales:

    def test_equipo_obligatorio_en_instancia_grupal(
        self, session, alumno, obligatorio
    ):
        ic, ev = obligatorio["instancia_cursado"], obligatorio["evaluacion"]
        insc = inscribir(session, alumno, ic, ev)

        with pytest.raises(ValueError, match="se requiere equipo_id"):
            CalificacionService().guardar_calificacion(
                cargado_por_id=1, inscripcion_id=insc.id,
                instancia_evaluacion_id=ev.id, nota=Decimal("80"),
                session=session, instancia_cursado_id=ic.id,
            )

    def test_equipo_de_otra_evaluacion_es_rechazado(
        self, session, alumno, obligatorio
    ):
        ic, ev = obligatorio["instancia_cursado"], obligatorio["evaluacion"]
        insc = inscribir(session, alumno, ic, ev)

        otra_ev = MateriaInstanciaEvaluacion(
            instancia_cursado_id=ic.id, nombre="Otro obligatorio",
            peso_maximo=Decimal("100"), orden=2, es_grupal=True,
        )
        session.add(otra_ev)
        session.commit()
        session.refresh(otra_ev)
        equipo_ajeno = armar_equipo(session, otra_ev, [alumno], nombre="Ajeno")

        with pytest.raises(ValueError, match="no pertenece a la instancia de evaluacion"):
            CalificacionService().guardar_calificacion(
                cargado_por_id=1, inscripcion_id=insc.id,
                instancia_evaluacion_id=ev.id, nota=Decimal("80"),
                session=session, equipo_id=equipo_ajeno.id,
                instancia_cursado_id=ic.id,
            )

    def test_alumno_que_no_integra_el_equipo(
        self, session, alumno, otro_alumno, obligatorio
    ):
        """No se puede calificar a alguien a traves de un equipo que no integra."""
        ic, ev = obligatorio["instancia_cursado"], obligatorio["evaluacion"]
        insc_a = inscribir(session, alumno, ic, ev)
        equipo_sin_a = armar_equipo(session, ev, [otro_alumno])

        with pytest.raises(ValueError, match="no integra el equipo"):
            CalificacionService().guardar_calificacion(
                cargado_por_id=1, inscripcion_id=insc_a.id,
                instancia_evaluacion_id=ev.id, nota=Decimal("80"),
                session=session, equipo_id=equipo_sin_a.id,
                instancia_cursado_id=ic.id,
            )

    def test_equipo_inexistente(self, session, alumno, obligatorio):
        ic, ev = obligatorio["instancia_cursado"], obligatorio["evaluacion"]
        insc = inscribir(session, alumno, ic, ev)

        with pytest.raises(ValueError, match="Equipo 9999 no encontrado"):
            CalificacionService().guardar_calificacion(
                cargado_por_id=1, inscripcion_id=insc.id,
                instancia_evaluacion_id=ev.id, nota=Decimal("80"),
                session=session, equipo_id=9999, instancia_cursado_id=ic.id,
            )
