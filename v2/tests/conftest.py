"""
Fixtures compartidas para los tests del portal academico v2.
Usa SQLite en memoria para no tocar la base de datos real.
"""
import os
import pytest
from decimal import Decimal
from datetime import datetime, timedelta

# Setear variable de entorno ANTES de importar cualquier modulo del proyecto
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("TIME_ZONE", "America/Montevideo")

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

# Importar todos los modelos para que SQLModel los registre
from v2.models.usuario import Usuario
from v2.models.alumno import Alumno
from v2.models.profesor import Profesor
from v2.models.administrativo import Administrativo
from v2.models.programa import Programa
from v2.models.materia import Materia
from v2.models.politica_calificacion import PoliticaCalificacion
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
from v2.models.calificacion import Calificacion
from v2.models.previatura import Previatura
from v2.models.excepcion_previatura import ExcepcionPreviatura
from v2.models.mesa_examen import MesaExamen
from v2.models.docente_materia import DocenteMateria
from v2.models.periodo_inscripcion_materia import PeriodoInscripcionMateria
from v2.models.enums import (
    RolUsuario, TipoPrograma, AreaPrograma, TipoNota,
    EstadoInstanciaCursado, EstadoInscripcionMateria,
    TipoPreviatura, RolDocente,
)
from v2.auth.security import create_v2_token


# ── Engine y Session ──────────────────────────────────────────────────────────

@pytest.fixture(name="engine")
def fixture_engine():
    """Engine SQLite en memoria."""
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
    """Session de base de datos para cada test."""
    with Session(engine) as session:
        yield session


# ── Datos base ────────────────────────────────────────────────────────────────

@pytest.fixture(name="politica_base100")
def fixture_politica_base100(session):
    """Politica de calificacion base 100 (carrera tipica)."""
    politica = PoliticaCalificacion(
        nombre="Base 100 - Test",
        nota_maxima=Decimal("100"),
        tipo_nota=TipoNota.NUMERICA,
        umbral_aprobacion=Decimal("60"),
        umbral_examen=Decimal("25"),
        umbral_exoneracion=Decimal("86"),
        activo=True,
    )
    session.add(politica)
    session.commit()
    session.refresh(politica)
    return politica


@pytest.fixture(name="politica_curso_corto")
def fixture_politica_curso_corto(session):
    """Politica sin examen (curso corto): solo aprobacion directa."""
    politica = PoliticaCalificacion(
        nombre="Curso Corto - Test",
        nota_maxima=Decimal("100"),
        tipo_nota=TipoNota.NUMERICA,
        umbral_aprobacion=Decimal("60"),
        umbral_examen=None,
        umbral_exoneracion=None,
        activo=True,
    )
    session.add(politica)
    session.commit()
    session.refresh(politica)
    return politica


@pytest.fixture(name="programa")
def fixture_programa(session):
    """Programa de test: Analista Programador."""
    prog = Programa(
        nombre="Analista Programador Test",
        tipo=TipoPrograma.CARRERA,
        area=AreaPrograma.INFORMATICA,
        duracion_semestres=4,
        creditos_requeridos=200,
        activo=True,
    )
    session.add(prog)
    session.commit()
    session.refresh(prog)
    return prog


@pytest.fixture(name="materias_con_previaturas")
def fixture_materias_con_previaturas(session, programa, politica_base100):
    """
    3 materias con cadena de previaturas:
    Prog1 (sem1) → Prog2 (sem2) → Prog3 (sem3)
    """
    m1 = Materia(
        programa_id=programa.id, nombre="Programacion 1", codigo="P1_T",
        semestre=1, creditos=10, politica_id=politica_base100.id, activo=True,
    )
    m2 = Materia(
        programa_id=programa.id, nombre="Programacion 2", codigo="P2_T",
        semestre=2, creditos=10, politica_id=politica_base100.id, activo=True,
    )
    m3 = Materia(
        programa_id=programa.id, nombre="Programacion 3", codigo="P3_T",
        semestre=3, creditos=10, politica_id=politica_base100.id, activo=True,
    )
    session.add_all([m1, m2, m3])
    session.commit()
    session.refresh(m1)
    session.refresh(m2)
    session.refresh(m3)

    # Previaturas: P2 requiere P1 aprobada, P3 requiere P2 aprobada
    prev1 = Previatura(
        materia_id=m2.id, materia_previa_id=m1.id,
        tipo_requerido=TipoPreviatura.APROBADA,
    )
    prev2 = Previatura(
        materia_id=m3.id, materia_previa_id=m2.id,
        tipo_requerido=TipoPreviatura.APROBADA,
    )
    session.add_all([prev1, prev2])
    session.commit()

    return {"prog1": m1, "prog2": m2, "prog3": m3, "prev_p2": prev1, "prev_p3": prev2}


