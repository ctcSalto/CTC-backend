"""
Planilla de carga inicial: generacion y validacion.

Estos scripts se corren un puñado de veces y despues no se tocan mas, pero
deciden que datos entran al sistema el dia del despliegue. Si el validador deja
pasar algo, el error aparece en produccion con alumnos reales adentro.

El chequeo de cadenas incompletas es el que mas importa: es el que anticipa los
"no me deja inscribirme" del primer dia.
"""
import pytest
from openpyxl import load_workbook

from v2.scripts.generar_planilla_migracion import generar
from v2.scripts.malla_inicial import normalizar
from v2.scripts.validar_planilla_migracion import HOJAS, Validador


@pytest.fixture(name="planilla_vacia")
def fixture_planilla_vacia(tmp_path, session, programa, materias_con_previaturas):
    """
    Genera la planilla contra la base de test.

    `generar` abre su propia sesion con get_db_session, asi que se le pasa la
    del fixture por monkeypatch en el propio modulo.
    """
    from contextlib import contextmanager
    import v2.scripts.generar_planilla_migracion as modulo

    @contextmanager
    def sesion_de_test():
        yield session

    original = modulo.get_db_session
    modulo.get_db_session = sesion_de_test
    try:
        ruta = str(tmp_path / "planilla.xlsx")
        generar(ruta, anio=2026)
    finally:
        modulo.get_db_session = original
    return completar_malla(ruta)


def completar_malla(ruta):
    """
    Rellena semestre y creditos de las filas precargadas desde la malla.

    Es lo primero que hace bedelia: la planilla llega con ~40 materias que solo
    tienen el nombre. Sin esto, todo test que espere cero errores choca contra
    esas filas incompletas, que es justamente lo que el validador debe pedir.
    """
    wb = load_workbook(ruta)
    ws = wb[HOJAS["plan"]]
    for fila in range(3, ws.max_row + 1):
        if ws.cell(row=fila, column=3).value is None:
            continue
        if ws.cell(row=fila, column=4).value is None:
            ws.cell(row=fila, column=4, value=1)
        if ws.cell(row=fila, column=5).value is None:
            ws.cell(row=fila, column=5, value=10)
    wb.save(ruta)
    return ruta


def escribir(ruta, hoja, filas, desde=3):
    """Escribe filas en una hoja, desde la primera fila de datos."""
    wb = load_workbook(ruta)
    ws = wb[hoja]
    for indice, fila in enumerate(filas, start=desde):
        for columna, valor in enumerate(fila, start=1):
            ws.cell(row=indice, column=columna, value=valor)
    wb.save(ruta)
    return ruta


def problemas_de(ruta):
    validador = Validador(ruta)
    problemas = validador.correr()
    return (
        [p for p in problemas if p.nivel == "ERROR"],
        [p for p in problemas if p.nivel == "AVISO"],
    )


class TestGeneracion:
    def test_tiene_todas_las_hojas(self, planilla_vacia):
        wb = load_workbook(planilla_vacia)
        for nombre in HOJAS.values():
            assert nombre in wb.sheetnames
        assert "LEEME" in wb.sheetnames

    def test_precarga_las_materias_que_ya_existen(self, planilla_vacia):
        """Bedelia no tiene que tipear lo que el sistema ya sabe."""
        wb = load_workbook(planilla_vacia)
        ws = wb[HOJAS["plan"]]
        codigos = {
            ws.cell(row=fila, column=2).value
            for fila in range(3, ws.max_row + 1)
        }
        assert {"P1_T", "P2_T", "P3_T"} <= codigos

    def test_precarga_las_previaturas(self, planilla_vacia):
        wb = load_workbook(planilla_vacia)
        ws = wb[HOJAS["previaturas"]]
        pares = {
            (ws.cell(row=fila, column=2).value, ws.cell(row=fila, column=3).value)
            for fila in range(3, ws.max_row + 1)
        }
        assert ("P2_T", "P1_T") in pares
        assert ("P3_T", "P2_T") in pares

    def test_el_estado_del_historial_es_desplegable(self, planilla_vacia):
        """Sin lista cerrada, la columna vuelve con diez formas de decir aprobado."""
        wb = load_workbook(planilla_vacia)
        ws = wb[HOJAS["historial"]]
        formulas = [dv.formula1 for dv in ws.data_validations.dataValidation]
        assert any("APROBADA" in f and "A_EXAMEN" in f for f in formulas)


