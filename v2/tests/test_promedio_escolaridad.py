"""
Promedio de la escolaridad del portal, con la regla de bedelia (22/09/2026).

Lo que se fija aca:

  - Cuentan todas las actividades rendidas: cada cursada y cada rendicion de
    examen. Eliminado, recursa, inasistencia y ausente suman 0 y cuentan 1.
  - Un examen aprobado cuenta UNA vez, aunque el portal marque tambien la
    cursada como APROBADO con la misma nota.
  - Si el alumno agota los examenes, la cursada no suma otro 0: los ceros son
    de los examenes.
  - El historico (Excel de bedelia) y el portal se suman en un solo cociente,
    por carrera, y la fecha de corte evita contar dos veces lo que la
    planilla de carga trae como "estado de hoy".
"""
import pytest
from datetime import date, datetime
from decimal import Decimal

from v2.models.enums import (
    EstadoInscripcionMateria as EM, EstadoInscripcionExamen as EE, EstadoInstanciaCursado,
)
from v2.models.historico import HistoricoAlumno, HistoricoPlan, HistoricoResultado
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.services import promedio_escolaridad as pe
from v2.services.inscripcion_service import InscripcionMateriaService

CEDULA = "45000001"


# ── Reglas puras ─────────────────────────────────────────────────────────────

def cursada(estado, nota_curso=None, nota_final=None, **extra):
    return InscripcionMateria(alumno_id=1, instancia_cursado_id=1, estado=estado,
                              nota_curso=nota_curso, nota_final=nota_final, **extra)


def rendicion(estado, nota=None):
    return InscripcionExamen(inscripcion_materia_id=1, instancia_examen_id=1, estado=estado,
                             nota_examen=Decimal(str(nota)) if nota is not None else None)


def una(actividades):
    assert len(actividades) == 1
    return actividades[0]


class TestCursadas:
    def test_exonerada_suma_su_nota(self):
        a = una(pe.actividades_de_cursada(cursada(EM.EXONERADO, 90, 90), "PROG 1", None, []))
        assert (a.resultado, a.nota_promedio, a.peso) == ("EXO", 90.0, 1)

    def test_recursa_suma_cero_y_cuenta_uno(self):
        """La regla dura: recursar baja el promedio."""
        a = una(pe.actividades_de_cursada(cursada(EM.REPROBADO, 40), "PROG 1", None, []))
        assert (a.resultado, a.nota_promedio, a.peso) == ("ELI", 0.0, 1)

    def test_inasistencia_es_como_recursa(self):
        a = una(pe.actividades_de_cursada(cursada(EM.PERDIDO_INASISTENCIA, 30), "PROG 1", None, []))
        assert (a.nota_promedio, a.peso) == (0.0, 1)

    def test_a_examen_no_cuenta_todavia(self):
        a = una(pe.actividades_de_cursada(cursada(EM.A_EXAMEN, 75), "PROG 1", None, []))
        assert a.peso == 0 and a.resultado == "APR"

    def test_cursando_no_aparece(self):
        assert pe.actividades_de_cursada(cursada(EM.CURSANDO), "PROG 1", None, []) == []

    def test_revalida_no_promedia(self):
        a = una(pe.actividades_de_cursada(
            cursada(EM.REVALIDADA, motivo_revalida="UTU 2024"), "PROG 1", None, []))
        assert (a.tipo, a.peso, a.detalle) == ("REV", 0, "UTU 2024")

    def test_abandono_no_cuenta_por_defecto(self):
        """A confirmar con bedelia: se deja listado pero fuera del promedio."""
        a = una(pe.actividades_de_cursada(cursada(EM.ABANDONO), "PROG 1", None, []))
        assert a.peso == 0

    def test_taller_se_muestra_como_taller(self):
        a = una(pe.actividades_de_cursada(cursada(EM.EXONERADO, 88), "Taller de Usabilidad", None, []))
        assert a.tipo == "TALLER"


