"""
Tests de verificacion de egreso.

Cubre:
- Que estados de inscripcion cuentan como materia cumplida (aprobado, exonerado,
  revalidada) y cuales no
- Conteo de creditos y porcentaje de avance
- Detalle de aprobadas/pendientes con recursadas
"""
import pytest
from decimal import Decimal

from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.enums import EstadoInscripcionMateria, EstadoInstanciaCursado
from v2.services.egreso_service import EgresoService


def inscribir(session, alumno, materia, estado, anio_lectivo=2025,
              nota_final=None, nota_curso=None):
    """Crea una instancia de cursado y una inscripcion del alumno en ese estado."""
    ic = InstanciaCursado(
        materia_id=materia.id,
        anio_lectivo=anio_lectivo,
        estado=EstadoInstanciaCursado.FINALIZADA,
    )
    session.add(ic)
    session.commit()
    session.refresh(ic)

    otorga_creditos = estado in EgresoService.ESTADOS_CUMPLIDA
    insc = InscripcionMateria(
        alumno_id=alumno.id,
        instancia_cursado_id=ic.id,
        estado=estado,
        nota_final=nota_final,
        nota_curso=nota_curso,
        creditos_obtenidos=materia.creditos if otorga_creditos else 0,
    )
    session.add(insc)
    session.commit()
    session.refresh(insc)
    return insc


def por_nombre(detalle):
    return {item["nombre"]: item for item in detalle}