class TestMallaPrecargada:
    """
    Las 44 previaturas ya estaban definidas en el repo desde mayo, en la
    migracion seed_previaturas, pero esa migracion no inserto nada: resolvia las
    materias por nombre exacto contra una tabla vacia. Se precargan en la
    planilla para no pedirle a bedelia que las tipee de nuevo.
    """

    def test_las_materias_de_la_malla_estan_en_el_plan(self, planilla_vacia):
        from v2.scripts.malla_inicial import materias_por_programa

        wb = load_workbook(planilla_vacia)
        ws = wb[HOJAS["plan"]]
        nombres = {
            normalizar(str(ws.cell(row=fila, column=3).value or ""))
            for fila in range(3, ws.max_row + 1)
        }

        esperadas = materias_por_programa()["Analista Programador"]
        faltantes = [n for n in esperadas if normalizar(n) not in nombres]
        assert faltantes == [], faltantes

    def test_las_previaturas_de_la_malla_estan_cargadas(self, planilla_vacia):
        from v2.scripts.malla_inicial import previaturas_por_programa

        wb = load_workbook(planilla_vacia)
        ws = wb[HOJAS["previaturas"]]
        pares = {
            (normalizar(str(ws.cell(row=fila, column=2).value or "")),
             normalizar(str(ws.cell(row=fila, column=3).value or "")))
            for fila in range(3, ws.max_row + 1)
        }

        for programa, esperados in previaturas_por_programa().items():
            for materia, previa in esperados:
                assert (normalizar(materia), normalizar(previa)) in pares, \
                    f"falta {materia} -> {previa} de {programa}"

    def test_la_planilla_recien_generada_pide_semestre_y_creditos(
        self, tmp_path, session, programa, materias_con_previaturas
    ):
        """Sin completar, el validador tiene que reclamar las filas de la malla."""
        from contextlib import contextmanager
        import v2.scripts.generar_planilla_migracion as modulo

        @contextmanager
        def sesion_de_test():
            yield session

        original = modulo.get_db_session
        modulo.get_db_session = sesion_de_test
        try:
            ruta = str(tmp_path / "sin_completar.xlsx")
            generar(ruta, anio=2026)
        finally:
            modulo.get_db_session = original

        errores, _ = problemas_de(ruta)
        reclamos = [e for e in errores if "sin completar" in str(e)]
        assert len(reclamos) == 1, [str(e) for e in errores]
        assert "semestre" in str(reclamos[0])

    def test_previaturas_por_nombre_se_resuelven(self, planilla_vacia, programa):
        """
        La malla viene con nombres, no con codigos: los codigos se decidieron
        despues. La hoja tiene que aceptar las dos formas.
        """
        errores, _ = problemas_de(planilla_vacia)
        assert not [e for e in errores if "Previaturas" in str(e)], \
            [str(e) for e in errores]

    def test_historial_acepta_el_nombre_de_la_materia(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["alumnos"], [
            ("41234567", "Perez", "Ana", None, None, None, None,
             programa.nombre, 2023, "ACTIVA", None)
        ])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "Programacion 1", "APROBADA", 78, 2024, 1, None),
        ])

        errores, _ = problemas_de(planilla_vacia)
        assert errores == [], [str(e) for e in errores]


