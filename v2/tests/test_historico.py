"""
Legajo historico: la planilla de escolaridades que bedelia llevaba antes.

Lo que se fija aca:

  - Las reglas del certificado (creditos, revalidas, promedio) son las de la
    hoja ESCOLARIDAD, formula por formula. El caso de referencia es un
    certificado real de la planilla: 6 creditos, promedio 30.375. Si alguien
    "arregla" la regla del eliminado-cuenta-cero, este test lo frena.
  - La busqueda no distingue acentos ni formato de cedula.
  - El legajo del estudiante se resuelve por documento del usuario, y no
    necesita perfil de alumno.
"""
import pytest
from datetime import date

from v2.models.historico import HistoricoAlumno, HistoricoPlan, HistoricoResultado
from v2.services.historico_service import (
    HistoricoService, evaluar_fila, resumir_plan, solo_digitos, texto_busqueda,
)

SERVICIO = HistoricoService()


def fila(tipo, resultado, nota, materia="X", **extra):
    datos = dict(alumno_id=1, plan_id=1, materia=materia, tipo_evaluacion=tipo,
                 resultado=resultado, puntaje=nota, puntaje_promedio=nota)
    datos.update(extra)
    return HistoricoResultado(**datos)


# ── Reglas puras ─────────────────────────────────────────────────────────────

class TestEvaluarFila:
    def test_examen_aprobado_da_credito_y_promedia(self):
        e = evaluar_fila("EXA", "APR", 74)
        assert e["otorga_credito"] and e["cuenta_promedio"] and e["nota_promedio"] == 74

    def test_examen_con_menos_de_70_no_da_credito(self):
        assert not evaluar_fila("EXA", "APR", 69)["otorga_credito"]

    def test_cursada_exonerada_da_credito(self):
        e = evaluar_fila("CUR", "EXO", 87)
        assert e["otorga_credito"] and e["nota_promedio"] == 87

    def test_cursada_aprobada_no_cierra_nada(self):
        """Espera el examen: ni credito ni entra al promedio."""
        e = evaluar_fila("CUR", "APR", 83)
        assert not e["otorga_credito"] and not e["cuenta_promedio"] and e["nota_promedio"] == 0

    def test_eliminado_cuenta_en_el_promedio_con_cero(self):
        """La regla dura de bedelia: baja el promedio. Es la que figura en los certificados."""
        e = evaluar_fila("TALLER", "ELI", 0)
        assert not e["otorga_credito"] and e["cuenta_promedio"] and e["nota_promedio"] == 0

    def test_revalida_da_credito_pero_no_promedia(self):
        e = evaluar_fila("REV", "REV", None)
        assert e["otorga_credito"] and not e["cuenta_promedio"] and e["revalidado"]

    def test_tolera_minusculas_y_nulos(self):
        assert evaluar_fila("exa", "apr", 90)["otorga_credito"]
        assert not evaluar_fila(None, None, None)["cuenta_promedio"]


