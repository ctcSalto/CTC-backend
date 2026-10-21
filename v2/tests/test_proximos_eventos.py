"""
Tests del servicio de proximos eventos (pantalla de inicio).

Cubren: orden cronologico ascendente, filtro temporal (>= now), ventana days,
limit, aislamiento por rol y respuesta vacia.
"""
import os
import pytest
from datetime import datetime, timedelta

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("TIME_ZONE", "America/Montevideo")

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from v2.models.usuario import Usuario
from v2.models.alumno import Alumno
from v2.models.profesor import Profesor
from v2.models.programa import Programa
from v2.models.materia import Materia
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.periodo_inscripcion_materia import PeriodoInscripcionMateria
from v2.models.politica_calificacion import PoliticaCalificacion
from v2.models.docente_materia import DocenteMateria
from v2.models.docente_instancia_examen import DocenteInstanciaExamen
from v2.models.enums import (
    RolUsuario, TipoPrograma, AreaPrograma,
    EstadoInscripcionPrograma, EstadoInscripcionMateria, EstadoInscripcionExamen,
    EstadoInstanciaCursado, EstadoInstanciaExamen, RolDocente, TipoEventoProximo,
)
from v2.services.proximos_eventos_service import ProximosEventosService


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


# Fechas naive relativas a "ahora", como las guarda la BD.
AHORA = datetime.now().replace(microsecond=0)
def dias(n):
    return AHORA + timedelta(days=n)


@pytest.fixture(name="escenario")
def fixture_escenario(session):
    """
    Un programa con una materia, un alumno cursandola y un profesor a cargo,
    mas un periodo de inscripcion, una instancia de cursado y una mesa de examen.
    """
    prog = Programa(nombre="Analista Programador", tipo=TipoPrograma.CARRERA,
                    area=AreaPrograma.INFORMATICA, duracion_semestres=4, activo=True)
    session.add(prog); session.commit(); session.refresh(prog)

    from decimal import Decimal
    pol = PoliticaCalificacion(nombre="Base 100", nota_maxima=Decimal("100"),
                               umbral_aprobacion=Decimal("60"), activo=True)
    session.add(pol); session.commit(); session.refresh(pol)

    materia = Materia(programa_id=prog.id, nombre="Programacion 1", codigo="P1",
                      semestre=1, creditos=10, politica_id=pol.id, activo=True)
    session.add(materia); session.commit(); session.refresh(materia)

    # Usuarios y perfiles
    u_al = Usuario(google_id="g_al", email="al@ctcsalto.edu.uy", nombre="Ana",
                   apellido="Alumna", rol=RolUsuario.ESTUDIANTE, activo=True)
    u_doc = Usuario(google_id="g_doc", email="doc@ctcsalto.edu.uy", nombre="Beto",
                    apellido="Docente", rol=RolUsuario.DOCENTE, activo=True)
    u_adm = Usuario(google_id="g_adm", email="adm@ctcsalto.edu.uy", nombre="Caro",
                    apellido="Admin", rol=RolUsuario.ADMINISTRATIVO, activo=True)
    session.add_all([u_al, u_doc, u_adm]); session.commit()
    for u in (u_al, u_doc, u_adm): session.refresh(u)

    alumno = Alumno(usuario_id=u_al.id)
    profesor = Profesor(usuario_id=u_doc.id)
    session.add_all([alumno, profesor]); session.commit()
    session.refresh(alumno); session.refresh(profesor)

    session.add(InscripcionPrograma(alumno_id=alumno.id, programa_id=prog.id,
                                    anio_ingreso=2026, estado=EstadoInscripcionPrograma.ACTIVA))

    # Periodo de inscripcion: abre en +5, cierra en +20
    session.add(PeriodoInscripcionMateria(programa_id=prog.id, anio_lectivo=2026,
                fecha_inicio=dias(5), fecha_fin=dias(20), habilitado=True))

    # Instancia de cursado: inicia en +10, termina en +100
    ic = InstanciaCursado(materia_id=materia.id, anio_lectivo=2026,
                          fecha_inicio=dias(10), fecha_fin=dias(100),
                          estado=EstadoInstanciaCursado.EN_CURSO)
    session.add(ic); session.commit(); session.refresh(ic)

    session.add(InscripcionMateria(alumno_id=alumno.id, instancia_cursado_id=ic.id,
                                   estado=EstadoInscripcionMateria.CURSANDO))

    # Mesa de examen: se rinde en +30
    ie = InstanciaExamen(materia_id=materia.id, nombre="Examen Feb",
                         fecha_inicio_inscripcion=dias(1), fecha_fin_inscripcion=dias(3),
                         fecha_examen=dias(30), estado=EstadoInstanciaExamen.PROGRAMADO,
                         habilitado=True)
    session.add(ie); session.commit(); session.refresh(ie)

    session.add(DocenteMateria(profesor_id=profesor.id, instancia_cursado_id=ic.id,
                               rol_docente=RolDocente.TITULAR))
    session.add(DocenteInstanciaExamen(profesor_id=profesor.id, instancia_examen_id=ie.id))
    session.commit()

    return {"alumno_user": u_al, "docente_user": u_doc, "admin_user": u_adm,
            "materia": materia, "instancia_cursado": ic, "instancia_examen": ie}


