"""
El importador de la planilla de carga inicial (v2/scripts/importar_planilla_migracion.py).

Una planilla chica con los casos de la real: una carrera con dos planes y el
programa que ya existia sin plan, un curso independiente, un alumno en una
carrera y un curso, un docente que ya tenia cuenta, y un historial con
materias de un plan viejo, un taller ".5" y cursadas de este año.
"""
from decimal import Decimal

import pytest
from openpyxl import Workbook
from sqlmodel import select

from v2.models.alumno import Alumno
from v2.models.docente_materia import DocenteMateria
from v2.models.enums import (
    EstadoInscripcionMateria, EstadoInscripcionPrograma, EstadoInstanciaCursado,
    RolUsuario, TipoNota, TipoPrograma,
)
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.materia import Materia
from v2.models.politica_calificacion import PoliticaCalificacion
from v2.models.politica_examen import PoliticaExamen
from v2.models.previatura import Previatura
from v2.models.profesor import Profesor
from v2.models.programa import Programa
from v2.models.usuario import Usuario
from v2.scripts.importar_planilla_migracion import EXAMEN_CURSO, Importador
from v2.scripts.validar_planilla_migracion import HOJAS, Validador

AP = "Analista Programador"
ANIO = 2026


def _hoja(wb, nombre, encabezado, filas):
    ws = wb.create_sheet(nombre)
    ws.append(["nota"])
    ws.append(encabezado)
    for fila in filas:
        ws.append(list(fila))


@pytest.fixture(name="planilla")
def fixture_planilla(tmp_path):
    wb = Workbook()
    wb.remove(wb.active)
    _hoja(wb, HOJAS["alumnos"],
          ["DOCUMENTO*", "Apellido*", "Nombre*", "Email institucional", "Email personal", "Telefono",
           "Fecha nacimiento", "Programa*", "Año de ingreso*", "Estado en la carrera*", "Observaciones",
           "Otro Programa*", "Estado en la carrera*"],
          [("4.123.456-7", "Perez", "Ana", "Ana@ctcsalto.edu.uy", "ana@gmail.com", "099 123 456",
            "22/07/2001", AP, 2021, "ACTIVA", None, "Excel", "ACTIVA")])
    _hoja(wb, HOJAS["docentes"],
          ["DOCUMENTO*", "Apellido*", "Nombre*", "Email institucional", "Email personal", "Telefono",
           "¿Sigue activo?*", "Observaciones"],
          [("30000001", "Gomez", "Juan", "doc@ctcsalto.edu.uy", None, None, "SI", None)])
    _hoja(wb, HOJAS["plan"],
          ["Programa*", "Codigo", "Nombre*", "Semestre*", "Creditos*", "¿Se sigue dictando?*",
           "Observaciones", "Plan"],
          [(AP, "PROG1", "Programacion 1", 1, 1, "NO", "Área Informática", 2020),
           (AP, "PROG1", "Programacion 1", 1, 1, "SI", "Área Informática", 2022),
           (AP, "PROG2", "Programacion 2", 2, 1, "SI", "Área Informática", 2022),
           (AP, "T.X", "Taller X", 1.5, 1, "SI", "Área Informática", 2022),
           (AP, "INT", "Proyecto Integrador Final", 5, 1, "SI", "Área Informática", 2022),
           ("Excel", "EXC", "Excel", "NC", "--", "SI", "Curso Corto - Área Administración", 2025)])
    _hoja(wb, HOJAS["previaturas"],
          ["Programa*", "Materia*", "Materia previa*", "Tipo*", "Observaciones"],
          [(AP, "Programacion 2", "Programacion 1", "APROBADA", None)])
    _hoja(wb, HOJAS["historial"],
          ["DOCUMENTO*", "Programa", "Materia*", "Estado*", "Nota", "Año", "Semestre", "Observaciones"],
          [("41234567", AP, "Programacion 1", "APROBADA", 80, 2021, 1, "Plan 2020"),
           ("41234567", AP, "Taller X", "EXONERADA", 90, 2022, 1.5, None),
           ("41234567", AP, "PROG2", "CURSANDO", None, ANIO, 2, None),
           ("41234567", "Excel", "Excel", "CURSANDO", None, ANIO, None, None)])
    _hoja(wb, HOJAS["dictado"],
          ["Programa*", "Materia*", "Año*", "Semestre*", "DOCUMENTO del docente*", "Rol*", None, "Rol*",
           "Horario", "Salon", "Cupo maximo", "Observaciones"],
          [(AP, "Programacion 2", 2022, 2, "30000001", "TITULAR", None, None, "Lunes 19-22", "3", 20, None),
           (AP, "Taller X", 2022, 1, "30000001", "TITULAR", None, None, None, None, None, None)])
    ruta = tmp_path / "carga.xlsx"
    wb.save(ruta)
    return str(ruta)