class TestResumirPlan:
    def test_el_certificado_real_de_la_planilla(self):
        """
        Reproduce el certificado de la hoja ESCOLARIDAD tal como estaba en la
        planilla: 20 filas, 6 creditos, 0 revalidados, promedio 486/16 = 30.375.
        """
        filas = [
            fila("CUR", "APR", 83), fila("CUR", "EXO", 87, "PROGRAMACION 1"),
            fila("TALLER", "APR", 88, "TALLER USAB"), fila("EXA", "APR", 74, "PENSAMIENTO"),
            fila("CUR", "APR", 70), fila("CUR", "APR", 70),
            fila("EXA", "APR", 86, "BASES 1"), fila("TALLER", "ELI", 0),
            fila("EXA", "APR", 71, "PROGRAMACION 2"), fila("CUR", "ELI", 0),
            fila("CUR", "ELI", 0), fila("CUR", "ELI", 0),
            fila("TALLER", "APR", 80, "TALLER SEG"), fila("CUR", "ELI", 0),
            fila("CUR", "ELI", 0), fila("CUR", "ELI", 0),
            fila("TALLER", "ELI", 0), fila("CUR", "APR", 70),
            fila("CUR", "ELI", 0), fila("CUR", "ELI", 0),
        ]
        plan = HistoricoPlan(codigo="AP 2022", carrera="Analista Programador", creditos_requeridos=15)

        r = resumir_plan(filas, plan)

        assert r.creditos_aprobados == 6
        assert r.creditos_revalidados == 0
        assert r.promedio == 30.38
        assert r.cantidad_resultados == 20
        assert r.por_resultado == {"APR": 9, "EXO": 1, "ELI": 10}
        assert r.creditos_requeridos == 15

    def test_el_divisor_es_el_de_la_hoja_aunque_de_cero(self):
        """
        F11 = SUM(K)/(SUM(I)-SUM(J)). J resta TODA fila con resultado REV,
        incluso la de tipo REV que I ya no contaba. Con estas tres filas la
        hoja da #DIV/0!; aca, None. Se dejo asi a pedido de bedelia (11/09/2026):
        el numero tiene que ser el mismo que el del Excel.
        """
        filas = [fila("EXA", "APR", 80), fila("CUR", "REV", 0), fila("REV", "REV", 0)]
        r = resumir_plan(filas, HistoricoPlan(codigo="P"))
        assert r.promedio is None
        assert r.creditos_revalidados == 2
        assert r.creditos_aprobados == 2  # el EXA y la fila de tipo REV; la CUR+REV no

    def test_una_revalida_de_cursada_sale_del_divisor(self):
        """El caso normal: la CUR+REV cuenta en I y se resta en J. El promedio es el del examen."""
        filas = [fila("EXA", "APR", 80), fila("CUR", "REV", 0)]
        r = resumir_plan(filas, HistoricoPlan(codigo="P"))
        assert r.promedio == 80.0

    def test_sin_filas_que_promedien(self):
        r = resumir_plan([fila("CUR", "APR", 80)], HistoricoPlan(codigo="P"))
        assert r.promedio is None and r.creditos_aprobados == 0

    def test_materias_aprobadas_sin_repetir(self):
        filas = [fila("EXA", "APR", 70, "M1"), fila("EXA", "APR", 90, "M1"), fila("CUR", "EXO", 90, "M2")]
        r = resumir_plan(filas, HistoricoPlan(codigo="P"))
        assert r.materias_aprobadas == ["M1", "M2"]

    def test_rango_de_fechas(self):
        filas = [fila("EXA", "APR", 70, fecha=date(2010, 3, 1)), fila("EXA", "APR", 70, fecha=None),
                 fila("EXA", "APR", 70, fecha=date(2012, 12, 1))]
        r = resumir_plan(filas, HistoricoPlan(codigo="P"))
        assert (r.primera_fecha, r.ultima_fecha) == (date(2010, 3, 1), date(2012, 12, 1))


class TestNormalizacion:
    def test_redondeo_como_excel(self):
        from v2.services.historico_service import redondear_como_excel
        assert redondear_como_excel(35.125) == 35.13   # round() daria 35.12
        assert redondear_como_excel(30.375) == 30.38
        assert redondear_como_excel(2.5, 0) == 3.0     # round() daria 2

    def test_solo_digitos(self):
        assert solo_digitos("4.257.024-3") == "42570243"
        assert solo_digitos(42570243) == "42570243"
        assert solo_digitos(None) == ""

    def test_texto_busqueda(self):
        assert texto_busqueda("Núñez  Ávila") == "NUNEZ AVILA"
        assert texto_busqueda("DALL'OGLIO RODRÍGUEZ") == "DALL'OGLIO RODRIGUEZ"


# ── Con base ─────────────────────────────────────────────────────────────────