class TestProximosEventos:

    def test_alumno_ve_sus_eventos_ordenados(self, session, escenario):
        eventos = ProximosEventosService().get_eventos(escenario["alumno_user"], session)
        # apertura(+5), cierre(+20), inicio dictado(+10), fin dictado(+100)
        tipos = [e.tipo for e in eventos]
        assert TipoEventoProximo.APERTURA_INSCRIPCION_MATERIA in tipos
        assert TipoEventoProximo.INICIO_DICTADO in tipos
        assert TipoEventoProximo.FIN_DICTADO in tipos
        # Orden ascendente estricto por fecha
        fechas = [e.fecha for e in eventos]
        assert fechas == sorted(fechas)

    def test_filtro_temporal_excluye_pasado(self, session, escenario):
        # La mesa de examen ya paso su ventana de inscripcion (+1/+3), pero el
        # examen (+30) sigue vigente. Como el alumno no esta inscripto al examen
        # ni en A_EXAMEN, no deberia ver la fecha de examen; sí el dictado futuro.
        eventos = ProximosEventosService().get_eventos(escenario["alumno_user"], session)
        assert all(e.fecha >= datetime.now().replace(tzinfo=None) - timedelta(seconds=5) for e in eventos)

    def test_ventana_days(self, session, escenario):
        # Con days=15 solo entran apertura(+5) e inicio dictado(+10); no el cierre(+20)
        eventos = ProximosEventosService().get_eventos(escenario["alumno_user"], session, days=15)
        assert all(e.fecha <= datetime.now().replace(tzinfo=None) + timedelta(days=15, seconds=5) for e in eventos)
        assert TipoEventoProximo.FIN_DICTADO not in [e.tipo for e in eventos]

    def test_limit(self, session, escenario):
        eventos = ProximosEventosService().get_eventos(escenario["alumno_user"], session, limit=2)
        assert len(eventos) == 2

    def test_profesor_ve_dictado_y_mesa(self, session, escenario):
        eventos = ProximosEventosService().get_eventos(escenario["docente_user"], session)
        tipos = {e.tipo for e in eventos}
        assert TipoEventoProximo.INICIO_DICTADO in tipos
        assert TipoEventoProximo.FIN_DICTADO in tipos
        assert TipoEventoProximo.FECHA_EXAMEN in tipos
        # El profesor NO ve periodos de inscripcion a materia (no le corresponden)
        assert TipoEventoProximo.APERTURA_INSCRIPCION_MATERIA not in tipos

    def test_admin_ve_todo_global(self, session, escenario):
        eventos = ProximosEventosService().get_eventos(escenario["admin_user"], session)
        tipos = {e.tipo for e in eventos}
        # El admin ve las 6 fuentes con fecha futura del escenario:
        # apertura/cierre de inscripcion a materia, apertura/cierre de inscripcion
        # a examen, fecha de examen, inicio y fin de dictado.
        assert TipoEventoProximo.APERTURA_INSCRIPCION_MATERIA in tipos
        assert TipoEventoProximo.CIERRE_INSCRIPCION_MATERIA in tipos
        assert TipoEventoProximo.APERTURA_INSCRIPCION_EXAMEN in tipos
        assert TipoEventoProximo.CIERRE_INSCRIPCION_EXAMEN in tipos
        assert TipoEventoProximo.FECHA_EXAMEN in tipos
        assert TipoEventoProximo.INICIO_DICTADO in tipos
        assert TipoEventoProximo.FIN_DICTADO in tipos

    def test_admin_no_filtra_por_asignacion(self, session, escenario):
        # Un segundo programa sin alumnos ni docentes asignados igual aparece
        # para el admin, porque su vista es institucional.
        from decimal import Decimal
        prog2 = Programa(nombre="Tecnico en Redes", tipo=TipoPrograma.CARRERA,
                         area=AreaPrograma.INFORMATICA, duracion_semestres=4, activo=True)
        session.add(prog2); session.commit(); session.refresh(prog2)
        session.add(PeriodoInscripcionMateria(programa_id=prog2.id, anio_lectivo=2026,
                    fecha_inicio=dias(7), fecha_fin=dias(21), habilitado=True))
        session.commit()

        eventos = ProximosEventosService().get_eventos(escenario["admin_user"], session, limit=100)
        programas = {e.programa_nombre for e in eventos if e.programa_nombre}
        assert "Tecnico en Redes" in programas
        assert "Analista Programador" in programas

    def test_alumno_no_ve_periodos_de_otro_programa(self, session, escenario):
        # Un periodo de un programa en el que el alumno NO esta inscripto no debe
        # aparecer en su listado.
        prog2 = Programa(nombre="Tecnico en Redes", tipo=TipoPrograma.CARRERA,
                         area=AreaPrograma.INFORMATICA, duracion_semestres=4, activo=True)
        session.add(prog2); session.commit(); session.refresh(prog2)
        session.add(PeriodoInscripcionMateria(programa_id=prog2.id, anio_lectivo=2026,
                    fecha_inicio=dias(7), fecha_fin=dias(21), habilitado=True))
        session.commit()

        eventos = ProximosEventosService().get_eventos(escenario["alumno_user"], session, limit=100)
        programas = {e.programa_nombre for e in eventos if e.programa_nombre}
        assert "Tecnico en Redes" not in programas

    def test_alumno_inscripto_a_examen_ve_fecha(self, session, escenario):
        # Inscribir al alumno al examen -> debe aparecer la FECHA_EXAMEN
        ic = escenario["instancia_cursado"]
        alumno_insc = session.exec(
            __import__("sqlmodel").select(InscripcionMateria).where(
                InscripcionMateria.instancia_cursado_id == ic.id)
        ).first()
        ie = escenario["instancia_examen"]
        session.add(InscripcionExamen(inscripcion_materia_id=alumno_insc.id,
                    instancia_examen_id=ie.id, estado=EstadoInscripcionExamen.INSCRIPTO))
        session.commit()

        eventos = ProximosEventosService().get_eventos(escenario["alumno_user"], session)
        assert TipoEventoProximo.FECHA_EXAMEN in [e.tipo for e in eventos]

    def test_respuesta_vacia_sin_error(self, session):
        # Usuario sin perfil ni datos: lista vacia, no error
        u = Usuario(google_id="g_x", email="x@ctcsalto.edu.uy", nombre="Sin",
                    apellido="Datos", rol=RolUsuario.ESTUDIANTE, activo=True)
        session.add(u); session.commit(); session.refresh(u)
        eventos = ProximosEventosService().get_eventos(u, session)
        assert eventos == []