class TestEgresoEstadosQueCuentan:
    """Que estados dan la materia por cumplida."""

    def test_sin_inscripciones_todo_pendiente(
        self, session, alumno, programa, materias_con_previaturas
    ):
        res = EgresoService().verificar_egreso(alumno.id, programa.id, session)

        assert res["creditos_obtenidos"] == 0
        assert res["materias_aprobadas"] == 0
        assert res["materias_pendientes"] == 3
        assert res["cumple"] is False

    @pytest.mark.parametrize("estado", [
        EstadoInscripcionMateria.APROBADO,
        EstadoInscripcionMateria.EXONERADO,
        EstadoInscripcionMateria.REVALIDADA,
    ])
    def test_estados_cumplidos_cuentan_creditos(
        self, session, alumno, programa, materias_con_previaturas, estado
    ):
        """
        Los tres estados que otorgan creditos cuentan para el egreso. Antes solo
        se contaba APROBADO: un alumno que exonero todo veia cero creditos y no
        podia egresar nunca.
        """
        m1 = materias_con_previaturas["prog1"]
        inscribir(session, alumno, m1, estado)

        res = EgresoService().verificar_egreso(alumno.id, programa.id, session)

        assert res["creditos_obtenidos"] == m1.creditos
        assert res["materias_aprobadas"] == 1
        assert res["materias_pendientes"] == 2

        detalle = por_nombre(res["detalle_aprobadas"])
        assert detalle["Programacion 1"]["estado"] == estado.value

    @pytest.mark.parametrize("estado", [
        EstadoInscripcionMateria.CURSANDO,
        EstadoInscripcionMateria.A_EXAMEN,
        EstadoInscripcionMateria.REPROBADO,
        EstadoInscripcionMateria.PERDIDO_INASISTENCIA,
        EstadoInscripcionMateria.ABANDONO,
    ])
    def test_estados_no_cumplidos_quedan_pendientes(
        self, session, alumno, programa, materias_con_previaturas, estado
    ):
        """Una materia en curso o no aprobada sigue pendiente para el egreso."""
        m1 = materias_con_previaturas["prog1"]
        inscribir(session, alumno, m1, estado)

        res = EgresoService().verificar_egreso(alumno.id, programa.id, session)

        assert res["creditos_obtenidos"] == 0
        assert res["materias_aprobadas"] == 0
        assert res["materias_pendientes"] == 3
        assert "Programacion 1" in por_nombre(res["detalle_pendientes"])

    def test_revalidada_no_tiene_notas(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Una revalida no tiene notas: el cliente las distingue por `estado`."""
        m1 = materias_con_previaturas["prog1"]
        insc = inscribir(
            session, alumno, m1, EstadoInscripcionMateria.REVALIDADA
        )
        insc.motivo_revalida = "Aprobada en UTEC - 2024"
        session.add(insc)
        session.commit()

        res = EgresoService().verificar_egreso(alumno.id, programa.id, session)

        item = por_nombre(res["detalle_aprobadas"])["Programacion 1"]
        assert item["estado"] == "revalidada"
        assert item["nota_final"] is None
        assert item["nota_curso"] is None
        assert res["creditos_obtenidos"] == m1.creditos


    def test_nota_cero_se_informa_como_cero(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """
        Una nota 0 es una nota, no ausencia de nota. Comparando por verdad en vez
        de contra None, un 0 se informaba como null.
        """
        m1 = materias_con_previaturas["prog1"]
        inscribir(session, alumno, m1, EstadoInscripcionMateria.APROBADO,
                  nota_final=Decimal("0"), nota_curso=Decimal("0"))

        res = EgresoService().verificar_egreso(alumno.id, programa.id, session)

        item = por_nombre(res["detalle_aprobadas"])["Programacion 1"]
        assert item["nota_final"] == 0.0
        assert item["nota_curso"] == 0.0


class TestEgresoCompleto:
    """Cumplimiento de los requisitos con estados mezclados."""

    def test_cumple_con_estados_mezclados(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Aprobado + exonerado + revalidada cubren el plan completo."""
        # El plan de test son 3 materias de 10 creditos
        programa.creditos_requeridos = 30
        session.add(programa)
        session.commit()

        inscribir(session, alumno, materias_con_previaturas["prog1"],
                  EstadoInscripcionMateria.APROBADO, nota_final=Decimal("70"))
        inscribir(session, alumno, materias_con_previaturas["prog2"],
                  EstadoInscripcionMateria.EXONERADO, nota_final=Decimal("95"))
        inscribir(session, alumno, materias_con_previaturas["prog3"],
                  EstadoInscripcionMateria.REVALIDADA)

        res = EgresoService().verificar_egreso(alumno.id, programa.id, session)

        assert res["creditos_obtenidos"] == 30
        assert res["creditos_requeridos"] == 30
        assert res["materias_aprobadas"] == 3
        assert res["materias_pendientes"] == 0
        assert res["porcentaje_avance"] == 100.0
        assert res["cumple"] is True

    def test_no_cumple_con_una_pendiente(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Con creditos suficientes pero una materia sin cerrar, no egresa."""
        programa.creditos_requeridos = 20
        session.add(programa)
        session.commit()

        inscribir(session, alumno, materias_con_previaturas["prog1"],
                  EstadoInscripcionMateria.EXONERADO)
        inscribir(session, alumno, materias_con_previaturas["prog2"],
                  EstadoInscripcionMateria.REVALIDADA)

        res = EgresoService().verificar_egreso(alumno.id, programa.id, session)

        assert res["creditos_obtenidos"] == 20
        assert res["creditos_obtenidos"] >= res["creditos_requeridos"]
        assert res["materias_pendientes"] == 1
        assert res["cumple"] is False

    def test_porcentaje_de_avance_parcial(
        self, session, alumno, programa, materias_con_previaturas
    ):
        programa.creditos_requeridos = 30
        session.add(programa)
        session.commit()

        inscribir(session, alumno, materias_con_previaturas["prog1"],
                  EstadoInscripcionMateria.EXONERADO)

        res = EgresoService().verificar_egreso(alumno.id, programa.id, session)

        assert res["porcentaje_avance"] == pytest.approx(33.33, abs=0.01)


class TestEgresoRecursadas:
    """Varias inscripciones cumplidas en la misma materia."""

    def test_toma_la_del_anio_mas_reciente(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """
        Con dos inscripciones cumplidas en la misma materia, el detalle reporta
        la del anio lectivo mas alto. Antes se cortaba en la primera fila que
        devolvia la base, asi que las notas eran arbitrarias.
        """
        m1 = materias_con_previaturas["prog1"]
        inscribir(session, alumno, m1, EstadoInscripcionMateria.APROBADO,
                  anio_lectivo=2024, nota_final=Decimal("60"))
        inscribir(session, alumno, m1, EstadoInscripcionMateria.EXONERADO,
                  anio_lectivo=2025, nota_final=Decimal("95"))

        res = EgresoService().verificar_egreso(alumno.id, programa.id, session)

        item = por_nombre(res["detalle_aprobadas"])["Programacion 1"]
        assert item["anio_lectivo"] == 2025
        assert item["estado"] == "exonerado"
        assert item["nota_final"] == 95.0

    def test_no_cuenta_los_creditos_dos_veces(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Dos inscripciones cumplidas en la misma materia suman una sola vez."""
        m1 = materias_con_previaturas["prog1"]
        inscribir(session, alumno, m1, EstadoInscripcionMateria.APROBADO,
                  anio_lectivo=2024)
        inscribir(session, alumno, m1, EstadoInscripcionMateria.EXONERADO,
                  anio_lectivo=2025)

        res = EgresoService().verificar_egreso(alumno.id, programa.id, session)

        assert res["creditos_obtenidos"] == m1.creditos
        assert res["materias_aprobadas"] == 1

    def test_intento_reprobado_previo_no_bloquea(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Reprobo y despues exonero: cuenta como cumplida."""
        m1 = materias_con_previaturas["prog1"]
        inscribir(session, alumno, m1, EstadoInscripcionMateria.REPROBADO,
                  anio_lectivo=2024)
        inscribir(session, alumno, m1, EstadoInscripcionMateria.EXONERADO,
                  anio_lectivo=2025, nota_final=Decimal("90"))

        res = EgresoService().verificar_egreso(alumno.id, programa.id, session)

        assert res["creditos_obtenidos"] == m1.creditos
        item = por_nombre(res["detalle_aprobadas"])["Programacion 1"]
        assert item["estado"] == "exonerado"


class TestEgresoValidaciones:

    def test_programa_inexistente(self, session, alumno):
        with pytest.raises(ValueError, match="no encontrado"):
            EgresoService().verificar_egreso(alumno.id, 99999, session)