@pytest.fixture(name="historico")
def fixture_historico(session):
    """Dos planes, tres personas (una sin actas), unas cuantas filas."""
    ap = HistoricoPlan(codigo="AP 2011", carrera="Analista Programador", creditos_requeridos=15)
    tsi = HistoricoPlan(codigo="TSI 2011", carrera="Tecnico en Soporte Informatico", creditos_requeridos=17)
    session.add_all([ap, tsi])
    session.flush()

    juan = HistoricoAlumno(cedula="41234567", nombre="PEREZ GOMEZ JUAN", nombre_busqueda="PEREZ GOMEZ JUAN")
    nunez = HistoricoAlumno(cedula="41000001", nombre="NÚÑEZ PÉREZ ANA", nombre_busqueda="NUNEZ PEREZ ANA")
    sin_actas = HistoricoAlumno(cedula="30000009", nombre="SIN ACTAS JUAN", nombre_busqueda="SIN ACTAS JUAN",
                                plan_declarado="TA 2001")
    session.add_all([juan, nunez, sin_actas])
    session.flush()

    session.add_all([
        HistoricoResultado(alumno_id=juan.id, plan_id=tsi.id, materia="REDES LAN", tipo_evaluacion="CUR",
                           resultado="EXO", puntaje=90, puntaje_promedio=90, credito="T", acta="2376",
                           fecha=date(2013, 12, 23), fila_origen=10),
        HistoricoResultado(alumno_id=juan.id, plan_id=tsi.id, materia="REDES WAN", tipo_evaluacion="EXA",
                           resultado="ELI", puntaje=1, puntaje_promedio=0, credito="T", acta="2372",
                           fecha=date(2014, 7, 14), fila_origen=11),
        HistoricoResultado(alumno_id=juan.id, plan_id=ap.id, materia="PROGRAMACION 1", tipo_evaluacion="EXA",
                           resultado="APR", puntaje=70, puntaje_promedio=70, credito="T", acta="2398",
                           fecha=date(2014, 8, 15), fila_origen=12),
        HistoricoResultado(alumno_id=juan.id, plan_id=ap.id, materia="INTRODUCCION AL COMPUTADOR",
                           tipo_evaluacion="CUR", resultado="REV", puntaje=None, puntaje_promedio=0,
                           credito="T", fecha=None, fecha_texto="31/11/2014", fila_origen=13),
        HistoricoResultado(alumno_id=nunez.id, plan_id=ap.id, materia="PROGRAMACION 1", tipo_evaluacion="EXA",
                           resultado="APR", puntaje=95, puntaje_promedio=95, credito="T", acta="2398",
                           fecha=date(2014, 8, 15), fila_origen=14),
    ])
    session.commit()
    return {"ap": ap, "tsi": tsi, "juan": juan, "nunez": nunez, "sin_actas": sin_actas}


