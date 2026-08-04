"""
Excepciones de previatura otorgadas por bedelia.

Regla pedida por administracion, con el ejemplo textual que dieron:

  Un alumno no tiene Programacion 1. Bedelia le permite cursar Programacion 2.
  Si aprueba Programacion 2 pero reprueba Programacion 1, NO puede hacer
  Programacion 3, aunque Programacion 2 sea la previatura de Programacion 3.

Y el complemento: el dia que apruebe Programacion 1 la cadena queda completa y
Programacion 3 se habilita sola, sin que bedelia tenga que volver a intervenir.

La excepcion habilita la inscripcion, no convalida la materia adeudada.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from sqlmodel import select

from v2.models.instancia_cursado import InstanciaCursado
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.periodo_inscripcion_materia import PeriodoInscripcionMateria
from v2.models.previatura import Previatura
from v2.models.excepcion_previatura import (
    ExcepcionPreviatura, ExcepcionPreviaturaCreate,
)
from v2.models.enums import (
    EstadoInscripcionMateria, EstadoInstanciaCursado, TipoPreviatura,
)
from v2.services.inscripcion_service import InscripcionMateriaService
from v2.services.excepcion_previatura_service import ExcepcionPreviaturaService

ANIO = 2026


def tz():
    return ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo"))


@pytest.fixture(name="cadena")
def fixture_cadena(session, programa, materias_con_previaturas):
    """
    Prog1 -> Prog2 -> Prog3, con instancias del anio y periodo abierto.
    Las previaturas ya vienen de la fixture compartida.
    """
    ahora = datetime.now(tz())
    session.add(PeriodoInscripcionMateria(
        programa_id=programa.id, anio_lectivo=ANIO,
        fecha_inicio=ahora - timedelta(days=5),
        fecha_fin=ahora + timedelta(days=5),
        habilitado=True,
    ))
    session.commit()

    instancias = {}
    for clave in ("prog1", "prog2", "prog3"):
        materia = materias_con_previaturas[clave]
        ic = InstanciaCursado(
            materia_id=materia.id, anio_lectivo=ANIO,
            estado=EstadoInstanciaCursado.EN_CURSO,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)
        instancias[clave] = ic

    return {**materias_con_previaturas, "instancias": instancias}


def previatura_de(session, materia, materia_previa):
    return session.exec(
        select(Previatura).where(
            Previatura.materia_id == materia.id,
            Previatura.materia_previa_id == materia_previa.id,
        )
    ).first()


def poner_estado(session, alumno, cadena, clave, estado):
    """Deja al alumno en un estado dado en esa materia."""
    ic = cadena["instancias"][clave]
    insc = session.exec(
        select(InscripcionMateria).where(
            InscripcionMateria.alumno_id == alumno.id,
            InscripcionMateria.instancia_cursado_id == ic.id,
        )
    ).first()
    if insc is None:
        insc = InscripcionMateria(
            alumno_id=alumno.id, instancia_cursado_id=ic.id, estado=estado,
        )
    else:
        insc.estado = estado
    session.add(insc)
    session.commit()
    return insc


def puede_cursar(session, alumno, materia, anio=ANIO):
    cumple, faltantes = InscripcionMateriaService().validar_previaturas(
        alumno.id, materia.id, session, anio_lectivo=anio
    )
    return cumple, faltantes


def otorgar(session, alumno, materia, materia_previa, admin, anio=ANIO):
    prev = previatura_de(session, materia, materia_previa)
    return ExcepcionPreviaturaService().otorgar(
        ExcepcionPreviaturaCreate(
            alumno_id=alumno.id, previatura_id=prev.id,
            anio_lectivo=anio, motivo="Caso excepcional autorizado por direccion",
        ),
        otorgada_por_id=admin.id,
        session=session,
    )


class TestElEjemploDeAdministracion:
    """El escenario textual que planteo administracion, paso a paso."""

    def test_sin_excepcion_no_puede_cursar_prog2(self, session, alumno, cadena):
        cumple, faltantes = puede_cursar(session, alumno, cadena["prog2"])

        assert cumple is False
        assert any("Programacion 1" in f for f in faltantes)

    def test_con_excepcion_puede_cursar_prog2(
        self, session, alumno, usuario_admin, cadena
    ):
        otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)

        cumple, faltantes = puede_cursar(session, alumno, cadena["prog2"])

        assert cumple is True, faltantes

    def test_aprobar_prog2_por_excepcion_NO_habilita_prog3(
        self, session, alumno, usuario_admin, cadena
    ):
        """
        El corazon del pedido. Prog2 aprobada, y aun asi Prog3 bloqueada, porque
        Prog1 sigue reprobada.
        """
        otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)
        poner_estado(session, alumno, cadena, "prog1", EstadoInscripcionMateria.REPROBADO)
        poner_estado(session, alumno, cadena, "prog2", EstadoInscripcionMateria.APROBADO)

        cumple, faltantes = puede_cursar(session, alumno, cadena["prog3"])

        assert cumple is False
        assert any("excepcion" in f for f in faltantes), faltantes

    def test_al_aprobar_prog1_se_habilita_prog3_solo(
        self, session, alumno, usuario_admin, cadena
    ):
        """Saldada la deuda, la cadena queda completa sin intervencion de bedelia."""
        otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)
        poner_estado(session, alumno, cadena, "prog1", EstadoInscripcionMateria.REPROBADO)
        poner_estado(session, alumno, cadena, "prog2", EstadoInscripcionMateria.APROBADO)

        assert puede_cursar(session, alumno, cadena["prog3"])[0] is False

        poner_estado(session, alumno, cadena, "prog1", EstadoInscripcionMateria.APROBADO)

        cumple, faltantes = puede_cursar(session, alumno, cadena["prog3"])
        assert cumple is True, faltantes

    def test_la_cadena_normal_sigue_funcionando(self, session, alumno, cadena):
        """Sin excepciones de por medio, aprobar en orden habilita lo siguiente."""
        poner_estado(session, alumno, cadena, "prog1", EstadoInscripcionMateria.APROBADO)
        assert puede_cursar(session, alumno, cadena["prog2"])[0] is True

        poner_estado(session, alumno, cadena, "prog2", EstadoInscripcionMateria.APROBADO)
        assert puede_cursar(session, alumno, cadena["prog3"])[0] is True


class TestAlcanceDeLaExcepcion:

    def test_solo_vale_para_el_anio_otorgado(
        self, session, alumno, usuario_admin, cadena
    ):
        otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin, anio=ANIO)

        assert puede_cursar(session, alumno, cadena["prog2"], anio=ANIO)[0] is True
        assert puede_cursar(session, alumno, cadena["prog2"], anio=ANIO + 1)[0] is False

    def test_sin_anio_no_se_aplica_ninguna(
        self, session, alumno, usuario_admin, cadena
    ):
        otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)

        cumple, _ = InscripcionMateriaService().validar_previaturas(
            alumno.id, cadena["prog2"].id, session
        )
        assert cumple is False

    def test_solo_vale_para_la_previatura_otorgada(
        self, session, alumno, otro_alumno, usuario_admin, cadena
    ):
        """Es por previatura puntual, no un permiso general del alumno."""
        otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)

        # Prog3 sigue exigiendo Prog2, que no esta aprobada
        assert puede_cursar(session, alumno, cadena["prog3"])[0] is False

    def test_no_alcanza_a_otro_alumno(
        self, session, alumno, otro_alumno, usuario_admin, cadena
    ):
        otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)

        assert puede_cursar(session, otro_alumno, cadena["prog2"])[0] is False

    def test_revocada_deja_de_valer(
        self, session, alumno, usuario_admin, cadena
    ):
        excepcion = otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)
        assert puede_cursar(session, alumno, cadena["prog2"])[0] is True

        ExcepcionPreviaturaService().revocar(
            excepcion.id, "Otorgada por error", usuario_admin.id, session
        )

        assert puede_cursar(session, alumno, cadena["prog2"])[0] is False


class TestOtorgarYRevocar:

    def test_motivo_obligatorio(self, session, alumno, usuario_admin, cadena):
        prev = previatura_de(session, cadena["prog2"], cadena["prog1"])

        with pytest.raises(ValueError, match="motivo"):
            ExcepcionPreviaturaService().otorgar(
                ExcepcionPreviaturaCreate(
                    alumno_id=alumno.id, previatura_id=prev.id,
                    anio_lectivo=ANIO, motivo="   ",
                ),
                otorgada_por_id=usuario_admin.id, session=session,
            )

    def test_no_se_duplica_para_el_mismo_anio(
        self, session, alumno, usuario_admin, cadena
    ):
        otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)

        with pytest.raises(ValueError, match="Ya existe una excepcion vigente"):
            otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)

    def test_se_puede_reotorgar_despues_de_revocar(
        self, session, alumno, usuario_admin, cadena
    ):
        excepcion = otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)
        ExcepcionPreviaturaService().revocar(
            excepcion.id, "Error", usuario_admin.id, session
        )

        nueva = otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)
        assert nueva.id != excepcion.id
        assert puede_cursar(session, alumno, cadena["prog2"])[0] is True

    def test_no_se_revoca_dos_veces(self, session, alumno, usuario_admin, cadena):
        excepcion = otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)
        service = ExcepcionPreviaturaService()
        service.revocar(excepcion.id, "Error", usuario_admin.id, session)

        with pytest.raises(ValueError, match="ya estaba revocada"):
            service.revocar(excepcion.id, "De nuevo", usuario_admin.id, session)

    def test_queda_registrado_quien_y_por_que(
        self, session, alumno, usuario_admin, cadena
    ):
        excepcion = otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)

        assert excepcion.otorgada_por_id == usuario_admin.id
        assert excepcion.motivo == "Caso excepcional autorizado por direccion"
        assert excepcion.fecha_otorgamiento is not None
        assert excepcion.revocada is False

    def test_listado_resuelve_los_nombres(
        self, session, alumno, usuario_admin, cadena
    ):
        otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)

        listado = ExcepcionPreviaturaService().listar_de_alumno(alumno.id, session)

        assert len(listado) == 1
        item = listado[0]
        assert item["materia_nombre"] == "Programacion 2"
        assert item["materia_previa_nombre"] == "Programacion 1"
        assert item["vigente"] is True

    def test_listado_puede_incluir_revocadas_para_auditoria(
        self, session, alumno, usuario_admin, cadena
    ):
        excepcion = otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)
        service = ExcepcionPreviaturaService()
        service.revocar(excepcion.id, "Error", usuario_admin.id, session)

        assert service.listar_de_alumno(alumno.id, session) == []

        con_revocadas = service.listar_de_alumno(
            alumno.id, session, incluir_revocadas=True
        )
        assert len(con_revocadas) == 1
        assert con_revocadas[0]["vigente"] is False
        assert con_revocadas[0]["motivo_revocacion"] == "Error"


class TestInscripcionReal:
    """La excepcion tiene que habilitar la inscripcion, no solo la validacion."""

    def test_se_puede_inscribir_con_excepcion(
        self, session, alumno, usuario_admin, cadena
    ):
        otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)

        inscripcion = InscripcionMateriaService().inscribir_materia(
            alumno_id=alumno.id,
            instancia_cursado_id=cadena["instancias"]["prog2"].id,
            session=session,
        )

        assert inscripcion.estado == EstadoInscripcionMateria.CURSANDO

    def test_sin_excepcion_la_inscripcion_es_rechazada(
        self, session, alumno, cadena
    ):
        with pytest.raises(ValueError, match="previaturas"):
            InscripcionMateriaService().inscribir_materia(
                alumno_id=alumno.id,
                instancia_cursado_id=cadena["instancias"]["prog2"].id,
                session=session,
            )


class TestPantallaDeInscripcion:
    """
    El alumno tiene que entender por que ve habilitada una materia cuya
    previatura debe, o se lee como un error del sistema.
    """

    def _materia(self, session, alumno, programa, materia_id):
        datos = InscripcionMateriaService().get_materias_habilitadas(
            alumno.id, programa.id, session
        )
        return next(
            (m for m in datos["materias"] if m["materia_id"] == materia_id), None
        )

    def test_muestra_el_motivo_de_la_excepcion(
        self, session, alumno, usuario_admin, programa, cadena
    ):
        otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)

        fila = self._materia(session, alumno, programa, cadena["prog2"].id)

        assert fila["puede_inscribirse"] is True
        assert len(fila["excepciones_aplicadas"]) == 1
        excepcion = fila["excepciones_aplicadas"][0]
        assert excepcion["materia_previa"] == cadena["prog1"].nombre
        assert excepcion["motivo"] == "Caso excepcional autorizado por direccion"

    def test_sin_excepcion_la_lista_va_vacia(
        self, session, alumno, programa, cadena
    ):
        fila = self._materia(session, alumno, programa, cadena["prog2"].id)

        assert fila["excepciones_aplicadas"] == []
        assert fila["puede_inscribirse"] is False

    def test_prog3_explica_que_prog2_esta_aprobada_por_excepcion(
        self, session, alumno, usuario_admin, programa, cadena
    ):
        otorgar(session, alumno, cadena["prog2"], cadena["prog1"], usuario_admin)
        poner_estado(session, alumno, cadena, "prog2", EstadoInscripcionMateria.APROBADO)
        poner_estado(session, alumno, cadena, "prog1", EstadoInscripcionMateria.REPROBADO)

        fila = self._materia(session, alumno, programa, cadena["prog3"].id)

        # La excepcion es de prog2, no de prog3: prog3 no muestra ninguna
        assert fila["excepciones_aplicadas"] == []
        assert fila["puede_inscribirse"] is False
        assert any("por excepcion" in m for m in fila["motivos"]), fila["motivos"]


class TestCicloIndirecto:
    """
    previatura_service ya bloquea los ciclos al crear, pero puede haber alguno
    cargado antes de esa validacion o por fuera de la API. La regla es
    recursiva: sin guarda no terminaria. Por eso se arma el ciclo a mano,
    salteando el servicio.
    """

    def test_no_se_cuelga_con_un_ciclo(self, session, alumno, cadena):
        # Prog1 -> Prog3 cierra el ciclo Prog1 -> Prog2 -> Prog3 -> Prog1
        session.add(Previatura(
            materia_id=cadena["prog1"].id,
            materia_previa_id=cadena["prog3"].id,
            tipo_requerido=TipoPreviatura.APROBADA,
        ))
        session.commit()

        for clave in ("prog1", "prog2", "prog3"):
            poner_estado(session, alumno, cadena, clave, EstadoInscripcionMateria.APROBADO)

        # Lo importante es que termine; con un ciclo nada esta plenamente cumplido
        cumple, faltantes = puede_cursar(session, alumno, cadena["prog3"])
        assert isinstance(cumple, bool)