class TestValidacion:
    def _alumno(self, documento="41234567", programa="Ingenieria de Test"):
        return (documento, "Perez", "Ana", None, None, None, None,
                programa, 2023, "ACTIVA", None)

    def test_planilla_bien_llena_no_da_errores(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa=programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "APROBADA", 78, 2024, 1, None),
            ("41234567", programa.nombre, "P2_T", "CURSANDO", None, 2026, 1, None),
        ])

        errores, _ = problemas_de(planilla_vacia)
        assert errores == [], [str(e) for e in errores]

    def test_documento_con_puntos_se_normaliza(self, planilla_vacia, programa):
        """Bedelia escribe 4.123.456-7 y el sistema tiene que entenderlo."""
        escribir(planilla_vacia, HOJAS["alumnos"], [
            self._alumno("4.123.456-7", programa.nombre)
        ])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "APROBADA", 78, 2024, 1, None),
        ])

        errores, _ = problemas_de(planilla_vacia)
        assert errores == [], [str(e) for e in errores]

    def test_alumno_del_historial_sin_ficha(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa=programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("99999999", programa.nombre, "P1_T", "APROBADA", 78, 2024, 1, None),
        ])

        errores, _ = problemas_de(planilla_vacia)
        assert any("99999999" in str(e) for e in errores)

    def test_materia_inexistente(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa=programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "NO_EXISTE", "APROBADA", 78, 2024, 1, None),
        ])

        errores, _ = problemas_de(planilla_vacia)
        assert any("NO_EXISTE" in str(e) for e in errores)

    def test_una_fila_identica_es_aviso(self, planilla_vacia, programa):
        """Misma materia, mismo año y mismo estado dos veces: probablemente copiada de mas."""
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa=programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "APROBADA", 78, 2024, 1, None),
            ("41234567", programa.nombre, "P1_T", "APROBADA", 78, 2024, 1, None),
        ])

        errores, avisos = problemas_de(planilla_vacia)
        assert errores == [], [str(e) for e in errores]
        assert any("Repite la fila" in str(a) for a in avisos)

    def test_estado_fuera_del_vocabulario(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa=programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "aprobo", 78, 2024, 1, None),
        ])

        errores, _ = problemas_de(planilla_vacia)
        assert any("APROBADA" in str(e) for e in errores)

    def test_nota_fuera_de_rango(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa=programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "APROBADA", 150, 2024, 1, None),
        ])

        errores, _ = problemas_de(planilla_vacia)
        assert any("150" in str(e) for e in errores)

    def test_programa_que_no_esta_en_el_plan(self, planilla_vacia):
        escribir(planilla_vacia, HOJAS["alumnos"], [
            self._alumno(programa="Carrera Que No Existe")
        ])

        errores, _ = problemas_de(planilla_vacia)
        assert any("Carrera Que No Existe" in str(e) for e in errores)

    def test_ciclo_de_previaturas(self, planilla_vacia, programa):
        """P1 requiere P3 cierra el circulo con las precargadas."""
        wb = load_workbook(planilla_vacia)
        ws = wb[HOJAS["previaturas"]]
        fila = ws.max_row + 1
        for columna, valor in enumerate(
            (programa.nombre, "P1_T", "P3_T", "APROBADA", None), start=1
        ):
            ws.cell(row=fila, column=columna, value=valor)
        wb.save(planilla_vacia)

        errores, _ = problemas_de(planilla_vacia)
        assert any("Ciclo de previaturas" in str(e) for e in errores)


class TestCadenasIncompletas:
    """
    El chequeo que anticipa los reclamos del dia uno: si falta el historial
    viejo, el portal bloquea inscripciones que en realidad corresponden.
    """

    def _alumno(self, programa):
        return ("41234567", "Perez", "Ana", None, None, None, None,
                programa, 2023, "ACTIVA", None)

    def test_avisa_si_falta_la_previatura(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa.nombre)])
        # P2 aprobada, pero P1 (su previatura) no figura
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P2_T", "APROBADA", 78, 2024, 1, None),
        ])

        errores, avisos = problemas_de(planilla_vacia)
        assert errores == [], [str(e) for e in errores]
        assert any("P1_T" in str(a) and "no figura" in str(a) for a in avisos)

    def test_avisa_si_la_previatura_esta_pero_sin_aprobar(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "RECURSA", 40, 2023, 1, None),
            ("41234567", programa.nombre, "P2_T", "APROBADA", 78, 2024, 1, None),
        ])

        errores, avisos = problemas_de(planilla_vacia)
        assert errores == []
        assert any("P1_T" in str(a) and "RECURSA" in str(a) for a in avisos)

    def test_cadena_completa_no_avisa(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "APROBADA", 78, 2023, 1, None),
            ("41234567", programa.nombre, "P2_T", "EXONERADA", 90, 2024, 1, None),
            ("41234567", programa.nombre, "P3_T", "CURSANDO", None, 2026, 1, None),
        ])

        errores, avisos = problemas_de(planilla_vacia)
        assert errores == []
        assert not [a for a in avisos if "previatura" in str(a)], [str(a) for a in avisos]

    def test_exonerada_cuenta_como_tenida(self, planilla_vacia, programa):
        """Exonerar es aprobar sin examen: no puede pedir la previa de nuevo."""
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "EXONERADA", 95, 2023, 1, None),
            ("41234567", programa.nombre, "P2_T", "APROBADA", 78, 2024, 1, None),
        ])

        _, avisos = problemas_de(planilla_vacia)
        assert not [a for a in avisos if "previatura" in str(a)]

    def test_a_examen_no_cuenta_como_tenida(self, planilla_vacia, programa):
        """Tener derecho a examen no es tener la materia."""
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "A_EXAMEN", 72, 2023, 1, None),
            ("41234567", programa.nombre, "P2_T", "APROBADA", 78, 2024, 1, None),
        ])

        _, avisos = problemas_de(planilla_vacia)
        assert any("P1_T" in str(a) and "A_EXAMEN" in str(a) for a in avisos)