class TestNoContarDosVeces:
    def test_aprobado_por_examen_cuenta_el_examen_no_la_cursada(self):
        """
        Al aprobar el examen el portal pone la cursada en APROBADO con
        nota_final = nota del examen. Si contaran las dos, sumaria doble.
        """
        examenes = [rendicion(EE.APROBADO, 80)]
        c = una(pe.actividades_de_cursada(cursada(EM.APROBADO, 75, 80), "PROG 1", None, examenes))
        e = pe.actividad_de_examen(examenes[0], "PROG 1", None)
        assert c.peso == 0
        assert (e.nota_promedio, e.peso) == (80.0, 1)
        assert pe.promediar([c, e])[0] == 80.0

    def test_aprobado_sin_examen_registrado_cuenta_la_cursada(self):
        """Carga manual: si no se cuenta aca, la materia desaparece del promedio."""
        a = una(pe.actividades_de_cursada(cursada(EM.APROBADO, 75, 82), "PROG 1", None, []))
        assert (a.nota_promedio, a.peso) == (82.0, 1)

    def test_agoto_examenes_los_ceros_son_de_los_examenes(self):
        examenes = [rendicion(EE.REPROBADO, 40), rendicion(EE.AUSENTE), rendicion(EE.REPROBADO, 50)]
        c = una(pe.actividades_de_cursada(cursada(EM.REPROBADO, 75), "PROG 1", None, examenes))
        assert c.peso == 0          # la cursada se habia aprobado
        rend = [pe.actividad_de_examen(e, "PROG 1", None) for e in examenes]
        assert [(r.resultado, r.nota_promedio, r.peso) for r in rend] == [
            ("ELI", 0.0, 1), ("NSP", 0.0, 1), ("ELI", 0.0, 1),
        ]


class TestExamenes:
    def test_eliminado_suma_cero_aunque_tenga_nota(self):
        """En el Excel, el eliminado promedia 0 aunque haya sacado 45."""
        a = pe.actividad_de_examen(rendicion(EE.REPROBADO, 45), "PROG 1", None)
        assert (a.nota, a.nota_promedio, a.peso) == (45.0, 0.0, 1)

    def test_inscripto_y_baja_no_son_actividades(self):
        assert pe.actividad_de_examen(rendicion(EE.INSCRIPTO), "PROG 1", None) is None
        assert pe.actividad_de_examen(rendicion(EE.BAJA), "PROG 1", None) is None


class TestAuxiliares:
    def test_sin_divisor_no_hay_promedio(self):
        assert pe.promediar([])[0] is None

    def test_redondeo_de_excel(self):
        acts = [pe.Actividad(None, "M", "CUR", "EXO", 281, 281.0, 8, "portal")]
        assert pe.promediar(acts)[0] == 35.13

    def test_carrera_por_nombre_sin_acentos(self):
        assert pe.carrera_historica_de("Analista Programador", ["Analista Programador", "X"]) == "Analista Programador"
        assert pe.carrera_historica_de("Técnico en Gerencia", ["Tecnico en Gerencia"]) == "Tecnico en Gerencia"
        assert pe.carrera_historica_de("Otra", ["Analista Programador"]) is None

    def test_fecha_de_cursada(self):
        ic = InstanciaCursado(materia_id=1, anio_lectivo=2026, semestre=1)
        insc = cursada(EM.EXONERADO)
        assert pe.fecha_de_cursada(ic, insc) == date(2026, 7, 31)
        ic.semestre = 2
        assert pe.fecha_de_cursada(ic, insc) == date(2026, 12, 31)
        ic.fecha_fin = datetime(2026, 11, 20)
        assert pe.fecha_de_cursada(ic, insc) == date(2026, 11, 20)


# ── Con base: historico + portal ─────────────────────────────────────────────

@pytest.fixture(name="con_documento")
def fixture_con_documento(session, usuario_estudiante, alumno):
    usuario_estudiante.documento = "4.500.000-1"
    session.add(usuario_estudiante)
    session.commit()
    return alumno


@pytest.fixture(name="historico_joaquin")
def fixture_historico_joaquin(session, programa):
    """
    El caso que trajo bedelia (datos cambiados): AP 2020 -> AP 2022 de la misma
    carrera, recurso Programacion 1 tres veces. Su Excel da 281 / 8 = 35,13.
    La carrera se llama igual que el programa del portal.
    """
    ap20 = HistoricoPlan(codigo="AP 2020", carrera=programa.nombre, creditos_requeridos=15)
    ap22 = HistoricoPlan(codigo="AP 2022", carrera=programa.nombre, creditos_requeridos=15)
    otra = HistoricoPlan(codigo="TA 2016", carrera="Tecnico en Gerencia")
    session.add_all([ap20, ap22, otra])
    session.flush()
    a = HistoricoAlumno(cedula=CEDULA, nombre="GOMEZ RUIZ PEDRO", nombre_busqueda="GOMEZ RUIZ PEDRO")
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
        # Otra carrera: no entra al promedio de este programa
        acta(otra, date(2019, 7, 1), "CONTABILIDAD", "EXA", "APR", 60, 9),
    ])
    session.commit()


