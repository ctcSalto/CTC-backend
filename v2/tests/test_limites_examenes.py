"""
Topes de inscripcion a examen.

Dos reglas de la institucion:
  - no mas de 4 examenes por periodo
  - no dos examenes el mismo dia

Las dos son DURAS: aplican tambien cuando inscribe bedelia. Es la diferencia con
el plazo de inscripcion, que si tiene bypass para admin.

El periodo es el mes calendario de fecha_examen. No existe una entidad mesa de
examen en el modelo, asi que el mes es la aproximacion acordada; el test
test_una_mesa_que_cruza_fin_de_mes_cuenta_aparte deja documentado su limite.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from sqlmodel import select

from v2.models.materia import Materia
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.politica_examen import PoliticaExamen
from v2.models.enums import (
    EstadoInscripcionMateria, EstadoInstanciaCursado, EstadoInscripcionExamen,
)
from v2.services.inscripcion_examen_service import InscripcionExamenService

SERVICIO = InscripcionExamenService()


def ahora_naive():
    tz = ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo"))
    return datetime.now(tz).replace(tzinfo=None)


@pytest.fixture(name="politica_examen")
def fixture_politica_examen(session):
    pol = PoliticaExamen(
        nombre="Examen base 100", nota_maxima=Decimal("100"),
        umbral_aprobacion=Decimal("70"), max_oportunidades=5,
    )
    session.add(pol)
    session.commit()
    session.refresh(pol)
    return pol


@pytest.fixture(name="mesa")
def fixture_mesa(session, alumno, programa, politica_base100, politica_examen):
    """
    Seis materias distintas, todas con el alumno en A_EXAMEN y con una instancia
    de examen con la inscripcion abierta.

    Hacen falta seis porque el tope es cuatro: con tres materias no se puede
    probar ni el cuarto ni el quinto.
    """
    base = ahora_naive()
    armado = {"inscripciones": {}, "instancias": {}}

    for indice in range(1, 7):
        materia = Materia(
            programa_id=programa.id, nombre=f"Materia {indice}",
            codigo=f"EX{indice}", semestre=1, creditos=10,
            politica_id=politica_base100.id,
            politica_examen_id=politica_examen.id, activo=True,
        )
        session.add(materia)
        session.commit()
        session.refresh(materia)

        ic = InstanciaCursado(
            materia_id=materia.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        insc = InscripcionMateria(
            alumno_id=alumno.id, instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.A_EXAMEN,
        )
        session.add(insc)
        session.commit()
        session.refresh(insc)

        # Ventana abierta ahora; la fecha del examen la fija cada test
        instancia = InstanciaExamen(
            materia_id=materia.id, nombre=f"Examen {indice}",
            fecha_inicio_inscripcion=base - timedelta(days=5),
            fecha_fin_inscripcion=base + timedelta(days=5),
            fecha_examen=datetime(2026, 7, indice + 9),  # 10/07 .. 15/07
            habilitado=True,
        )
        session.add(instancia)
        session.commit()
        session.refresh(instancia)

        armado["inscripciones"][indice] = insc
        armado["instancias"][indice] = instancia

    return armado


def mover_examen(session, instancia, fecha):
    instancia.fecha_examen = fecha
    session.add(instancia)
    session.commit()
    session.refresh(instancia)


def inscribir(session, mesa, indice, **kwargs):
    return SERVICIO.inscribir_examen(
        inscripcion_materia_id=mesa["inscripciones"][indice].id,
        instancia_examen_id=mesa["instancias"][indice].id,
        session=session,
        **kwargs,
    )


# ══════════════════════════════════════════════════════════════════════════════
# La regla, aislada de la base
# ══════════════════════════════════════════════════════════════════════════════

class TestReglaPura:
    """
    Sin mesa asignada, que es el caso de estos tests, el periodo es el mes
    calendario. `ocupadas` son tuplas (mesa_examen_id, fecha).
    """

    @staticmethod
    def sin_mesa(*fechas):
        return [(None, fecha) for fecha in fechas]

    def test_sin_examenes_previos_no_hay_motivos(self):
        assert SERVICIO._evaluar_limites(datetime(2026, 7, 10), []) == []

    def test_mismo_dia_bloquea(self):
        motivos = SERVICIO._evaluar_limites(
            datetime(2026, 7, 10, 14, 0), self.sin_mesa(datetime(2026, 7, 10, 9, 0))
        )
        assert any("mas de uno por dia" in m for m in motivos)

    def test_el_dia_anterior_no_molesta(self):
        assert SERVICIO._evaluar_limites(
            datetime(2026, 7, 10), self.sin_mesa(datetime(2026, 7, 9))
        ) == []

    def test_tres_en_el_mes_permiten_el_cuarto(self):
        ocupadas = self.sin_mesa(*[datetime(2026, 7, d) for d in (1, 2, 3)])
        assert SERVICIO._evaluar_limites(datetime(2026, 7, 20), ocupadas) == []

    def test_cuatro_en_el_mes_bloquean_el_quinto(self):
        ocupadas = self.sin_mesa(*[datetime(2026, 7, d) for d in (1, 2, 3, 4)])
        motivos = SERVICIO._evaluar_limites(datetime(2026, 7, 20), ocupadas)
        assert any("maximo es 4" in m for m in motivos)

    def test_los_de_otro_mes_no_cuentan(self):
        ocupadas = self.sin_mesa(*[datetime(2026, 6, d) for d in (1, 2, 3, 4)])
        assert SERVICIO._evaluar_limites(datetime(2026, 7, 20), ocupadas) == []

    def test_los_del_mismo_mes_de_otro_anio_no_cuentan(self):
        ocupadas = self.sin_mesa(*[datetime(2025, 7, d) for d in (1, 2, 3, 4)])
        assert SERVICIO._evaluar_limites(datetime(2026, 7, 20), ocupadas) == []

    def test_puede_chocar_por_las_dos_reglas_a_la_vez(self):
        ocupadas = self.sin_mesa(*[datetime(2026, 7, d) for d in (1, 2, 3, 20)])
        motivos = SERVICIO._evaluar_limites(datetime(2026, 7, 20), ocupadas)
        assert len(motivos) == 2

    def test_sin_fecha_de_examen_no_opina(self):
        """Una instancia sin fecha no puede evaluarse; no se inventa un bloqueo."""
        assert SERVICIO._evaluar_limites(
            None, self.sin_mesa(datetime(2026, 7, 10))
        ) == []

    def test_una_mesa_ignora_el_mes(self):
        """
        Con mesa, el mes no interviene: cuatro de la misma mesa bloquean aunque
        esten repartidos en meses distintos.
        """
        ocupadas = [
            (7, datetime(2026, 7, 28)), (7, datetime(2026, 7, 29)),
            (7, datetime(2026, 7, 30)), (7, datetime(2026, 8, 1)),
        ]
        motivos = SERVICIO._evaluar_limites(
            datetime(2026, 8, 3), ocupadas, mesa_examen_id=7
        )
        assert any("maximo es 4" in m for m in motivos)

    def test_mesas_distintas_no_se_suman(self):
        ocupadas = [(7, datetime(2026, 7, d)) for d in (6, 7, 8, 9)]
        assert SERVICIO._evaluar_limites(
            datetime(2026, 7, 27), ocupadas, mesa_examen_id=8
        ) == []

    def test_el_tope_de_la_mesa_pisa_al_general(self):
        ocupadas = [(7, datetime(2026, 7, 6)), (7, datetime(2026, 7, 7))]
        motivos = SERVICIO._evaluar_limites(
            datetime(2026, 7, 20), ocupadas, mesa_examen_id=7, max_examenes=2
        )
        assert any("maximo es 2" in m for m in motivos)


# ══════════════════════════════════════════════════════════════════════════════
# Contra la base, por inscribir_examen
# ══════════════════════════════════════════════════════════════════════════════

class TestTopeDelPeriodo:
    def test_cuatro_examenes_se_pueden(self, session, mesa):
        for indice in range(1, 5):
            assert inscribir(session, mesa, indice) is not None

    def test_el_quinto_se_rechaza(self, session, mesa):
        for indice in range(1, 5):
            inscribir(session, mesa, indice)

        with pytest.raises(ValueError, match="maximo es 4"):
            inscribir(session, mesa, 5)

    def test_una_baja_libera_el_lugar(self, session, mesa):
        for indice in range(1, 5):
            inscribir(session, mesa, indice)

        inscripciones = session.exec(select(InscripcionExamen)).all()
        primera = inscripciones[0]
        primera.estado = EstadoInscripcionExamen.BAJA
        session.add(primera)
        session.commit()

        assert inscribir(session, mesa, 5) is not None

    def test_lo_ya_rendido_sigue_ocupando(self, session, mesa):
        """
        Si rendir liberara el lugar, se podria pasar el tope rindiendo y
        volviendo a anotarse dentro del mismo mes.
        """
        for indice in range(1, 5):
            inscribir(session, mesa, indice)

        inscripciones = session.exec(select(InscripcionExamen)).all()
        rendida = inscripciones[0]
        rendida.estado = EstadoInscripcionExamen.REPROBADO
        session.add(rendida)
        session.commit()

        with pytest.raises(ValueError, match="maximo es 4"):
            inscribir(session, mesa, 5)

    def test_otro_mes_habilita_otros_cuatro(self, session, mesa):
        for indice in range(1, 5):
            inscribir(session, mesa, indice)

        mover_examen(session, mesa["instancias"][5], datetime(2026, 8, 12))
        assert inscribir(session, mesa, 5) is not None

    def test_sin_mesa_una_que_cruza_fin_de_mes_cuenta_aparte(self, session, mesa):
        """
        El limite de agrupar por mes, que es lo que se hace cuando el examen no
        tiene mesa asignada: 30/07 y 02/08 caen en periodos distintos.

        Con mesa esto no pasa; lo cubre TestMesaDeExamen.
        """
        for indice, dia in zip(range(1, 5), (27, 28, 29, 30)):
            mover_examen(session, mesa["instancias"][indice], datetime(2026, 7, dia))
            inscribir(session, mesa, indice)

        mover_examen(session, mesa["instancias"][5], datetime(2026, 8, 2))
        assert inscribir(session, mesa, 5) is not None


class TestMismoDia:
    def test_dos_el_mismo_dia_se_rechaza(self, session, mesa):
        inscribir(session, mesa, 1)

        mover_examen(
            session, mesa["instancias"][2], mesa["instancias"][1].fecha_examen
        )
        with pytest.raises(ValueError, match="mas de uno por dia"):
            inscribir(session, mesa, 2)

    def test_distinta_hora_el_mismo_dia_tampoco(self, session, mesa):
        mover_examen(session, mesa["instancias"][1], datetime(2026, 7, 10, 9, 0))
        inscribir(session, mesa, 1)

        mover_examen(session, mesa["instancias"][2], datetime(2026, 7, 10, 18, 30))
        with pytest.raises(ValueError, match="mas de uno por dia"):
            inscribir(session, mesa, 2)

    def test_el_dia_siguiente_si(self, session, mesa):
        mover_examen(session, mesa["instancias"][1], datetime(2026, 7, 10))
        inscribir(session, mesa, 1)

        mover_examen(session, mesa["instancias"][2], datetime(2026, 7, 11))
        assert inscribir(session, mesa, 2) is not None

    def test_una_baja_libera_el_dia(self, session, mesa):
        mover_examen(session, mesa["instancias"][1], datetime(2026, 7, 10))
        inscripcion = inscribir(session, mesa, 1)

        inscripcion.estado = EstadoInscripcionExamen.BAJA
        session.add(inscripcion)
        session.commit()

        mover_examen(session, mesa["instancias"][2], datetime(2026, 7, 10))
        assert inscribir(session, mesa, 2) is not None


class TestSinBypass:
    """
    Las dos reglas aplican tambien a bedelia. bypass_periodo saltea el plazo de
    inscripcion, que es administrativo, no cuanto puede rendir un alumno.
    """

    def test_bedelia_tampoco_pasa_de_cuatro(self, session, mesa):
        for indice in range(1, 5):
            inscribir(session, mesa, indice, bypass_periodo=True)

        with pytest.raises(ValueError, match="maximo es 4"):
            inscribir(session, mesa, 5, bypass_periodo=True)

    def test_bedelia_tampoco_dos_el_mismo_dia(self, session, mesa):
        inscribir(session, mesa, 1, bypass_periodo=True)

        mover_examen(
            session, mesa["instancias"][2], mesa["instancias"][1].fecha_examen
        )
        with pytest.raises(ValueError, match="mas de uno por dia"):
            inscribir(session, mesa, 2, bypass_periodo=True)

    def test_el_plazo_si_se_saltea(self, session, mesa):
        """Control: bypass_periodo sigue sirviendo para lo que fue hecho."""
        base = ahora_naive()
        instancia = mesa["instancias"][1]
        instancia.fecha_inicio_inscripcion = base - timedelta(days=30)
        instancia.fecha_fin_inscripcion = base - timedelta(days=20)
        session.add(instancia)
        session.commit()

        with pytest.raises(ValueError, match="Fuera del plazo"):
            inscribir(session, mesa, 1)

        assert inscribir(session, mesa, 1, bypass_periodo=True) is not None


# ══════════════════════════════════════════════════════════════════════════════
# La pantalla no puede ofrecer lo que el POST rechaza
# ══════════════════════════════════════════════════════════════════════════════

class TestPantallaDeExamenes:
    def _fila(self, session, alumno, programa, instancia_id):
        habilitados = SERVICIO.get_examenes_habilitados(
            alumno.id, programa.id, session
        )
        return next(
            (h for h in habilitados if h["instancia_examen_id"] == instancia_id), None
        )

    def test_el_quinto_sale_bloqueado_con_motivo(
        self, session, alumno, programa, mesa
    ):
        for indice in range(1, 5):
            inscribir(session, mesa, indice)

        fila = self._fila(session, alumno, programa, mesa["instancias"][5].id)

        assert fila is not None
        assert fila["puede_inscribirse"] is False
        assert any("maximo es 4" in m for m in fila["motivos"]), fila["motivos"]

    def test_el_del_mismo_dia_sale_bloqueado_con_motivo(
        self, session, alumno, programa, mesa
    ):
        mover_examen(session, mesa["instancias"][1], datetime(2026, 7, 10))
        inscribir(session, mesa, 1)
        mover_examen(session, mesa["instancias"][2], datetime(2026, 7, 10))

        fila = self._fila(session, alumno, programa, mesa["instancias"][2].id)

        assert fila["puede_inscribirse"] is False
        assert any("mas de uno por dia" in m for m in fila["motivos"]), fila["motivos"]

    def test_con_lugar_sigue_habilitado(self, session, alumno, programa, mesa):
        inscribir(session, mesa, 1)

        fila = self._fila(session, alumno, programa, mesa["instancias"][2].id)

        assert fila["puede_inscribirse"] is True, fila["motivos"]

    def test_el_que_ya_tiene_no_se_choca_consigo_mismo(
        self, session, alumno, programa, mesa
    ):
        """
        Su propia fecha figura entre las ocupadas: el motivo tiene que ser 'ya
        estas inscripto' y no un falso choque de mismo dia.
        """
        inscribir(session, mesa, 1)

        fila = self._fila(session, alumno, programa, mesa["instancias"][1].id)

        assert fila["ya_inscripto"] is True
        assert not any("mas de uno por dia" in m for m in fila["motivos"]), fila["motivos"]