class TestLegajo:
    def test_resumen_por_plan_y_filas_ordenadas(self, session, historico):
        legajo = SERVICIO.legajo(session, "41234567")

        assert legajo.alumno.nombre == "PEREZ GOMEZ JUAN"
        assert [p.plan for p in legajo.planes] == ["TSI 2011", "AP 2011"]  # por primera fecha
        tsi = legajo.planes[0]
        assert (tsi.creditos_aprobados, tsi.promedio) == (1, 45.0)   # (90 + 0) / 2
        ap = legajo.planes[1]
        assert ap.creditos_aprobados == 1 and ap.creditos_revalidados == 1
        assert ap.promedio == 70.0   # la revalida sale del divisor

        fechas = [r.fecha for r in legajo.resultados]
        assert fechas[:3] == sorted(f for f in fechas if f)
        assert legajo.resultados[-1].fecha is None and legajo.resultados[-1].fecha_texto == "31/11/2014"

    def test_las_filas_traen_descripciones_y_si_dan_credito(self, session, historico):
        legajo = SERVICIO.legajo(session, "41234567")
        redes = next(r for r in legajo.resultados if r.materia == "REDES LAN")
        assert redes.tipo_evaluacion_descripcion == "Cursada"
        assert redes.resultado_descripcion == "Exonerado"
        assert redes.otorga_credito is True
        assert redes.carrera == "Tecnico en Soporte Informatico"
        assert set(legajo.codigos) == {"tipo_evaluacion", "resultado", "credito"}

    def test_cedula_con_puntos_y_guion(self, session, historico):
        assert SERVICIO.legajo(session, "4.123.456-7").alumno.cedula == "41234567"

    def test_persona_sin_actas_tiene_legajo_vacio(self, session, historico):
        legajo = SERVICIO.legajo(session, "30000009")
        assert legajo.planes == [] and legajo.resultados == []
        assert legajo.alumno.plan_declarado == "TA 2001"

    def test_cedula_desconocida(self, session, historico):
        assert SERVICIO.legajo(session, "99999999") is None

    def test_por_documento_del_usuario(self, session, historico):
        assert SERVICIO.legajo_por_documento(session, "4.123.456-7").alumno.id == historico["juan"].id
        assert SERVICIO.legajo_por_documento(session, None) is None
        assert SERVICIO.legajo_por_documento(session, "pasaporte") is None


class TestBusqueda:
    def test_por_nombre_sin_acentos(self, session, historico):
        assert SERVICIO.buscar_alumnos(session, q="nuñez")["total"] == 1
        assert SERVICIO.buscar_alumnos(session, q="NUNEZ")["total"] == 1
        assert SERVICIO.buscar_alumnos(session, q="perez ana")["total"] == 1

    def test_por_prefijo_de_cedula(self, session, historico):
        r = SERVICIO.buscar_alumnos(session, q="4123")
        assert r["total"] == 1 and r["items"][0].cedula == "41234567"
        assert SERVICIO.buscar_alumnos(session, q="4.123.456-7")["total"] == 1

    def test_el_listado_resume_planes_y_fechas(self, session, historico):
        item = SERVICIO.buscar_alumnos(session, q="GOMEZ")["items"][0]
        assert item.planes == ["AP 2011", "TSI 2011"]
        assert item.cantidad_resultados == 4
        assert (item.primera_fecha, item.ultima_fecha) == (date(2013, 12, 23), date(2014, 8, 15))

    def test_filtro_por_plan(self, session, historico):
        r = SERVICIO.buscar_alumnos(session, plan="tsi 2011")
        assert [i.cedula for i in r["items"]] == ["41234567"]

    def test_solo_con_resultados(self, session, historico):
        assert SERVICIO.buscar_alumnos(session)["total"] == 3
        assert SERVICIO.buscar_alumnos(session, solo_con_resultados=True)["total"] == 2

    def test_paginado(self, session, historico):
        r = SERVICIO.buscar_alumnos(session, limit=2, offset=2)
        assert r["total"] == 3 and len(r["items"]) == 1


class TestCatalogos:
    def test_planes_con_conteos(self, session, historico):
        planes = {p["codigo"]: p for p in SERVICIO.listar_planes(session)}
        assert planes["AP 2011"]["cantidad_alumnos"] == 2
        assert planes["AP 2011"]["cantidad_resultados"] == 3
        assert planes["TSI 2011"]["primera_fecha"] == date(2013, 12, 23)

    def test_materias_por_plan(self, session, historico):
        assert [m["materia"] for m in SERVICIO.listar_materias(session, plan="TSI 2011")] == ["REDES LAN", "REDES WAN"]
        assert next(m for m in SERVICIO.listar_materias(session) if m["materia"] == "PROGRAMACION 1")["cantidad"] == 2