def cursar(session, alumno, materia, estado, anio, semestre, nota_curso=None, nota_final=None,
           cerrada=None):
    """`cerrada` es la fecha_cierre que graba el portal; la planilla de carga no la pone."""
    ic = InstanciaCursado(materia_id=materia.id, anio_lectivo=anio, semestre=semestre,
                          estado=EstadoInstanciaCursado.FINALIZADA)
    session.add(ic)
    session.flush()
    insc = InscripcionMateria(alumno_id=alumno.id, instancia_cursado_id=ic.id, estado=estado,
                              nota_curso=nota_curso, nota_final=nota_final, fecha_cierre=cerrada)
    session.add(insc)
    session.commit()
    session.refresh(insc)
    return insc


def rendir(session, insc, materia, fecha, estado, nota=None):
    inst = InstanciaExamen(materia_id=materia.id, nombre=f"Examen {fecha}",
                           fecha_inicio_inscripcion=fecha, fecha_fin_inscripcion=fecha,
                           fecha_examen=fecha, habilitado=True)
    session.add(inst)
    session.flush()
    ie = InscripcionExamen(inscripcion_materia_id=insc.id, instancia_examen_id=inst.id, estado=estado,
                           nota_examen=Decimal(str(nota)) if nota is not None else None)
    session.add(ie)
    session.commit()
    return ie


