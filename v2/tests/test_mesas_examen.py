"""
Mesas de examen: el periodo declarado contra el que se cuenta el tope.

Antes el periodo se inferia del mes calendario de fecha_examen, y eso contaba mal
en dos casos:

  - una mesa que cruza fin de mes (30/07 y 02/08) contaba doble, y el alumno se
    podia anotar a 8 examenes de la misma mesa;
  - dos mesas dentro de un mismo mes contaban como una, y lo bloqueaba mal. Este
    es el peor de los dos, porque le niega algo que le corresponde.

Los dos casos estan cubiertos aca. El comportamiento por mes sigue vivo para los
examenes sin mesa asignada y se prueba en test_limites_examenes.py.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from v2.models.materia import Materia
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen, InstanciaExamenCreate
from v2.models.mesa_examen import MesaExamen, MesaExamenCreate
from v2.models.politica_examen import PoliticaExamen
from v2.models.enums import EstadoInscripcionMateria, EstadoInstanciaCursado
from v2.services.inscripcion_examen_service import InscripcionExamenService
from v2.services.instancia_examen_service import InstanciaExamenService
from v2.services.mesa_examen_service import MesaExamenService

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


@pytest.fixture(name="escenario")
def fixture_escenario(session, alumno, programa, politica_base100, politica_examen):
    """Seis materias con el alumno en A_EXAMEN y un examen abierto en cada una."""
    base = ahora_naive()
    armado = {"inscripciones": {}, "instancias": {}}

    for indice in range(1, 7):
        materia = Materia(
            programa_id=programa.id, nombre=f"Materia {indice}",
            codigo=f"MX{indice}", semestre=1, creditos=10,
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

        instancia = InstanciaExamen(
            materia_id=materia.id, nombre=f"Examen {indice}",
            fecha_inicio_inscripcion=base - timedelta(days=5),
            fecha_fin_inscripcion=base + timedelta(days=5),
            fecha_examen=datetime(2026, 7, indice + 9),
            habilitado=True,
        )
        session.add(instancia)
        session.commit()
        session.refresh(instancia)

        armado["inscripciones"][indice] = insc
        armado["instancias"][indice] = instancia

    return armado


def crear_mesa(session, nombre, max_examenes=None):
    base = ahora_naive()
    mesa = MesaExamen(
        nombre=nombre, anio_lectivo=2026,
        fecha_inicio_inscripcion=base - timedelta(days=5),
        fecha_fin_inscripcion=base + timedelta(days=5),
        max_examenes=max_examenes,
    )
    session.add(mesa)
    session.commit()
    session.refresh(mesa)
    return mesa


def preparar(session, escenario, indice, fecha, mesa=None):
    """Fija la fecha del examen y, si se da, lo asigna a una mesa."""
    instancia = escenario["instancias"][indice]
    instancia.fecha_examen = fecha
    if mesa is not None:
        instancia.mesa_examen_id = mesa.id
    session.add(instancia)
    session.commit()
    session.refresh(instancia)
    return instancia


def inscribir(session, escenario, indice):
    return SERVICIO.inscribir_examen(
        inscripcion_materia_id=escenario["inscripciones"][indice].id,
        instancia_examen_id=escenario["instancias"][indice].id,
        session=session,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Los dos casos que el mes contaba mal
# ══════════════════════════════════════════════════════════════════════════════

class TestLoQueArreglaLaMesa:
    def test_una_mesa_que_cruza_fin_de_mes_cuenta_junta(self, session, escenario):
        """Con el mes, el 02/08 era otro periodo y el alumno llegaba a 8."""
        julio = crear_mesa(session, "Julio 2026")

        for indice, dia in zip(range(1, 5), (27, 28, 29, 30)):
            preparar(session, escenario, indice, datetime(2026, 7, dia), julio)
            inscribir(session, escenario, indice)

        preparar(session, escenario, 5, datetime(2026, 8, 2), julio)

        with pytest.raises(ValueError, match="maximo es 4"):
            inscribir(session, escenario, 5)

    def test_dos_mesas_en_un_mismo_mes_cuentan_aparte(self, session, escenario):
        """
        Con el mes, la extraordinaria de julio se sumaba a la ordinaria y
        bloqueaba al alumno sin corresponder.
        """
        ordinaria = crear_mesa(session, "Julio 2026 - Ordinaria")
        extraordinaria = crear_mesa(session, "Julio 2026 - Extraordinaria")

        for indice, dia in zip(range(1, 5), (6, 7, 8, 9)):
            preparar(session, escenario, indice, datetime(2026, 7, dia), ordinaria)
            inscribir(session, escenario, indice)

        preparar(session, escenario, 5, datetime(2026, 7, 27), extraordinaria)
        assert inscribir(session, escenario, 5) is not None


class TestLoQueNoCambia:
    def test_el_mismo_dia_bloquea_entre_mesas_distintas(self, session, escenario):
        """No se puede estar en dos examenes a la vez, sean de la mesa que sean."""
        ordinaria = crear_mesa(session, "Ordinaria")
        extraordinaria = crear_mesa(session, "Extraordinaria")

        preparar(session, escenario, 1, datetime(2026, 7, 10), ordinaria)
        inscribir(session, escenario, 1)

        preparar(session, escenario, 2, datetime(2026, 7, 10), extraordinaria)
        with pytest.raises(ValueError, match="mas de uno por dia"):
            inscribir(session, escenario, 2)

    def test_con_mesa_y_sin_mesa_no_se_mezclan(self, session, escenario):
        """
        Consecuencia de que la mesa sea opcional: un examen con mesa y otro sin
        mesa no cuentan juntos aunque caigan en el mismo mes. Se resuelve
        asignandole mesa a todos.
        """
        julio = crear_mesa(session, "Julio 2026")

        for indice, dia in zip(range(1, 5), (6, 7, 8, 9)):
            preparar(session, escenario, indice, datetime(2026, 7, dia), julio)
            inscribir(session, escenario, indice)

        preparar(session, escenario, 5, datetime(2026, 7, 27))
        assert inscribir(session, escenario, 5) is not None


class TestTopePropioDeLaMesa:
    def test_la_mesa_puede_acotar_el_tope(self, session, escenario):
        """Sin tocar codigo: max_examenes de la mesa manda sobre el general."""
        acotada = crear_mesa(session, "Mesa acotada", max_examenes=2)

        for indice, dia in zip((1, 2), (6, 7)):
            preparar(session, escenario, indice, datetime(2026, 7, dia), acotada)
            inscribir(session, escenario, indice)

        preparar(session, escenario, 3, datetime(2026, 7, 8), acotada)
        with pytest.raises(ValueError, match="maximo es 2"):
            inscribir(session, escenario, 3)

    def test_en_null_usa_el_general(self, session, escenario):
        sin_tope = crear_mesa(session, "Mesa normal")

        for indice, dia in zip(range(1, 5), (6, 7, 8, 9)):
            preparar(session, escenario, indice, datetime(2026, 7, dia), sin_tope)
            inscribir(session, escenario, indice)

        preparar(session, escenario, 5, datetime(2026, 7, 27), sin_tope)
        with pytest.raises(ValueError, match="maximo es 4"):
            inscribir(session, escenario, 5)

    def test_la_pantalla_respeta_el_tope_de_la_mesa(
        self, session, alumno, programa, escenario
    ):
        acotada = crear_mesa(session, "Mesa acotada", max_examenes=1)

        preparar(session, escenario, 1, datetime(2026, 7, 6), acotada)
        inscribir(session, escenario, 1)
        preparar(session, escenario, 2, datetime(2026, 7, 7), acotada)

        habilitados = SERVICIO.get_examenes_habilitados(alumno.id, programa.id, session)
        fila = next(
            h for h in habilitados
            if h["instancia_examen_id"] == escenario["instancias"][2].id
        )

        assert fila["puede_inscribirse"] is False
        assert fila["mesa_examen_id"] == acotada.id
        assert any("maximo es 1" in m for m in fila["motivos"]), fila["motivos"]


# ══════════════════════════════════════════════════════════════════════════════
# Crear un examen dentro de una mesa
# ══════════════════════════════════════════════════════════════════════════════

class TestCreacionDeExamen:
    @pytest.fixture(name="materia_suelta")
    def fixture_materia_suelta(self, session, programa, politica_base100):
        materia = Materia(
            programa_id=programa.id, nombre="Materia nueva", codigo="NUE1",
            semestre=1, creditos=10, politica_id=politica_base100.id,
        )
        session.add(materia)
        session.commit()
        session.refresh(materia)
        return materia

    def test_copia_la_ventana_de_la_mesa(self, session, materia_suelta):
        """El dato que antes habia que repetir en cada examen."""
        mesa = crear_mesa(session, "Julio 2026")

        instancia = InstanciaExamenService().crear(
            InstanciaExamenCreate(
                materia_id=materia_suelta.id, nombre="Examen sin fechas",
                mesa_examen_id=mesa.id, fecha_examen=datetime(2026, 7, 20),
            ),
            session,
        )

        assert instancia.fecha_inicio_inscripcion == mesa.fecha_inicio_inscripcion
        assert instancia.fecha_fin_inscripcion == mesa.fecha_fin_inscripcion

    def test_lo_que_se_manda_explicito_gana(self, session, materia_suelta):
        mesa = crear_mesa(session, "Julio 2026")
        propio_inicio = datetime(2026, 6, 1)
        propio_fin = datetime(2026, 6, 20)

        instancia = InstanciaExamenService().crear(
            InstanciaExamenCreate(
                materia_id=materia_suelta.id, nombre="Examen con fechas propias",
                mesa_examen_id=mesa.id, fecha_examen=datetime(2026, 7, 20),
                fecha_inicio_inscripcion=propio_inicio,
                fecha_fin_inscripcion=propio_fin,
            ),
            session,
        )

        assert instancia.fecha_inicio_inscripcion == propio_inicio
        assert instancia.fecha_fin_inscripcion == propio_fin

    def test_sin_mesa_las_fechas_son_obligatorias(self, session, materia_suelta):
        with pytest.raises(ValueError, match="fecha_inicio_inscripcion"):
            InstanciaExamenService().crear(
                InstanciaExamenCreate(
                    materia_id=materia_suelta.id, nombre="Examen suelto",
                    fecha_examen=datetime(2026, 7, 20),
                ),
                session,
            )

    def test_una_mesa_inactiva_se_rechaza(self, session, materia_suelta):
        mesa = crear_mesa(session, "Mesa vieja")
        mesa.activo = False
        session.add(mesa)
        session.commit()

        with pytest.raises(ValueError, match="inactiva"):
            InstanciaExamenService().crear(
                InstanciaExamenCreate(
                    materia_id=materia_suelta.id, nombre="Examen",
                    mesa_examen_id=mesa.id, fecha_examen=datetime(2026, 7, 20),
                ),
                session,
            )

    def test_una_mesa_inexistente_se_rechaza(self, session, materia_suelta):
        with pytest.raises(ValueError, match="no encontrada"):
            InstanciaExamenService().crear(
                InstanciaExamenCreate(
                    materia_id=materia_suelta.id, nombre="Examen",
                    mesa_examen_id=9999, fecha_examen=datetime(2026, 7, 20),
                ),
                session,
            )


# ══════════════════════════════════════════════════════════════════════════════
# CRUD de mesas
# ══════════════════════════════════════════════════════════════════════════════

class TestServicioDeMesas:
    def test_no_se_borra_una_mesa_con_examenes(self, session, escenario):
        """
        Borrarla dejaria a esos examenes sin periodo, y volverian a contarse por
        mes calendario sin que nadie se entere.
        """
        julio = crear_mesa(session, "Julio 2026")
        preparar(session, escenario, 1, datetime(2026, 7, 10), julio)

        with pytest.raises(ValueError, match="examenes asignados"):
            MesaExamenService().eliminar(julio.id, session)

    def test_una_mesa_vacia_si_se_borra(self, session):
        vacia = crear_mesa(session, "Mesa vacia")
        MesaExamenService().eliminar(vacia.id, session)

        assert MesaExamenService().get_by_id(vacia.id, session) is None

    def test_el_listado_cuenta_los_examenes(self, session, escenario):
        julio = crear_mesa(session, "Julio 2026")
        preparar(session, escenario, 1, datetime(2026, 7, 10), julio)
        preparar(session, escenario, 2, datetime(2026, 7, 11), julio)

        fila = next(
            f for f in MesaExamenService().listar(session) if f["id"] == julio.id
        )
        assert fila["examenes"] == 2

    def test_el_listado_esconde_las_inactivas(self, session):
        activa = crear_mesa(session, "Activa")
        inactiva = crear_mesa(session, "Inactiva")
        inactiva.activo = False
        session.add(inactiva)
        session.commit()

        ids = {f["id"] for f in MesaExamenService().listar(session)}
        assert activa.id in ids
        assert inactiva.id not in ids

        ids_todas = {
            f["id"] for f in MesaExamenService().listar(session, incluir_inactivas=True)
        }
        assert inactiva.id in ids_todas

    def test_la_ventana_no_puede_cerrar_antes_de_abrir(self, session):
        base = ahora_naive()
        with pytest.raises(ValueError, match="cerrar antes de abrir"):
            MesaExamenService().crear(
                MesaExamenCreate(
                    nombre="Invertida", anio_lectivo=2026,
                    fecha_inicio_inscripcion=base + timedelta(days=10),
                    fecha_fin_inscripcion=base,
                ),
                session,
            )

    def test_el_tope_tiene_que_ser_al_menos_uno(self, session):
        base = ahora_naive()
        with pytest.raises(ValueError, match="al menos 1"):
            MesaExamenService().crear(
                MesaExamenCreate(
                    nombre="Cero", anio_lectivo=2026,
                    fecha_inicio_inscripcion=base,
                    fecha_fin_inscripcion=base + timedelta(days=5),
                    max_examenes=0,
                ),
                session,
            )