class TestBuscarResultados:
    def test_por_acta(self, session, historico):
        r = SERVICIO.buscar_resultados(session, acta="2398")
        assert r["total"] == 2
        assert {i["alumno"]["cedula"] for i in r["items"]} == {"41234567", "41000001"}

    def test_por_materia_tipo_y_fechas(self, session, historico):
        assert SERVICIO.buscar_resultados(session, materia="redes", tipo_evaluacion="exa")["total"] == 1
        assert SERVICIO.buscar_resultados(session, desde=date(2014, 8, 1), hasta=date(2014, 8, 31))["total"] == 2
        assert SERVICIO.buscar_resultados(session, resultado="ELI")["items"][0]["materia"] == "REDES WAN"

    def test_mas_reciente_primero(self, session, historico):
        fechas = [i["fecha"] for i in SERVICIO.buscar_resultados(session, cedula="41234567")["items"]]
        assert fechas[:3] == sorted((f for f in fechas if f), reverse=True)
        assert fechas[-1] is None


@pytest.fixture(name="cambio_de_plan")
def fixture_cambio_de_plan(session):
    ap20 = HistoricoPlan(codigo="AP 2020", carrera="Analista Programador", creditos_requeridos=15)
    ap22 = HistoricoPlan(codigo="AP 2022", carrera="Analista Programador", creditos_requeridos=15)
    session.add_all([ap20, ap22])
    session.flush()
    a = HistoricoAlumno(cedula="45000001", nombre="GOMEZ RUIZ PEDRO", nombre_busqueda="GOMEZ RUIZ PEDRO")
    session.add(a)
    session.flush()

    def acta(plan, fecha, materia, tipo, resultado, nota, n):
        return HistoricoResultado(alumno_id=a.id, plan_id=plan.id, materia=materia, fecha=fecha,
                                  tipo_evaluacion=tipo, resultado=resultado, puntaje=nota,
                                  puntaje_promedio=nota, fila_origen=n)
    session.add_all([
        acta(ap20, date(2021, 7, 30), "PROGRAMACION 1", "CUR", "ELI", 0, 1),
        acta(ap20, date(2021, 7, 30), "PENSAMIENTO COMPUTACIONAL", "CUR", "EXO", 97, 2),
        acta(ap20, date(2021, 12, 15), "BASES DE DATOS 1", "CUR", "ELI", 0, 3),
        acta(ap20, date(2022, 7, 30), "PROGRAMACION 1", "CUR", "ELI", 0, 4),
        acta(ap22, date(2023, 7, 31), "PROGRAMACION 1", "CUR", "ELI", 0, 5),
        acta(ap22, date(2023, 9, 15), "TALLER DE USABILIDAD", "TALLER", "ELI", 0, 6),
        acta(ap22, date(2026, 7, 7), "PENSAMIENTO COMPUTACIONAL", "CUR", "EXO", 89, 7),
        acta(ap22, date(2026, 7, 20), "PROGRAMACION 1", "CUR", "EXO", 95, 8),
    ])
    session.commit()
    return a


class TestResumenGeneral:
    """
    El certificado de bedelia filtra por documento con CARRERA = (Todas): un
    alumno que cambio de plan promedia todas sus actas juntas. Caso real del
    22/09/2026 (datos cambiados): AP 2020 -> AP 2022, recurso Programacion 1
    tres veces. El Excel da 281 / 8 = 35,125.
    """

    def test_el_general_da_lo_mismo_que_el_certificado(self, session, cambio_de_plan):
        legajo = SERVICIO.legajo(session, "45000001")
        g = legajo.general
        assert g.plan == "(Todas)"
        assert g.cantidad_resultados == 8
        assert g.promedio == 35.13          # 281 / 8 = 35,125: redondeo de Excel, no al par
        assert g.creditos_aprobados == 3     # las tres exoneraciones
        assert g.carrera == "Analista Programador"
        assert g.creditos_requeridos == 15   # del plan del acta mas reciente

    def test_por_plan_sigue_disponible(self, session, cambio_de_plan):
        """Es lo que ve bedelia si filtra CARRERA en el certificado."""
        planes = {p.plan: p for p in SERVICIO.legajo(session, "45000001").planes}
        assert set(planes) == {"AP 2020", "AP 2022"}
        assert planes["AP 2020"].cantidad_resultados + planes["AP 2022"].cantidad_resultados == 8

    def test_cada_recursada_cuenta_en_el_divisor(self, session, cambio_de_plan):
        """Recursar baja el promedio: el 0 suma al divisor. Es la regla del Excel."""
        g = SERVICIO.legajo(session, "45000001").general
        assert g.por_resultado == {"ELI": 5, "EXO": 3}

    def test_carrera_mezclada_queda_sin_carrera(self, session, historico):
        """AP 2011 y TSI 2011 son carreras distintas: el general no inventa una."""
        g = SERVICIO.legajo(session, "41234567").general
        assert g.carrera is None
        assert g.cantidad_resultados == 4

    def test_sin_actas_no_hay_general(self, session, historico):
        assert SERVICIO.legajo(session, "30000009").general is None


