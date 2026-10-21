"""
Permisos sobre las instancias de evaluacion.

Las define el docente de la cursada en cada semestre, y bedelia tambien puede.
Antes todas las rutas eran solo para administrativo, asi que el profesor no podia
cargar las evaluaciones de sus propios cursos.

Lo que se verifica aca es el helper de acceso: bedelia entra a cualquier cursada,
el docente solo a las que dicta.
"""
import pytest
from decimal import Decimal

from fastapi import HTTPException

from v2.models.instancia_cursado import InstanciaCursado
from v2.models.docente_materia import DocenteMateria
from v2.models.usuario import UsuarioRead
from v2.models.enums import EstadoInstanciaCursado, RolDocente
from v2.services import get_v2_services
from v2.services.docente_materia_service import DocenteMateriaService
from v2.routes.instancias_evaluacion import _validar_acceso_a_cursada


@pytest.fixture(name="cursadas")
def fixture_cursadas(session, materias_con_previaturas, profesor):
    """Dos cursadas: el profesor dicta la primera, la segunda es ajena."""
    propia = InstanciaCursado(
        materia_id=materias_con_previaturas["prog1"].id, anio_lectivo=2026,
        estado=EstadoInstanciaCursado.EN_CURSO,
    )
    ajena = InstanciaCursado(
        materia_id=materias_con_previaturas["prog2"].id, anio_lectivo=2026,
        estado=EstadoInstanciaCursado.EN_CURSO,
    )
    session.add_all([propia, ajena])
    session.commit()
    session.refresh(propia)
    session.refresh(ajena)

    session.add(DocenteMateria(
        profesor_id=profesor.id,
        instancia_cursado_id=propia.id,
        rol_docente=RolDocente.TITULAR,
    ))
    session.commit()

    return {"propia": propia, "ajena": ajena}


class TestAsignacionDelDocente:
    """El helper del servicio, que traduce usuario -> perfil docente."""

    def test_reconoce_la_cursada_propia(
        self, session, usuario_docente, cursadas
    ):
        assert DocenteMateriaService.docente_asignado_a_cursada(
            usuario_docente.id, cursadas["propia"].id, session
        ) is True

    def test_no_reconoce_una_cursada_ajena(
        self, session, usuario_docente, cursadas
    ):
        assert DocenteMateriaService.docente_asignado_a_cursada(
            usuario_docente.id, cursadas["ajena"].id, session
        ) is False

    def test_un_usuario_sin_perfil_de_profesor(
        self, session, usuario_admin, cursadas
    ):
        """Recibe usuario_id: si esa persona no tiene perfil docente, no dicta nada."""
        assert DocenteMateriaService.docente_asignado_a_cursada(
            usuario_admin.id, cursadas["propia"].id, session
        ) is False


class TestAccesoALaCursada:

    def test_el_docente_entra_a_su_cursada(
        self, session, usuario_docente, cursadas
    ):
        _validar_acceso_a_cursada(
            UsuarioRead.model_validate(usuario_docente),
            cursadas["propia"].id,
            get_v2_services(),
            session,
        )  # no levanta

    def test_el_docente_no_entra_a_una_cursada_ajena(
        self, session, usuario_docente, cursadas
    ):
        """Abrir las rutas al rol docente sin esto dejaria editar materias ajenas."""
        with pytest.raises(HTTPException) as exc:
            _validar_acceso_a_cursada(
                UsuarioRead.model_validate(usuario_docente),
                cursadas["ajena"].id,
                get_v2_services(),
                session,
            )
        assert exc.value.status_code == 403
        assert "No esta asignado" in exc.value.detail

    def test_bedelia_entra_a_cualquier_cursada(
        self, session, usuario_admin, cursadas
    ):
        """El administrativo no necesita asignacion."""
        for cursada in cursadas.values():
            _validar_acceso_a_cursada(
                UsuarioRead.model_validate(usuario_admin),
                cursada.id,
                get_v2_services(),
                session,
            )  # no levanta