class TestHistoricoMasPortal:
    def test_solo_historico_da_lo_del_excel(self, session, con_documento, programa, historico_joaquin):
        r = pe.promedio_escolaridad(con_documento.id, programa.id, session)
        assert r.promedio == 35.13
        assert (r.suma_notas, r.divisor) == (281.0, 8)
        assert r.del_historico == 8 and r.del_portal == 0
        assert r.carrera_historica == programa.nombre
        assert r.fecha_corte == date(2026, 7, 20)   # el acta mas reciente

    def test_lo_nuevo_del_portal_se_suma(self, session, con_documento, programa,
                                         historico_joaquin, materias_con_previaturas):
        p2 = materias_con_previaturas["prog2"]
        # Despues del corte: cursa P2 (2026, 2do semestre), llega a examen, pierde uno y aprueba el otro
        insc = cursar(session, con_documento, p2, EM.APROBADO, 2026, 2, nota_curso=75, nota_final=80,
                      cerrada=datetime(2027, 2, 20))
        rendir(session, insc, p2, datetime(2026, 12, 10), EE.REPROBADO, 40)
        rendir(session, insc, p2, datetime(2027, 2, 20), EE.APROBADO, 80)

        r = pe.promedio_escolaridad(con_documento.id, programa.id, session)
        # 281 + 0 + 80 sobre 8 + 2 (la cursada aprobada no cuenta, cuentan los dos examenes)
        assert (r.suma_notas, r.divisor) == (361.0, 10)
        assert r.promedio == 36.1
        assert r.del_portal == 3 and r.actividades_que_cuentan == 10   # 8 del historico + 2 examenes

    def test_la_fila_de_la_planilla_no_cuenta_doble(self, session, con_documento, programa,
                                                    historico_joaquin, materias_con_previaturas):
        """
        La planilla de carga trae P1 como EXONERADA en 2026 1er semestre (su
        ultima cursada). Esa instancia ya esta en el historico. No la cerro el
        portal (sin fecha_cierre), asi que no entra.

        Con fechas por semestre caia el 31/07, despues de la ultima acta del
        Excel (20/07), y se contaba doble. Por eso la regla es "la cerro el
        portal", no "cae despues del corte".
        """
        p1 = materias_con_previaturas["prog1"]
        cursar(session, con_documento, p1, EM.EXONERADO, 2026, 1, nota_curso=95, nota_final=95)

        r = pe.promedio_escolaridad(con_documento.id, programa.id, session)
        assert r.promedio == 35.13 and r.del_portal == 0

    def test_lo_que_la_planilla_trae_cursando_cuenta_cuando_el_portal_lo_cierra(
            self, session, con_documento, programa, historico_joaquin, materias_con_previaturas):
        p2 = materias_con_previaturas["prog2"]
        insc = cursar(session, con_documento, p2, EM.CURSANDO, 2026, 2)
        assert pe.promedio_escolaridad(con_documento.id, programa.id, session).del_portal == 0

        # El portal la califica y la cierra
        insc.estado, insc.nota_curso, insc.nota_final = EM.EXONERADO, Decimal("91"), Decimal("91")
        insc.fecha_cierre = datetime(2026, 12, 5)
        session.add(insc)
        session.commit()

        r = pe.promedio_escolaridad(con_documento.id, programa.id, session)
        assert (r.suma_notas, r.divisor) == (372.0, 9)

    def test_examen_de_una_materia_que_vino_a_examen_de_la_planilla(
            self, session, con_documento, programa, historico_joaquin, materias_con_previaturas):
        """La planilla trae P2 en A_EXAMEN (2025); el alumno rinde en el portal y aprueba."""
        p2 = materias_con_previaturas["prog2"]
        insc = cursar(session, con_documento, p2, EM.A_EXAMEN, 2025, 2, nota_curso=74)
        rendir(session, insc, p2, datetime(2026, 12, 12), EE.APROBADO, 77)
        # el portal, al aprobar, cierra la cursada como APROBADO
        insc.estado, insc.nota_final, insc.fecha_cierre = EM.APROBADO, Decimal("77"), datetime(2026, 12, 12)
        session.add(insc)
        session.commit()

        r = pe.promedio_escolaridad(con_documento.id, programa.id, session)
        assert (r.suma_notas, r.divisor) == (358.0, 9)     # cuenta el examen, una vez

    def test_otra_carrera_no_entra(self, session, con_documento, programa, historico_joaquin):
        r = pe.promedio_escolaridad(con_documento.id, programa.id, session)
        assert all(a.materia != "CONTABILIDAD" for a in r.actividades)

    def test_fecha_de_corte_fijada(self, session, con_documento, programa, historico_joaquin, monkeypatch):
        """Con el corte antes de 2026, las dos actas de 2026 del historico no entran."""
        monkeypatch.setenv("ESCOLARIDAD_FECHA_CORTE", "2025-12-31")
        r = pe.promedio_escolaridad(con_documento.id, programa.id, session)
        assert r.fecha_corte == date(2025, 12, 31)
        assert (r.suma_notas, r.divisor) == (97.0, 6)

    def test_sin_documento_solo_cuenta_el_portal(self, session, alumno, programa, historico_joaquin,
                                                 materias_con_previaturas):
        p2 = materias_con_previaturas["prog2"]
        cursar(session, alumno, p2, EM.EXONERADO, 2027, 1, nota_curso=90, nota_final=90,
               cerrada=datetime(2027, 7, 15))
        r = pe.promedio_escolaridad(alumno.id, programa.id, session)
        assert r.del_historico == 0 and r.promedio == 90.0

    def test_sin_historico_cargado_cuenta_todo_el_portal(self, session, alumno, programa,
                                                         materias_con_previaturas):
        p1 = materias_con_previaturas["prog1"]
        cursar(session, alumno, p1, EM.REPROBADO, 2024, 1, nota_curso=30)
        cursar(session, alumno, p1, EM.EXONERADO, 2025, 1, nota_curso=88, nota_final=88)
        r = pe.promedio_escolaridad(alumno.id, programa.id, session)
        assert r.fecha_corte is None
        assert r.promedio == 44.0     # (0 + 88) / 2


class TestEnLaEscolaridad:
    def test_la_respuesta_trae_el_promedio(self, session, con_documento, programa, historico_joaquin,
                                           materias_con_previaturas):
        esc = InscripcionMateriaService().get_escolaridad(con_documento.id, programa.id, session)
        assert esc["promedio"] == 35.13
        detalle = esc["promedio_detalle"]
        assert detalle["divisor"] == 8
        assert len(detalle["actividades"]) == 8
        assert detalle["actividades"][0]["origen"] == "historico"
        assert {"fecha", "materia", "tipo", "resultado", "nota_promedio", "cuenta_en_promedio"} <= set(
            detalle["actividades"][0])

    def test_sin_nada_el_promedio_es_none(self, session, alumno, programa, materias_con_previaturas):
        esc = InscripcionMateriaService().get_escolaridad(alumno.id, programa.id, session)
        assert esc["promedio"] is None
        assert esc["promedio_detalle"]["actividades"] == []