class TestPorCarrera:
    """
    Criterio de bedelia (22/09/2026): la escolaridad es por carrera. Si el
    alumno cambio de plan dentro de la misma carrera, se suma; si son dos
    carreras o dos cursos distintos, un promedio para cada una. El Excel no
    podia separar; el legajo si.
    """

    def test_cambio_de_plan_en_la_misma_carrera_se_suma(self, session, cambio_de_plan):
        carreras = SERVICIO.legajo(session, "45000001").carreras
        assert len(carreras) == 1
        c = carreras[0]
        assert c.carrera == "Analista Programador"
        assert c.planes == ["AP 2020", "AP 2022"]
        assert c.promedio == 35.13
        assert c.cantidad_resultados == 8

    def test_carreras_distintas_van_separadas(self, session, historico):
        """AP 2011 y TSI 2011: dos carreras, dos promedios."""
        carreras = {c.carrera: c for c in SERVICIO.legajo(session, "41234567").carreras}
        assert set(carreras) == {"Analista Programador", "Tecnico en Soporte Informatico"}
        assert carreras["Tecnico en Soporte Informatico"].promedio == 45.0    # (90 + 0) / 2
        assert carreras["Analista Programador"].planes == ["AP 2011"]
        # El general sigue mezclando todo, como el Excel
        assert SERVICIO.legajo(session, "41234567").general.cantidad_resultados == 4

    def test_plan_sin_carrera_no_se_mezcla(self, session):
        raro = HistoricoPlan(codigo="PLAN RARO")
        ap = HistoricoPlan(codigo="AP 2022", carrera="Analista Programador", creditos_requeridos=15)
        session.add_all([raro, ap])
        session.flush()
        a = HistoricoAlumno(cedula="46000001", nombre="X", nombre_busqueda="X")
        session.add(a)
        session.flush()
        session.add_all([
            HistoricoResultado(alumno_id=a.id, plan_id=raro.id, materia="M1", tipo_evaluacion="EXA",
                               resultado="APR", puntaje=80, puntaje_promedio=80, fecha=date(2020, 1, 1)),
            HistoricoResultado(alumno_id=a.id, plan_id=ap.id, materia="M2", tipo_evaluacion="EXA",
                               resultado="APR", puntaje=90, puntaje_promedio=90, fecha=date(2021, 1, 1)),
        ])
        session.commit()

        carreras = SERVICIO.legajo(session, "46000001").carreras
        assert [c.carrera for c in carreras] == ["PLAN RARO", "Analista Programador"]
        assert [c.promedio for c in carreras] == [80.0, 90.0]

    def test_los_planes_nocturnos_son_la_misma_carrera(self):
        from v2.scripts.importar_historico import CATALOGO_PLANES
        assert CATALOGO_PLANES["TA 2001 N"][0] == CATALOGO_PLANES["TA 2001"][0]
        assert CATALOGO_PLANES["TA 2016 N"][0] == CATALOGO_PLANES["TA 2016"][0]