class TestRevalida:
    """
    Agregada el 22/09/2026: bedelia tiene alumnos con materias por reválida y
    la planilla no tenia como decirlo. En el portal es REVALIDADA y cuenta como
    materia cumplida para las previaturas.
    """

    def _alumno(self, programa):
        return ("41234567", "Perez", "Ana", None, None, None, None,
                programa, 2023, "ACTIVA", None)

    def test_revalidada_cuenta_como_tenida(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "REVALIDADA", None, 2023, 1, "Equivalencia UTU"),
            ("41234567", programa.nombre, "P2_T", "APROBADA", 78, 2024, 1, None),
        ])

        errores, avisos = problemas_de(planilla_vacia)
        assert errores == [], [str(e) for e in errores]
        assert not [a for a in avisos if "previatura" in str(a)]

    @pytest.mark.parametrize("escrito", ["REVALIDA", "Revalida", "Reválida", "revalidada"])
    def test_acepta_como_lo_escribe_bedelia(self, planilla_vacia, programa, escrito):
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", escrito, None, 2023, 1, None),
        ])

        errores, _ = problemas_de(planilla_vacia)
        assert errores == [], [str(e) for e in errores]

    def test_varias_cursadas_de_la_misma_materia(self, planilla_vacia, programa):
        """
        Bedelia cargo todas las cursadas, no solo la de hoy (planilla del
        25/09/2026). Se aceptan, y el estado actual es el de la mas reciente:
        recurso P1 en 2023 y la aprobo en 2024, asi que P2 no queda sin previa.
        """
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "RECURSA", 40, 2023, 1, None),
            ("41234567", programa.nombre, "P1_T", "APROBADA", 80, 2024, 1, None),
            ("41234567", programa.nombre, "P2_T", "APROBADA", 75, 2025, 2, None),
        ])

        errores, avisos = problemas_de(planilla_vacia)
        assert errores == [], [str(e) for e in errores]
        assert not [a for a in avisos if "previatura" in str(a)], [str(a) for a in avisos]

    def test_gana_la_mas_reciente_aunque_este_arriba(self, planilla_vacia, programa):
        """El orden de las filas no importa: manda el año."""
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "RECURSA", 40, 2025, 1, None),
            ("41234567", programa.nombre, "P1_T", "APROBADA", 80, 2023, 1, None),
            ("41234567", programa.nombre, "P2_T", "APROBADA", 75, 2025, 2, None),
        ])

        _, avisos = problemas_de(planilla_vacia)
        assert any("P1_T" in str(a) and "RECURSA" in str(a) for a in avisos)


# ══════════════════════════════════════════════════════════════════════════════
# Lo que agrego administracion en la planilla real (25/09/2026)
# ══════════════════════════════════════════════════════════════════════════════

ENCABEZADO_ALUMNOS_CON_OTRO = [
    "DOCUMENTO*", "Apellido*", "Nombre*", "Email institucional", "Email personal", "Telefono",
    "Fecha nacimiento (dd/mm/aaaa)", "Programa*", "Año de ingreso*", "Estado en la carrera*",
    "Observaciones", "Otro Programa*", "Estado en la carrera*",
]
ENCABEZADO_DICTADO_DOS_DOCENTES = [
    "Programa*", "Materia* (codigo o nombre)", "Año*", "Semestre* (1 o 2)",
    "DOCUMENTO del docente*", "Rol*", None, "Rol*", "Horario", "Salon", "Cupo maximo", "Observaciones",
]