@pytest.fixture(name="usuario_estudiante")
def fixture_usuario_estudiante(session):
    """Usuario con rol ESTUDIANTE."""
    user = Usuario(
        google_id="google_est_001",
        email="estudiante.test@ctcsalto.edu.uy",
        nombre="Juan",
        apellido="Perez",
        rol=RolUsuario.ESTUDIANTE,
        activo=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="usuario_docente")
def fixture_usuario_docente(session):
    """Usuario con rol DOCENTE."""
    user = Usuario(
        google_id="google_doc_001",
        email="docente.test@ctcsalto.edu.uy",
        nombre="Maria",
        apellido="Garcia",
        rol=RolUsuario.DOCENTE,
        activo=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="usuario_admin")
def fixture_usuario_admin(session):
    """Usuario con rol ADMINISTRATIVO."""
    user = Usuario(
        google_id="google_adm_001",
        email="admin.test@ctcsalto.edu.uy",
        nombre="Carlos",
        apellido="Lopez",
        rol=RolUsuario.ADMINISTRATIVO,
        activo=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# ── Perfiles academicos ───────────────────────────────────────────────────────
# Las entidades academicas referencian alumno.id / profesor.id, no usuario.id.
# En produccion estos perfiles los crea _auto_crear_perfil() al dar de alta al
# usuario; en los tests los montamos explicitamente.

@pytest.fixture(name="alumno")
def fixture_alumno(session, usuario_estudiante):
    """Perfil de alumno del usuario estudiante."""
    alumno = Alumno(usuario_id=usuario_estudiante.id)
    session.add(alumno)
    session.commit()
    session.refresh(alumno)
    return alumno


@pytest.fixture(name="otro_alumno")
def fixture_otro_alumno(session):
    """
    Segundo alumno, para los tests que verifican que no se puede acceder a la
    inscripcion de otro. Tiene su propio usuario: usar el id de un usuario
    cualquiera no sirve, porque los ids de usuario y de alumno son secuencias
    distintas y pueden coincidir por casualidad.
    """
    user = Usuario(
        google_id="google_est_002",
        email="otro.estudiante@ctcsalto.edu.uy",
        nombre="Ana",
        apellido="Silva",
        rol=RolUsuario.ESTUDIANTE,
        activo=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    alumno = Alumno(usuario_id=user.id)
    session.add(alumno)
    session.commit()
    session.refresh(alumno)
    return alumno


@pytest.fixture(name="profesor")
def fixture_profesor(session, usuario_docente):
    """Perfil de profesor del usuario docente."""
    profesor = Profesor(usuario_id=usuario_docente.id)
    session.add(profesor)
    session.commit()
    session.refresh(profesor)
    return profesor


@pytest.fixture(name="otro_profesor")
def fixture_otro_profesor(session):
    """Segundo profesor, para los tests de asignaciones ajenas."""
    user = Usuario(
        google_id="google_doc_002",
        email="otro.docente@ctcsalto.edu.uy",
        nombre="Luis",
        apellido="Gomez",
        rol=RolUsuario.DOCENTE,
        activo=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    profesor = Profesor(usuario_id=user.id)
    session.add(profesor)
    session.commit()
    session.refresh(profesor)
    return profesor


@pytest.fixture(name="usuario_inactivo")
def fixture_usuario_inactivo(session):
    """Usuario desactivado."""
    user = Usuario(
        google_id="google_inac_001",
        email="inactivo.test@ctcsalto.edu.uy",
        nombre="Pedro",
        apellido="Ruiz",
        rol=RolUsuario.ESTUDIANTE,
        activo=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# ── Instancia de cursado con evaluaciones ─────────────────────────────────────

@pytest.fixture(name="instancia_cursado_completa")
def fixture_instancia_cursado_completa(session, materias_con_previaturas, politica_base100):
    """
    Instancia de cursado para Prog1 con 2 evaluaciones (parcial1=30, parcial2=70).
    faltas_maximas=5.
    """
    m1 = materias_con_previaturas["prog1"]
    ic = InstanciaCursado(
        materia_id=m1.id,
        anio_lectivo=2026,
        estado=EstadoInstanciaCursado.EN_CURSO,
        faltas_maximas=5,
    )
    session.add(ic)
    session.commit()
    session.refresh(ic)

    ev1 = MateriaInstanciaEvaluacion(
        instancia_cursado_id=ic.id, nombre="Parcial 1",
        peso_maximo=Decimal("30"), orden=1, es_grupal=False, activo=True,
    )
    ev2 = MateriaInstanciaEvaluacion(
        instancia_cursado_id=ic.id, nombre="Parcial 2",
        peso_maximo=Decimal("70"), orden=2, es_grupal=False, activo=True,
    )
    session.add_all([ev1, ev2])
    session.commit()
    session.refresh(ev1)
    session.refresh(ev2)

    return {"instancia": ic, "eval1": ev1, "eval2": ev2, "materia": m1}


@pytest.fixture(name="inscripcion_cursando")
def fixture_inscripcion_cursando(session, alumno, instancia_cursado_completa):
    """Inscripcion en estado CURSANDO con snapshots."""
    ic = instancia_cursado_completa["instancia"]
    ev1 = instancia_cursado_completa["eval1"]
    ev2 = instancia_cursado_completa["eval2"]

    snapshot_politica = {
        "nota_maxima": 100.0,
        "tipo_nota": "numerica",
        "umbral_aprobacion": 60.0,
        "umbral_examen": 25.0,
        "umbral_exoneracion": 86.0,
    }
    snapshot_instancias = [
        {"id": ev1.id, "nombre": "Parcial 1", "peso_maximo": 30.0, "orden": 1, "es_grupal": False},
        {"id": ev2.id, "nombre": "Parcial 2", "peso_maximo": 70.0, "orden": 2, "es_grupal": False},
    ]

    insc = InscripcionMateria(
        alumno_id=alumno.id,
        instancia_cursado_id=ic.id,
        estado=EstadoInscripcionMateria.CURSANDO,
        snapshot_politica=snapshot_politica,
        snapshot_instancias=snapshot_instancias,
    )
    session.add(insc)
    session.commit()
    session.refresh(insc)
    return insc


@pytest.fixture(name="asignacion_docente")
def fixture_asignacion_docente(session, profesor, instancia_cursado_completa):
    """Asigna el docente a la instancia de cursado."""
    dm = DocenteMateria(
        profesor_id=profesor.id,
        instancia_cursado_id=instancia_cursado_completa["instancia"].id,
        rol_docente=RolDocente.TITULAR,
    )
    session.add(dm)
    session.commit()
    session.refresh(dm)
    return dm


# ── Helpers de tokens ─────────────────────────────────────────────────────────

def make_token(usuario):
    """Genera un JWT v2 para un usuario."""
    return create_v2_token(
        email=usuario.email,
        usuario_id=usuario.id,
        rol=usuario.rol.value,
    )


def make_headers(usuario):
    """Headers con Authorization Bearer para un usuario."""
    return {"Authorization": f"Bearer {make_token(usuario)}"}


# ── Periodo de inscripcion ────────────────────────────────────────────────────

@pytest.fixture(name="periodo_activo")
def fixture_periodo_activo(session, programa):
    """Periodo de inscripcion activo (ahora esta dentro del rango)."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo"))
    ahora = datetime.now(tz)

    periodo = PeriodoInscripcionMateria(
        programa_id=programa.id,
        anio_lectivo=2026,
        fecha_inicio=ahora - timedelta(days=30),
        fecha_fin=ahora + timedelta(days=30),
        habilitado=True,
    )
    session.add(periodo)
    session.commit()
    session.refresh(periodo)
    return periodo


@pytest.fixture(name="periodo_cerrado")
def fixture_periodo_cerrado(session, programa):
    """Periodo de inscripcion que ya cerro."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo"))
    ahora = datetime.now(tz)

    periodo = PeriodoInscripcionMateria(
        programa_id=programa.id,
        anio_lectivo=2026,
        fecha_inicio=ahora - timedelta(days=60),
        fecha_fin=ahora - timedelta(days=30),
        habilitado=True,
    )
    session.add(periodo)
    session.commit()
    session.refresh(periodo)
    return periodo