@pytest.fixture(name="base")
def fixture_base(session):
    """Lo que ya hay en develop: politicas, el programa sin plan con PROG1 y una cuenta de Google."""
    carrera = PoliticaCalificacion(nombre="Base 100 - Carrera AP", nota_maxima=Decimal("100"),
                                   tipo_nota=TipoNota.NUMERICA, umbral_aprobacion=Decimal("70"),
                                   umbral_examen=Decimal("70"), umbral_exoneracion=Decimal("86"))
    curso = PoliticaCalificacion(nombre="Base 100 - Curso Corto", nota_maxima=Decimal("100"),
                                 tipo_nota=TipoNota.NUMERICA, umbral_aprobacion=Decimal("70"))
    examen = PoliticaExamen(nombre="Examen estandar base 100", nota_maxima=Decimal("100"),
                            umbral_aprobacion=Decimal("70"), max_oportunidades=5)
    programa = Programa(nombre=AP, tipo=TipoPrograma.CARRERA, duracion_semestres=6)
    session.add_all([carrera, curso, examen, programa])
    session.flush()
    prog1 = Materia(programa_id=programa.id, nombre="Programacion 1", codigo="PROG1", semestre=1,
                    creditos=10, politica_id=carrera.id)
    docente = Usuario(nombre="Juan", apellido="Gomez", email="doc@ctcsalto.edu.uy", rol=RolUsuario.DOCENTE,
                      google_id="g-123")
    session.add_all([prog1, docente])
    session.commit()
    return {"programa": programa, "prog1": prog1, "docente": docente}


def importar(ruta, session, anio=ANIO):
    validador = Validador(ruta)
    errores = [str(p) for p in validador.correr() if p.nivel == "ERROR"]
    assert errores == []
    importador = Importador(validador, session)
    importador.anio_actual = anio
    importador.correr()
    session.commit()
    return importador


def uno(session, modelo, *condiciones):
    return session.exec(select(modelo).where(*condiciones)).one()


class TestProgramasYMaterias:
    def test_cada_plan_un_programa_y_el_viejo_sin_plan_es_el_vigente(self, planilla, session, base):
        importar(planilla, session)
        vigente = uno(session, Programa, Programa.nombre == f"{AP} (Plan 2022)")
        viejo = uno(session, Programa, Programa.nombre == f"{AP} (Plan 2020)")
        assert vigente.id == base["programa"].id
        assert vigente.activo and not viejo.activo
        assert session.exec(select(Programa).where(Programa.nombre == AP)).first() is None

    def test_reusa_la_materia_por_codigo_y_la_planilla_manda(self, planilla, session, base):
        importar(planilla, session)
        prog1 = session.get(Materia, base["prog1"].id)
        assert prog1.codigo == "PROG1" and prog1.creditos == 1
        viejo = uno(session, Materia, Materia.codigo == "PROG1-2020")
        assert not viejo.activo

    def test_taller_punto_cinco_y_curso(self, planilla, session, base):
        importar(planilla, session)
        assert uno(session, Materia, Materia.codigo == "T.X").semestre == 1
        excel = uno(session, Materia, Materia.codigo == "EXC")
        assert (excel.semestre, excel.creditos) == (1, 0)
        assert session.get(PoliticaCalificacion, excel.politica_id).nombre == "Base 100 - Curso Corto"
        assert session.get(PoliticaExamen, excel.politica_examen_id).max_oportunidades == 2
        assert uno(session, Programa, Programa.nombre == "Excel").tipo == TipoPrograma.CURSO_CORTO

    def test_el_integrador_requiere_todo_el_plan(self, planilla, session, base):
        importar(planilla, session)
        integrador = uno(session, Materia, Materia.codigo == "INT")
        previas = {session.get(Materia, p.materia_previa_id).codigo for p in
                   session.exec(select(Previatura).where(Previatura.materia_id == integrador.id)).all()}
        assert previas == {"PROG1", "PROG2", "T.X"}


