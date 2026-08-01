"""
Tests de las consultas de disponibilidad del semestre activo y del historico
del docente.

Cubre:
- get_materias_habilitadas: periodo activo, semestre, previaturas, cupo, estado
  de la instancia y materias ya obtenidas
- get_examenes_habilitados: estado A_EXAMEN, plazo, politica y oportunidades
- get_historico_materias / get_historico_examenes: historico del profesor
- Profesor.activo
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.docente_instancia_examen import DocenteInstanciaExamen
from v2.models.politica_examen import PoliticaExamen
from v2.models.periodo_inscripcion_materia import PeriodoInscripcionMateria
from v2.models.profesor import Profesor
from v2.models.docente_materia import DocenteMateria
from v2.models.enums import (
    EstadoInscripcionMateria, EstadoInstanciaCursado,
    EstadoInscripcionExamen, RolDocente,
)
from v2.services.inscripcion_service import InscripcionMateriaService
from v2.services.inscripcion_examen_service import InscripcionExamenService
from v2.services.docente_materia_service import DocenteMateriaService


def tz():
    return ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo"))


def crear_periodo(session, programa, semestre=None, anio_lectivo=2026, abierto=True):
    ahora = datetime.now(tz())
    if abierto:
        inicio, fin = ahora - timedelta(days=10), ahora + timedelta(days=10)
    else:
        inicio, fin = ahora - timedelta(days=60), ahora - timedelta(days=30)
    periodo = PeriodoInscripcionMateria(
        programa_id=programa.id,
        anio_lectivo=anio_lectivo,
        semestre=semestre,
        fecha_inicio=inicio,
        fecha_fin=fin,
        habilitado=True,
    )
    session.add(periodo)
    session.commit()
    session.refresh(periodo)
    return periodo


def crear_instancia(session, materia, anio_lectivo=2026, semestre=None,
                    estado=EstadoInstanciaCursado.PLANIFICADA, cupo_maximo=None):
    ic = InstanciaCursado(
        materia_id=materia.id,
        anio_lectivo=anio_lectivo,
        semestre=semestre,
        estado=estado,
        cupo_maximo=cupo_maximo,
    )
    session.add(ic)
    session.commit()
    session.refresh(ic)
    return ic


def crear_instancia_examen(session, materia, abierta=True):
    ahora = datetime.now(tz()).replace(tzinfo=None)
    if abierta:
        inicio, fin = ahora - timedelta(days=5), ahora + timedelta(days=5)
    else:
        inicio, fin = ahora - timedelta(days=30), ahora - timedelta(days=20)
    inst = InstanciaExamen(
        materia_id=materia.id,
        nombre=f"Examen {materia.nombre}",
        fecha_inicio_inscripcion=inicio,
        fecha_fin_inscripcion=fin,
        fecha_examen=ahora + timedelta(days=15),
        habilitado=True,
    )
    session.add(inst)
    session.commit()
    session.refresh(inst)
    return inst


def nombres(materias):
    return {m["nombre"] for m in materias}


# ══════════════════════════════════════════════════════════════════════════════
# Materias habilitadas
# ══════════════════════════════════════════════════════════════════════════════

class TestMateriasHabilitadas:

    def test_sin_periodo_abierto_no_hay_nada_habilitado(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Sin periodo de inscripcion abierto se informa el motivo, no una lista vacia muda."""
        crear_instancia(session, materias_con_previaturas["prog1"])
        crear_periodo(session, programa, abierto=False)

        res = InscripcionMateriaService().get_materias_habilitadas(
            alumno.id, programa.id, session
        )

        assert res["periodo_inscripcion"] == {"abierto": False}
        assert res["materias"] == []

    def test_materia_sin_previaturas_es_inscribible(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """P1 no tiene previaturas: con instancia y periodo abierto se puede inscribir."""
        crear_periodo(session, programa)
        ic = crear_instancia(session, materias_con_previaturas["prog1"])

        res = InscripcionMateriaService().get_materias_habilitadas(
            alumno.id, programa.id, session
        )

        assert res["periodo_inscripcion"]["abierto"] is True
        assert res["periodo_inscripcion"]["anio_lectivo"] == 2026
        assert len(res["materias"]) == 1
        mat = res["materias"][0]
        assert mat["nombre"] == "Programacion 1"
        assert mat["instancia_cursado_id"] == ic.id
        assert mat["puede_inscribirse"] is True
        assert mat["motivos"] == []

    def test_previaturas_faltantes_bloquean(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """P2 requiere P1 aprobada: aparece listada pero no inscribible."""
        crear_periodo(session, programa)
        crear_instancia(session, materias_con_previaturas["prog2"])

        res = InscripcionMateriaService().get_materias_habilitadas(
            alumno.id, programa.id, session
        )

        mat = res["materias"][0]
        assert mat["nombre"] == "Programacion 2"
        assert mat["puede_inscribirse"] is False
        assert any("Programacion 1" in m for m in mat["previaturas_faltantes"])
        assert mat["motivos"] == mat["previaturas_faltantes"]

    def test_instancia_cancelada_no_se_ofrece(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Una instancia CANCELADA o FINALIZADA no cuenta como oferta."""
        crear_periodo(session, programa)
        crear_instancia(
            session, materias_con_previaturas["prog1"],
            estado=EstadoInstanciaCursado.CANCELADA,
        )
        crear_instancia(
            session, materias_con_previaturas["prog2"],
            estado=EstadoInstanciaCursado.FINALIZADA,
        )

        res = InscripcionMateriaService().get_materias_habilitadas(
            alumno.id, programa.id, session
        )

        assert res["materias"] == []

    def test_cupo_lleno_bloquea_con_motivo(
        self, session, alumno, otro_alumno, programa, materias_con_previaturas
    ):
        """Con el cupo agotado la materia se lista pero no es inscribible."""
        crear_periodo(session, programa)
        ic = crear_instancia(session, materias_con_previaturas["prog1"], cupo_maximo=1)

        # Otro alumno ya ocupa el unico lugar
        session.add(InscripcionMateria(
            alumno_id=otro_alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.CURSANDO,
        ))
        session.commit()

        res = InscripcionMateriaService().get_materias_habilitadas(
            alumno.id, programa.id, session
        )

        mat = res["materias"][0]
        assert mat["inscriptos"] == 1
        assert mat["cupo_maximo"] == 1
        assert mat["puede_inscribirse"] is False
        assert any("completa" in m for m in mat["motivos"])

    @pytest.mark.parametrize("estado", [
        EstadoInscripcionMateria.APROBADO,
        EstadoInscripcionMateria.EXONERADO,
        EstadoInscripcionMateria.REVALIDADA,
        EstadoInscripcionMateria.CURSANDO,
    ])
    def test_materia_ya_obtenida_no_se_ofrece(
        self, session, alumno, programa, materias_con_previaturas, estado
    ):
        """Aprobada, exonerada, revalidada o en curso: no se vuelve a ofrecer."""
        crear_periodo(session, programa)
        m1 = materias_con_previaturas["prog1"]
        ic_previa = crear_instancia(session, m1, anio_lectivo=2025)
        crear_instancia(session, m1, anio_lectivo=2026)

        session.add(InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic_previa.id,
            estado=estado,
        ))
        session.commit()

        res = InscripcionMateriaService().get_materias_habilitadas(
            alumno.id, programa.id, session
        )

        assert "Programacion 1" not in nombres(res["materias"])

    def test_reprobada_se_puede_recursar(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Una materia reprobada si se vuelve a ofrecer."""
        crear_periodo(session, programa)
        m1 = materias_con_previaturas["prog1"]
        ic_previa = crear_instancia(session, m1, anio_lectivo=2025)
        crear_instancia(session, m1, anio_lectivo=2026)

        session.add(InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic_previa.id,
            estado=EstadoInscripcionMateria.REPROBADO,
        ))
        session.commit()

        res = InscripcionMateriaService().get_materias_habilitadas(
            alumno.id, programa.id, session
        )

        assert "Programacion 1" in nombres(res["materias"])

    def test_filtra_por_semestre_del_periodo(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """El periodo declara semestre 1: solo se ofrece la instancia de ese semestre."""
        crear_periodo(session, programa, semestre=1)
        crear_instancia(session, materias_con_previaturas["prog1"], semestre=1)
        crear_instancia(session, materias_con_previaturas["prog2"], semestre=2)

        res = InscripcionMateriaService().get_materias_habilitadas(
            alumno.id, programa.id, session
        )

        assert nombres(res["materias"]) == {"Programacion 1"}
        assert res["periodo_inscripcion"]["semestre"] == 1

    def test_instancia_sin_semestre_se_ofrece_igual(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Una instancia con semestre NULL no queda oculta al filtrar por semestre."""
        crear_periodo(session, programa, semestre=1)
        crear_instancia(session, materias_con_previaturas["prog1"], semestre=None)

        res = InscripcionMateriaService().get_materias_habilitadas(
            alumno.id, programa.id, session
        )

        assert nombres(res["materias"]) == {"Programacion 1"}
        assert res["materias"][0]["semestre"] is None

    def test_periodo_sin_semestre_no_filtra_por_semestre(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Si el periodo no declara semestre, vale para todo el anio lectivo."""
        crear_periodo(session, programa, semestre=None)
        crear_instancia(session, materias_con_previaturas["prog1"], semestre=1)
        crear_instancia(session, materias_con_previaturas["prog2"], semestre=2)

        res = InscripcionMateriaService().get_materias_habilitadas(
            alumno.id, programa.id, session
        )

        assert nombres(res["materias"]) == {"Programacion 1", "Programacion 2"}


# ══════════════════════════════════════════════════════════════════════════════
# Examenes habilitados
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(name="politica_examen")
def fixture_politica_examen(session):
    pol = PoliticaExamen(
        nombre="Examen test",
        nota_maxima=Decimal("100"),
        umbral_aprobacion=Decimal("60"),
        max_oportunidades=2,
    )
    session.add(pol)
    session.commit()
    session.refresh(pol)
    return pol


class TestExamenesHabilitados:

    def _inscripcion_a_examen(self, session, alumno, materia):
        ic = crear_instancia(session, materia, estado=EstadoInstanciaCursado.FINALIZADA)
        insc = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.A_EXAMEN,
        )
        session.add(insc)
        session.commit()
        session.refresh(insc)
        return insc

    def test_sin_materias_a_examen_lista_vacia(
        self, session, alumno, programa, materias_con_previaturas
    ):
        crear_instancia_examen(session, materias_con_previaturas["prog1"])

        res = InscripcionExamenService().get_examenes_habilitados(
            alumno.id, programa.id, session
        )
        assert res == []

    def test_materia_a_examen_con_plazo_abierto(
        self, session, alumno, programa, materias_con_previaturas, politica_examen
    ):
        m1 = materias_con_previaturas["prog1"]
        m1.politica_examen_id = politica_examen.id
        session.add(m1)
        session.commit()

        insc = self._inscripcion_a_examen(session, alumno, m1)
        inst = crear_instancia_examen(session, m1)

        res = InscripcionExamenService().get_examenes_habilitados(
            alumno.id, programa.id, session
        )

        assert len(res) == 1
        ex = res[0]
        assert ex["instancia_examen_id"] == inst.id
        assert ex["inscripcion_materia_id"] == insc.id
        assert ex["puede_inscribirse"] is True
        assert ex["motivos"] == []
        assert ex["max_oportunidades"] == 2
        assert ex["rendiciones_previas"] == 0

    def test_plazo_cerrado_no_aparece(
        self, session, alumno, programa, materias_con_previaturas, politica_examen
    ):
        m1 = materias_con_previaturas["prog1"]
        m1.politica_examen_id = politica_examen.id
        session.add(m1)
        session.commit()

        self._inscripcion_a_examen(session, alumno, m1)
        crear_instancia_examen(session, m1, abierta=False)

        res = InscripcionExamenService().get_examenes_habilitados(
            alumno.id, programa.id, session
        )
        assert res == []

    def test_sin_politica_de_examen_no_es_inscribible(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """inscribir_examen exige politica_examen_id, asi que la lista debe avisarlo."""
        m1 = materias_con_previaturas["prog1"]
        assert m1.politica_examen_id is None

        self._inscripcion_a_examen(session, alumno, m1)
        crear_instancia_examen(session, m1)

        res = InscripcionExamenService().get_examenes_habilitados(
            alumno.id, programa.id, session
        )

        assert len(res) == 1
        assert res[0]["puede_inscribirse"] is False
        assert any("politica de examen" in m for m in res[0]["motivos"])

    def test_oportunidades_agotadas_bloquean(
        self, session, alumno, programa, materias_con_previaturas, politica_examen
    ):
        """Con las rendiciones agotadas el examen se lista pero no es inscribible."""
        m1 = materias_con_previaturas["prog1"]
        m1.politica_examen_id = politica_examen.id
        session.add(m1)
        session.commit()

        insc = self._inscripcion_a_examen(session, alumno, m1)
        inst_vieja = crear_instancia_examen(session, m1, abierta=False)

        # max_oportunidades = 2, dos rendiciones ya consumidas
        session.add_all([
            InscripcionExamen(
                inscripcion_materia_id=insc.id,
                instancia_examen_id=inst_vieja.id,
                estado=EstadoInscripcionExamen.REPROBADO,
                numero_rendicion=1,
            ),
            InscripcionExamen(
                inscripcion_materia_id=insc.id,
                instancia_examen_id=inst_vieja.id,
                estado=EstadoInscripcionExamen.AUSENTE,
                numero_rendicion=2,
            ),
        ])
        session.commit()

        crear_instancia_examen(session, m1)

        res = InscripcionExamenService().get_examenes_habilitados(
            alumno.id, programa.id, session
        )

        assert len(res) == 1
        assert res[0]["rendiciones_previas"] == 2
        assert res[0]["puede_inscribirse"] is False
        assert any("oportunidades" in m for m in res[0]["motivos"])

    def test_ya_inscripto_se_marca(
        self, session, alumno, programa, materias_con_previaturas, politica_examen
    ):
        m1 = materias_con_previaturas["prog1"]
        m1.politica_examen_id = politica_examen.id
        session.add(m1)
        session.commit()

        insc = self._inscripcion_a_examen(session, alumno, m1)
        inst = crear_instancia_examen(session, m1)

        session.add(InscripcionExamen(
            inscripcion_materia_id=insc.id,
            instancia_examen_id=inst.id,
            estado=EstadoInscripcionExamen.INSCRIPTO,
        ))
        session.commit()

        res = InscripcionExamenService().get_examenes_habilitados(
            alumno.id, programa.id, session
        )

        assert res[0]["ya_inscripto"] is True
        assert res[0]["puede_inscribirse"] is False


# ══════════════════════════════════════════════════════════════════════════════
# Historico del docente
# ══════════════════════════════════════════════════════════════════════════════

class TestHistoricoDocente:

    def test_historico_materias_todos_los_anios_ordenado(
        self, session, profesor, alumno, programa, materias_con_previaturas
    ):
        """Sin filtro devuelve todos los anios, del mas reciente al mas antiguo."""
        m1 = materias_con_previaturas["prog1"]
        ic_2025 = crear_instancia(session, m1, anio_lectivo=2025)
        ic_2026 = crear_instancia(session, m1, anio_lectivo=2026)

        session.add_all([
            DocenteMateria(
                profesor_id=profesor.id,
                instancia_cursado_id=ic_2025.id,
                rol_docente=RolDocente.TITULAR,
            ),
            DocenteMateria(
                profesor_id=profesor.id,
                instancia_cursado_id=ic_2026.id,
                rol_docente=RolDocente.TITULAR,
            ),
        ])
        # Un inscripto en la instancia de 2026
        session.add(InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic_2026.id,
            estado=EstadoInscripcionMateria.CURSANDO,
        ))
        session.commit()

        hist = DocenteMateriaService().get_historico_materias(profesor.id, session)

        assert [h["anio_lectivo"] for h in hist] == [2026, 2025]
        assert hist[0]["total_inscriptos"] == 1
        assert hist[1]["total_inscriptos"] == 0
        assert hist[0]["programa_nombre"] == programa.nombre
        assert hist[0]["rol_docente"] == "titular"

    def test_historico_materias_filtra_por_anio(
        self, session, profesor, programa, materias_con_previaturas
    ):
        m1 = materias_con_previaturas["prog1"]
        ic_2025 = crear_instancia(session, m1, anio_lectivo=2025)
        ic_2026 = crear_instancia(session, m1, anio_lectivo=2026)
        session.add_all([
            DocenteMateria(
                profesor_id=profesor.id,
                instancia_cursado_id=ic_2025.id,
                rol_docente=RolDocente.TITULAR,
            ),
            DocenteMateria(
                profesor_id=profesor.id,
                instancia_cursado_id=ic_2026.id,
                rol_docente=RolDocente.ASISTENTE,
            ),
        ])
        session.commit()

        hist = DocenteMateriaService().get_historico_materias(
            profesor.id, session, anio_lectivo=2025
        )

        assert len(hist) == 1
        assert hist[0]["anio_lectivo"] == 2025

    def test_historico_examenes(
        self, session, profesor, alumno, programa, materias_con_previaturas
    ):
        """Devuelve los examenes donde el profesor fue tribunal, con inscriptos."""
        m1 = materias_con_previaturas["prog1"]
        inst = crear_instancia_examen(session, m1)

        ic = crear_instancia(session, m1, estado=EstadoInstanciaCursado.FINALIZADA)
        insc_materia = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.A_EXAMEN,
        )
        session.add(insc_materia)
        session.commit()
        session.refresh(insc_materia)

        session.add_all([
            DocenteInstanciaExamen(
                profesor_id=profesor.id,
                instancia_examen_id=inst.id,
            ),
            InscripcionExamen(
                inscripcion_materia_id=insc_materia.id,
                instancia_examen_id=inst.id,
                estado=EstadoInscripcionExamen.INSCRIPTO,
            ),
        ])
        session.commit()

        hist = DocenteMateriaService().get_historico_examenes(profesor.id, session)

        assert len(hist) == 1
        assert hist[0]["instancia_examen_id"] == inst.id
        assert hist[0]["materia_nombre"] == "Programacion 1"
        assert hist[0]["programa_nombre"] == programa.nombre
        assert hist[0]["total_inscriptos"] == 1

    def test_historico_vacio_para_profesor_sin_asignaciones(self, session, profesor):
        service = DocenteMateriaService()
        assert service.get_historico_materias(profesor.id, session) == []
        assert service.get_historico_examenes(profesor.id, session) == []

    def test_historico_no_mezcla_profesores(
        self, session, profesor, otro_profesor, materias_con_previaturas
    ):
        """El historico de un profesor no incluye las asignaciones de otro."""
        m1 = materias_con_previaturas["prog1"]
        ic = crear_instancia(session, m1, anio_lectivo=2026)

        session.add(DocenteMateria(
            profesor_id=otro_profesor.id,
            instancia_cursado_id=ic.id,
            rol_docente=RolDocente.TITULAR,
        ))
        session.commit()

        service = DocenteMateriaService()
        assert service.get_historico_materias(profesor.id, session) == []
        assert len(service.get_historico_materias(otro_profesor.id, session)) == 1


# ══════════════════════════════════════════════════════════════════════════════
# Profesor.activo
# ══════════════════════════════════════════════════════════════════════════════

class TestProfesorActivo:

    def test_profesor_activo_por_defecto(self, session, profesor):
        """Un profesor nuevo queda activo."""
        assert profesor.activo is True

    def test_desactivar_docente_no_toca_el_acceso(
        self, session, profesor, usuario_docente
    ):
        """profesor.activo y usuario.activo son independientes."""
        profesor.activo = False
        session.add(profesor)
        session.commit()
        session.refresh(profesor)
        session.refresh(usuario_docente)

        assert profesor.activo is False
        assert usuario_docente.activo is True