class TestColumnasAgregadas:
    def _alumno(self, programa, otro=None, estado_otro=None, email=None):
        return ("41234567", "Perez", "Ana", email, None, None, None,
                programa, 2023, "ACTIVA", None, otro, estado_otro)

    def _segunda_carrera(self, session, politica_base100):
        """Un segundo programa con una materia, cargado en el plan de estudios."""
        from v2.models.programa import Programa
        from v2.models.materia import Materia
        from v2.models.enums import TipoPrograma, AreaPrograma
        otro = Programa(nombre="Excel y Power BI", tipo=TipoPrograma.CURSO_CORTO,
                        area=AreaPrograma.INFORMATICA, duracion_semestres=1, activo=True)
        session.add(otro)
        session.flush()
        session.add(Materia(programa_id=otro.id, nombre="Power BI", codigo="PBI", semestre=1,
                            creditos=1, politica_id=politica_base100.id, activo=True))
        session.commit()
        return otro

    def test_otro_programa_cuenta_como_inscripcion(self, tmp_path, session, programa,
                                                    materias_con_previaturas, politica_base100, monkeypatch):
        otro = self._segunda_carrera(session, politica_base100)
        from contextlib import contextmanager
        import v2.scripts.generar_planilla_migracion as modulo

        @contextmanager
        def sesion_de_test():
            yield session
        monkeypatch.setattr(modulo, "get_db_session", sesion_de_test)
        ruta = completar_malla(generar(str(tmp_path / "p.xlsx"), 2026))

        escribir(ruta, HOJAS["alumnos"], [ENCABEZADO_ALUMNOS_CON_OTRO], desde=2)
        escribir(ruta, HOJAS["alumnos"], [self._alumno(programa.nombre, otro.nombre, "COMPLETADA")])
        escribir(ruta, HOJAS["historial"], [
            ("41234567", otro.nombre, "PBI", "APROBADA", 90, 2024, 1, None),
        ])

        errores, avisos = problemas_de(ruta)
        assert errores == [], [str(e) for e in errores]
        assert any("segundo programa" in str(a) for a in avisos)

    def test_programa_con_tipeo_sugiere_el_correcto(self, planilla_vacia, programa):
        mal = programa.nombre.replace("Programador", "Programdor")
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(mal)])
        errores, _ = problemas_de(planilla_vacia)
        assert any(f"¿Es '{programa.nombre}'?" in str(e) for e in errores), [str(e) for e in errores]

    def test_guiones_son_vacio(self, planilla_vacia, programa):
        """Bedelia pone '--' donde no hay mail."""
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa.nombre, email="--")])
        errores, _ = problemas_de(planilla_vacia)
        assert not [e for e in errores if "email" in str(e).lower()]

    def test_cuenta_de_prueba_sin_cedula(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["alumnos"], [
            (None, "Ejemplo", "Estudiante", "estudiante.ejemplo@ctcsalto.edu.uy", None, None, None,
             programa.nombre, 2023, "ACTIVA", None),
        ])
        errores, _ = problemas_de(planilla_vacia)
        assert any("cuenta de prueba" in str(e) for e in errores)

    def test_semestre_del_plan_en_el_historial(self, planilla_vacia, programa):
        """Bedelia puso el semestre del plan (3, 1.5...) y no el del año: se acepta."""
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa.nombre)])
        escribir(planilla_vacia, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "APROBADA", 78, 2024, 3, None),
            ("41234567", programa.nombre, "P2_T", "CURSANDO", None, 2026, 1.5, None),
        ])
        errores, _ = problemas_de(planilla_vacia)
        assert errores == [], [str(e) for e in errores]

    def test_segundo_docente_no_corre_las_columnas(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["alumnos"], [self._alumno(programa.nombre)])
        escribir(planilla_vacia, HOJAS["docentes"], [
            ("30000001", "Uno", "Docente", None, None, None, "SI", None),
            ("30000002", "Dos", "Docente", None, None, None, "SI", None),
        ])
        escribir(planilla_vacia, HOJAS["dictado"], [ENCABEZADO_DICTADO_DOS_DOCENTES], desde=2)
        escribir(planilla_vacia, HOJAS["dictado"], [
            (programa.nombre, "P1_T", 2026, 1, "30000001", "TITULAR", "30000002", "TITULAR",
             "18:00 a 21:00", "Laboratorio 1", 25, None),
        ])
        errores, _ = problemas_de(planilla_vacia)
        assert errores == [], [str(e) for e in errores]

    def test_segundo_docente_desconocido_es_error(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["docentes"], [("30000001", "Uno", "Docente", None, None, None, "SI", None)])
        escribir(planilla_vacia, HOJAS["dictado"], [ENCABEZADO_DICTADO_DOS_DOCENTES], desde=2)
        escribir(planilla_vacia, HOJAS["dictado"], [
            (programa.nombre, "P1_T", 2026, 1, "30000001", "TITULAR", "39999999", "TITULAR",
             None, None, None, None),
        ])
        errores, _ = problemas_de(planilla_vacia)
        assert any("39999999" in str(e) and "segundo docente" in str(e) for e in errores)

    def test_dictado_sin_docente_es_aviso(self, planilla_vacia, programa):
        escribir(planilla_vacia, HOJAS["dictado"], [
            (programa.nombre, "P1_T", 2026, 1, None, None, None, None, None, None),
        ])
        errores, avisos = problemas_de(planilla_vacia)
        assert not [e for e in errores if "docente" in str(e)], [str(e) for e in errores]
        assert any("Sin docente asignado" in str(a) for a in avisos)

    def test_curso_corto_con_nc_y_guiones(self, planilla_vacia, programa):
        """En el plan, los cursos cortos traen semestre 'NC' y creditos '--': no faltan."""
        from openpyxl import load_workbook
        wb = load_workbook(planilla_vacia)
        ws = wb[HOJAS["plan"]]
        ultima = ws.max_row + 1
        for col, valor in enumerate([programa.nombre, "CC1", "Curso corto de prueba", "NC", "--", "SI"], start=1):
            ws.cell(row=ultima, column=col, value=valor)
        wb.save(planilla_vacia)
        completar_malla(planilla_vacia)

        errores, _ = problemas_de(planilla_vacia)
        assert not [e for e in errores if "Curso corto de prueba" in str(e) or "CC1" in str(e)], \
            [str(e) for e in errores]

    def test_misma_materia_en_dos_planes_no_es_repetida(self, planilla_vacia, programa):
        from openpyxl import load_workbook
        wb = load_workbook(planilla_vacia)
        ws = wb[HOJAS["plan"]]
        ws.cell(row=2, column=8, value="Plan")
        filas = [r for r in range(3, ws.max_row + 1) if ws.cell(row=r, column=3).value]
        for r in filas:
            ws.cell(row=r, column=8, value=2022)
        # la misma primera materia, ahora del plan 2011
        ultima = ws.max_row + 1
        for col in range(1, 8):
            ws.cell(row=ultima, column=col, value=ws.cell(row=filas[0], column=col).value)
        # sin codigo, para que se busque por nombre. Ojo: ws.cell(..., value=None) no
        # borra la celda en openpyxl, hay que asignar .value
        ws.cell(row=ultima, column=2).value = None
        ws.cell(row=ultima, column=8, value=2011)
        wb.save(planilla_vacia)
        completar_malla(planilla_vacia)

        errores, avisos = problemas_de(planilla_vacia)
        assert not [e for e in errores if "no se puede repetir" in str(e)], [str(e) for e in errores]
        assert any("planes" in str(a) and "2011" in str(a) and "2022" in str(a) for a in avisos),             [str(a) for a in avisos]