class TestPersonas:
    def test_alumno_con_carrera_y_curso(self, planilla, session, base):
        importar(planilla, session)
        ana = uno(session, Usuario, Usuario.documento == "41234567")
        assert ana.email == "ana@ctcsalto.edu.uy"
        assert ana.telefono == "099123456"
        assert str(ana.fecha_nacimiento) == "2001-07-22"
        alumno = uno(session, Alumno, Alumno.usuario_id == ana.id)
        inscripciones = {session.get(Programa, i.programa_id).nombre: i for i in
                         session.exec(select(InscripcionPrograma).where(InscripcionPrograma.alumno_id == alumno.id))}
        assert set(inscripciones) == {f"{AP} (Plan 2022)", "Excel"}
        assert inscripciones[f"{AP} (Plan 2022)"].anio_ingreso == 2021
        # El segundo curso no trae año: el de su primera materia en el historial
        assert inscripciones["Excel"].anio_ingreso == ANIO
        assert inscripciones["Excel"].estado == EstadoInscripcionPrograma.ACTIVA

    def test_docente_con_cuenta_se_completa_sin_duplicar(self, planilla, session, base):
        importar(planilla, session)
        docente = uno(session, Usuario, Usuario.email == "doc@ctcsalto.edu.uy")
        assert docente.id == base["docente"].id
        assert docente.documento == "30000001" and docente.google_id == "g-123"
        assert uno(session, Profesor, Profesor.usuario_id == docente.id).activo


class TestHistorial:
    def _inscripcion(self, session, codigo, anio):
        materia = uno(session, Materia, Materia.codigo == codigo)
        cursada = uno(session, InstanciaCursado, InstanciaCursado.materia_id == materia.id,
                      InstanciaCursado.anio_lectivo == anio)
        return cursada, uno(session, InscripcionMateria, InscripcionMateria.instancia_cursado_id == cursada.id)

    def test_materia_de_plan_viejo_aprobada(self, planilla, session, base):
        importar(planilla, session)
        cursada, insc = self._inscripcion(session, "PROG1-2020", 2021)
        assert cursada.estado == EstadoInstanciaCursado.FINALIZADA
        assert insc.estado == EstadoInscripcionMateria.APROBADO
        assert insc.nota_final == Decimal("80") and insc.creditos_obtenidos == 1
        # Sin fecha_cierre: la escolaridad no la cuenta dos veces (ya esta en el legajo)
        assert insc.fecha_cierre is None

    def test_cursando_queda_calificable_con_su_docente(self, planilla, session, base):
        importar(planilla, session)
        cursada, insc = self._inscripcion(session, "PROG2", ANIO)
        assert cursada.estado == EstadoInstanciaCursado.EN_CURSO
        assert (cursada.horario, cursada.salon, cursada.cupo_maximo) == ("Lunes 19-22", "3", 20)
        assert insc.estado == EstadoInscripcionMateria.CURSANDO
        assert insc.snapshot_politica["umbral_exoneracion"] == 86.0
        asignacion = uno(session, DocenteMateria, DocenteMateria.instancia_cursado_id == cursada.id)
        assert session.get(Profesor, asignacion.profesor_id).usuario_id == base["docente"].id

    def test_sin_cursada_este_anio_no_se_crea(self, planilla, session, base):
        importador = importar(planilla, session)
        taller = uno(session, Materia, Materia.codigo == "T.X")
        anios = {c.anio_lectivo for c in
                 session.exec(select(InstanciaCursado).where(InstanciaCursado.materia_id == taller.id))}
        assert anios == {2022}
        assert any("sin alumnos cursando" in n for n in importador.notas)


def test_correr_dos_veces_no_duplica(planilla, session, base):
    importar(planilla, session)
    antes = {m.__name__: len(session.exec(select(m)).all()) for m in
             (Programa, Materia, Previatura, Usuario, Alumno, Profesor, InscripcionPrograma,
              InstanciaCursado, InscripcionMateria, DocenteMateria, PoliticaExamen)}
    segunda = importar(planilla, session)
    despues = {m.__name__: len(session.exec(select(m)).all()) for m in
               (Programa, Materia, Previatura, Usuario, Alumno, Profesor, InscripcionPrograma,
                InstanciaCursado, InscripcionMateria, DocenteMateria, PoliticaExamen)}
    assert antes == despues
    assert not any("nuevos" in k for k in segunda.cuenta), segunda.cuenta
    assert uno(session, PoliticaExamen, PoliticaExamen.nombre == EXAMEN_CURSO).max_oportunidades == 2
