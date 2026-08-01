"""
Armado de equipos para evaluaciones grupales.

Tres agujeros que permitian dejar los equipos en un estado que la calificacion
grupal no puede resolver:
- integrantes que no cursan la materia (la nota no les llega a ningun lado)
- un alumno en dos equipos de la misma evaluacion (el segundo pisa la nota del
  primero, en silencio)
- borrar un equipo con notas cargadas
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
from v2.services.equipo_service import EquipoService


@pytest.fixture(name="grupal")
def fixture_grupal(session, alumno, otro_alumno, materias_con_previaturas):
    """Cursada con una evaluacion grupal y los dos alumnos inscriptos."""
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
    individual = MateriaInstanciaEvaluacion(
        instancia_cursado_id=ic.id, nombre="Parcial",
        peso_maximo=Decimal("0"), orden=2, es_grupal=False,
    )
    session.add_all([ev, individual])
    session.commit()
    session.refresh(ev)
    session.refresh(individual)

    for a in (alumno, otro_alumno):
        session.add(InscripcionMateria(
            alumno_id=a.id, instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.CURSANDO,
        ))
    session.commit()

    return {"ic": ic, "ev": ev, "individual": individual}


class TestArmadoDeEquipos:

    def test_equipo_con_alumnos_de_la_cursada(
        self, session, alumno, otro_alumno, grupal
    ):
        equipo = EquipoService().create_equipo(
            grupal["ev"].id, "Equipo 1", [alumno.id, otro_alumno.id], session
        )

        miembros = session.exec(
            select(EquipoMiembro).where(EquipoMiembro.equipo_id == equipo.id)
        ).all()
        assert len(miembros) == 2

    def test_rechaza_un_alumno_que_no_cursa(
        self, session, alumno, otro_alumno, grupal, materias_con_previaturas
    ):
        """otro_alumno se desinscribe: ya no puede integrar el equipo."""
        insc = session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.alumno_id == otro_alumno.id
            )
        ).first()
        session.delete(insc)
        session.commit()

        with pytest.raises(ValueError, match="no esta inscripto a la cursada"):
            EquipoService().create_equipo(
                grupal["ev"].id, "Equipo 1", [alumno.id, otro_alumno.id], session
            )

    def test_no_deja_el_equipo_a_medio_armar(
        self, session, alumno, otro_alumno, grupal
    ):
        """Si un integrante no sirve, no se crea el equipo con el resto."""
        insc = session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.alumno_id == otro_alumno.id
            )
        ).first()
        session.delete(insc)
        session.commit()

        with pytest.raises(ValueError):
            EquipoService().create_equipo(
                grupal["ev"].id, "Equipo 1", [alumno.id, otro_alumno.id], session
            )

        assert session.exec(select(Equipo)).first() is None

    def test_rechaza_integrantes_repetidos(self, session, alumno, grupal):
        with pytest.raises(ValueError, match="repetidos"):
            EquipoService().create_equipo(
                grupal["ev"].id, "Equipo 1", [alumno.id, alumno.id], session
            )

    def test_la_evaluacion_tiene_que_ser_grupal(self, session, alumno, grupal):
        with pytest.raises(ValueError, match="no es de tipo grupal"):
            EquipoService().create_equipo(
                grupal["individual"].id, "Equipo 1", [alumno.id], session
            )


class TestUnEquipoPorAlumnoYEvaluacion:

    def test_no_puede_estar_en_dos_equipos_de_la_misma_evaluacion(
        self, session, alumno, grupal
    ):
        """
        El caso grave: la calificacion es unica por inscripcion + evaluacion, asi
        que calificar el segundo equipo le pisaba la nota del primero.
        """
        service = EquipoService()
        service.create_equipo(grupal["ev"].id, "Equipo 1", [alumno.id], session)

        with pytest.raises(ValueError, match="ya integra el equipo"):
            service.create_equipo(grupal["ev"].id, "Equipo 2", [alumno.id], session)

    def test_tampoco_agregandolo_despues(self, session, alumno, grupal):
        service = EquipoService()
        service.create_equipo(grupal["ev"].id, "Equipo 1", [alumno.id], session)
        eq2 = service.create_equipo(grupal["ev"].id, "Equipo 2", [], session)

        with pytest.raises(ValueError, match="ya integra el equipo"):
            service.add_miembro(eq2.id, alumno.id, session)

    def test_si_puede_estar_en_equipos_de_evaluaciones_distintas(
        self, session, alumno, grupal
    ):
        """La restriccion es por evaluacion, no global."""
        otra_ev = MateriaInstanciaEvaluacion(
            instancia_cursado_id=grupal["ic"].id, nombre="Segundo obligatorio",
            peso_maximo=Decimal("0"), orden=3, es_grupal=True,
        )
        session.add(otra_ev)
        session.commit()
        session.refresh(otra_ev)

        service = EquipoService()
        service.create_equipo(grupal["ev"].id, "Equipo 1", [alumno.id], session)
        equipo2 = service.create_equipo(otra_ev.id, "Equipo A", [alumno.id], session)

        assert equipo2.id is not None

    def test_agregar_dos_veces_al_mismo_equipo(self, session, alumno, grupal):
        service = EquipoService()
        equipo = service.create_equipo(grupal["ev"].id, "Equipo 1", [alumno.id], session)

        with pytest.raises(ValueError, match="ya es miembro de este equipo"):
            service.add_miembro(equipo.id, alumno.id, session)


class TestBorradoDeEquipo:

    def test_se_borra_un_equipo_sin_notas(self, session, alumno, grupal):
        service = EquipoService()
        equipo = service.create_equipo(grupal["ev"].id, "Equipo 1", [alumno.id], session)
        equipo_id = equipo.id

        service.delete_equipo(equipo_id, session)

        assert session.get(Equipo, equipo_id) is None
        assert session.exec(
            select(EquipoMiembro).where(EquipoMiembro.equipo_id == equipo_id)
        ).first() is None

    def test_no_se_borra_un_equipo_con_notas(self, session, alumno, grupal):
        """Borrarlo dejaba la calificacion apuntando a un equipo inexistente."""
        service = EquipoService()
        equipo = service.create_equipo(grupal["ev"].id, "Equipo 1", [alumno.id], session)

        insc = session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.alumno_id == alumno.id
            )
        ).first()
        session.add(Calificacion(
            inscripcion_id=insc.id, instancia_evaluacion_id=grupal["ev"].id,
            nota=Decimal("80"), equipo_id=equipo.id, cargado_por_id=1,
        ))
        session.commit()

        with pytest.raises(ValueError, match="calificaciones registradas"):
            service.delete_equipo(equipo.id, session)

        assert session.get(Equipo, equipo.id) is not None
