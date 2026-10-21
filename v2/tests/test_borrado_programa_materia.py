"""
Guards de borrado de programas y materias.

El de materias consultaba `InscripcionMateria.materia_id`, columna que dejo de
existir cuando las inscripciones pasaron a colgar de instancia_cursado: el
endpoint tiraba AttributeError (500) siempre, hubiera o no inscripciones. El de
programas solo miraba materias, asi que un programa con alumnos inscriptos
fallaba con una violacion de foreign key en vez de un mensaje.
"""
import pytest
from decimal import Decimal
from sqlmodel import select

from v2.models.materia import Materia
from v2.models.programa import Programa
from v2.models.previatura import Previatura
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.periodo_inscripcion_materia import PeriodoInscripcionMateria
from v2.models.enums import (
    EstadoInscripcionMateria, EstadoInstanciaCursado,
    EstadoInscripcionPrograma, TipoPreviatura,
)
from v2.services.materia_service import MateriaService
from v2.services.programa_service import ProgramaService

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os


def tz():
    return ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo"))


@pytest.fixture(name="materia_suelta")
def fixture_materia_suelta(session, programa, politica_base100):
    """Materia sin instancias, sin inscripciones y sin previaturas."""
    m = Materia(
        programa_id=programa.id, nombre="Materia Suelta", codigo="MS1",
        semestre=1, creditos=10, politica_id=politica_base100.id, activo=True,
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


class TestBorradoDeMateria:

    def test_se_puede_borrar_una_materia_sin_nada_colgando(
        self, session, materia_suelta
    ):
        """Antes esto tiraba AttributeError en vez de borrar."""
        materia_id = materia_suelta.id
        MateriaService().delete(materia_id, session)

        assert session.get(Materia, materia_id) is None

    def test_no_se_borra_una_materia_con_inscripciones(
        self, session, alumno, materia_suelta
    ):
        ic = InstanciaCursado(
            materia_id=materia_suelta.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.EN_CURSO,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        session.add(InscripcionMateria(
            alumno_id=alumno.id, instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.CURSANDO,
        ))
        session.commit()

        with pytest.raises(ValueError, match="inscripciones registradas"):
            MateriaService().delete(materia_suelta.id, session)

        assert session.get(Materia, materia_suelta.id) is not None

    def test_no_se_borra_una_materia_con_instancias_de_cursado(
        self, session, materia_suelta
    ):
        """Sin inscripciones pero con instancias: borrarla dejaria filas colgadas."""
        session.add(InstanciaCursado(
            materia_id=materia_suelta.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.PLANIFICADA,
        ))
        session.commit()

        with pytest.raises(ValueError, match="instancias de cursado"):
            MateriaService().delete(materia_suelta.id, session)

    def test_no_se_borra_una_materia_que_es_previa_de_otra(
        self, session, materia_suelta, materias_con_previaturas
    ):
        """La previatura referencia la materia por los dos lados."""
        session.add(Previatura(
            materia_id=materias_con_previaturas["prog1"].id,
            materia_previa_id=materia_suelta.id,
            tipo_requerido=TipoPreviatura.APROBADA,
        ))
        session.commit()

        with pytest.raises(ValueError, match="previaturas"):
            MateriaService().delete(materia_suelta.id, session)

    def test_no_se_borra_una_materia_con_previaturas_propias(
        self, session, materia_suelta, materias_con_previaturas
    ):
        session.add(Previatura(
            materia_id=materia_suelta.id,
            materia_previa_id=materias_con_previaturas["prog1"].id,
            tipo_requerido=TipoPreviatura.APROBADA,
        ))
        session.commit()

        with pytest.raises(ValueError, match="previaturas"):
            MateriaService().delete(materia_suelta.id, session)

    def test_materia_inexistente(self, session):
        with pytest.raises(ValueError, match="no encontrada"):
            MateriaService().delete(99999, session)


class TestBorradoDePrograma:

    @pytest.fixture(name="programa_vacio")
    def fixture_programa_vacio(self, session):
        from v2.models.enums import TipoPrograma, AreaPrograma
        p = Programa(
            nombre="Programa Vacio", tipo=TipoPrograma.TALLER,
            area=AreaPrograma.GENERAL, duracion_semestres=1,
            creditos_requeridos=10, activo=True,
        )
        session.add(p)
        session.commit()
        session.refresh(p)
        return p

    def test_se_puede_borrar_un_programa_vacio(self, session, programa_vacio):
        programa_id = programa_vacio.id
        ProgramaService().delete(programa_id, session)

        assert session.get(Programa, programa_id) is None

    def test_no_se_borra_un_programa_con_materias(
        self, session, programa, materias_con_previaturas
    ):
        with pytest.raises(ValueError, match="materias asignadas"):
            ProgramaService().delete(programa.id, session)

    def test_no_se_borra_un_programa_con_alumnos_inscriptos(
        self, session, alumno, programa_vacio
    ):
        """Sin materias pero con alumnos: antes era una violacion de FK (500)."""
        session.add(InscripcionPrograma(
            alumno_id=alumno.id, programa_id=programa_vacio.id,
            estado=EstadoInscripcionPrograma.ACTIVA, anio_ingreso=2026,
        ))
        session.commit()

        with pytest.raises(ValueError, match="alumnos inscriptos"):
            ProgramaService().delete(programa_vacio.id, session)

    def test_no_se_borra_un_programa_con_periodos(self, session, programa_vacio):
        ahora = datetime.now(tz())
        session.add(PeriodoInscripcionMateria(
            programa_id=programa_vacio.id, anio_lectivo=2026,
            fecha_inicio=ahora, fecha_fin=ahora + timedelta(days=10),
            habilitado=True,
        ))
        session.commit()

        with pytest.raises(ValueError, match="periodos de inscripcion"):
            ProgramaService().delete(programa_vacio.id, session)

    def test_programa_inexistente(self, session):
        with pytest.raises(ValueError, match="no encontrado"):
            ProgramaService().delete(99999, session)