# ══════════════════════════════════════════════════════════════════════════════
# Cada plan es un programa aparte: cada alumno tiene que decir su plan
# ══════════════════════════════════════════════════════════════════════════════

class TestPlanDelAlumno:
    """
    Decidido el 25/09/2026: cada plan de una carrera es un programa aparte.
    En la planilla real, de 52 alumnos de carreras con varios planes, en 39 no
    habia forma de saber el plan: lo tiene que decir bedelia.
    """

    @pytest.fixture(name="dos_planes")
    def fixture_dos_planes(self, planilla_vacia, programa):
        """El programa de test con sus materias en el plan 2022, y P1 y una 'Algoritmos 1' en el 2011."""
        wb = load_workbook(planilla_vacia)
        ws = wb[HOJAS["plan"]]
        ws.cell(row=2, column=8, value="Plan")
        propias = [r for r in range(3, ws.max_row + 1) if ws.cell(row=r, column=1).value == programa.nombre]
        for r in propias:
            ws.cell(row=r, column=8, value=2022)
        ultima = ws.max_row + 1
        for col, valor in enumerate([programa.nombre, None, "Programacion 1", 1, 10, "NO", None, 2011], start=1):
            ws.cell(row=ultima, column=col, value=valor)
        for col, valor in enumerate([programa.nombre, None, "Algoritmos 1", 1, 10, "NO", None, 2011], start=1):
            ws.cell(row=ultima + 1, column=col, value=valor)
        wb.save(planilla_vacia)
        completar_malla(planilla_vacia)
        return planilla_vacia

    def _con_plan(self, ruta, programa, plan):
        encabezado = list(ENCABEZADO_ALUMNOS_CON_OTRO) + ["Plan"]
        escribir(ruta, HOJAS["alumnos"], [encabezado], desde=2)
        escribir(ruta, HOJAS["alumnos"], [
            ("41234567", "Perez", "Ana", None, None, None, None, programa, 2015, "ACTIVA",
             None, None, None, plan),
        ])

    def test_sin_plan_va_al_mas_reciente(self, dos_planes, programa):
        """
        Bedelia (25/09/2026): los alumnos actuales estan todos en el plan
        vigente, aunque hayan empezado en uno viejo. Sin plan, el mas reciente.
        """
        escribir(dos_planes, HOJAS["alumnos"], [
            ("41234567", "Perez", "Ana", None, None, None, None, programa.nombre, 2015, "ACTIVA", None),
        ])
        escribir(dos_planes, HOJAS["historial"], [
            ("41234567", programa.nombre, "P1_T", "APROBADA", 75, 2025, 1, None),
        ])
        errores, avisos = problemas_de(dos_planes)
        assert errores == [], [str(e) for e in errores]
        assert any("no dicen el plan" in str(a) and "(2022)" in str(a) for a in avisos), \
            [str(a) for a in avisos]

    def test_con_la_columna_plan(self, dos_planes, programa):
        self._con_plan(dos_planes, programa.nombre, 2011)
        errores, _ = problemas_de(dos_planes)
        assert not [e for e in errores if "plan" in str(e).lower()], [str(e) for e in errores]

    def test_con_el_plan_en_el_nombre(self, dos_planes, programa):
        escribir(dos_planes, HOJAS["alumnos"], [
            ("41234567", "Perez", "Ana", None, None, None, None,
             f"{programa.nombre} (Plan 2011)", 2015, "ACTIVA", None),
        ])
        errores, _ = problemas_de(dos_planes)
        assert not [e for e in errores if "plan" in str(e).lower()], [str(e) for e in errores]

    def test_plan_que_no_existe(self, dos_planes, programa):
        self._con_plan(dos_planes, programa.nombre, 2019)
        errores, _ = problemas_de(dos_planes)
        assert any("El plan 2019 no esta" in str(e) for e in errores)

    def test_la_materia_se_busca_en_el_plan_del_alumno(self, dos_planes, programa):
        """'Algoritmos 1' solo existe en el 2011: para un alumno del 2011 se encuentra sin aviso."""
        self._con_plan(dos_planes, programa.nombre, 2011)
        escribir(dos_planes, HOJAS["historial"], [
            ("41234567", programa.nombre, "Algoritmos 1", "APROBADA", 80, 2012, 1, None),
            ("41234567", programa.nombre, "Programacion 1", "APROBADA", 75, 2012, 1, None),
        ])
        errores, avisos = problemas_de(dos_planes)
        assert errores == [], [str(e) for e in errores]
        assert not [a for a in avisos if "no esta en el plan" in str(a)], [str(a) for a in avisos]

    def test_materia_de_otro_plan_es_aviso(self, dos_planes, programa):
        """Alumno del 2022 con una materia que solo esta en el 2011: se toma, pero se avisa."""
        self._con_plan(dos_planes, programa.nombre, 2022)
        escribir(dos_planes, HOJAS["historial"], [
            ("41234567", programa.nombre, "Algoritmos 1", "APROBADA", 80, 2012, 1, None),
        ])
        errores, avisos = problemas_de(dos_planes)
        assert errores == [], [str(e) for e in errores]
        assert any("no esta en el plan 2022" in str(a) and "2011" in str(a) for a in avisos)

    def test_observaciones_dicen_el_plan_de_la_fila(self, dos_planes, programa):
        """Cambio de plan: la fila vieja dice 'Plan 2011' en Observaciones y no se avisa."""
        self._con_plan(dos_planes, programa.nombre, 2022)
        escribir(dos_planes, HOJAS["historial"], [
            ("41234567", programa.nombre, "Algoritmos 1", "APROBADA", 80, 2012, 1,
             "Analista Programador - Plan 2011"),
        ])
        errores, avisos = problemas_de(dos_planes)
        assert errores == [], [str(e) for e in errores]
        assert not [a for a in avisos if "no esta en el plan" in str(a)], [str(a) for a in avisos]
