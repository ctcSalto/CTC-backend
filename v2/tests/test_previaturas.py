"""
Tests del sistema de previaturas.

Cubre:
- CRUD de previaturas (PreviaturaService)
- Validaciones: misma materia, mismo programa, duplicados, ciclos
- Validacion de previaturas al inscribir (InscripcionMateriaService)
- Tipo APROBADA vs EXONERADA
- Mapa de previaturas para alumno
- Malla curricular
"""
import pytest
from decimal import Decimal

from v2.models.materia import Materia
from v2.models.previatura import Previatura, PreviaturaCreate
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.enums import (
    TipoPreviatura, EstadoInscripcionMateria, EstadoInstanciaCursado,
)
from v2.services.previatura_service import PreviaturaService
from v2.services.inscripcion_service import InscripcionMateriaService


# ══════════════════════════════════════════════════════════════════════════════
# CRUD Previaturas
# ══════════════════════════════════════════════════════════════════════════════

class TestPreviaturaCRUD:
    """Operaciones basicas de previaturas."""

    def test_crear_previatura(self, session, materias_con_previaturas):
        """Crear previatura exitosamente."""
        service = PreviaturaService()
        m1 = materias_con_previaturas["prog1"]
        m3 = materias_con_previaturas["prog3"]

        # P3 ya requiere P2, agregamos P3 tambien requiere P1
        prev = service.create(
            PreviaturaCreate(
                materia_id=m3.id,
                materia_previa_id=m1.id,
                tipo_requerido=TipoPreviatura.APROBADA,
            ),
            session,
        )
        assert prev.id is not None
        assert prev.materia_id == m3.id
        assert prev.materia_previa_id == m1.id

    def test_obtener_previaturas_de_materia(self, session, materias_con_previaturas):
        """get_by_materia retorna previaturas con nombres."""
        service = PreviaturaService()
        m2 = materias_con_previaturas["prog2"]

        prevs = service.get_by_materia(m2.id, session)
        assert len(prevs) == 1
        assert prevs[0].materia_previa_nombre == "Programacion 1"
        assert prevs[0].tipo_requerido == TipoPreviatura.APROBADA

    def test_materia_sin_previaturas(self, session, materias_con_previaturas):
        """Materia sin previaturas retorna lista vacia."""
        service = PreviaturaService()
        m1 = materias_con_previaturas["prog1"]

        prevs = service.get_by_materia(m1.id, session)
        assert len(prevs) == 0

    def test_eliminar_previatura(self, session, materias_con_previaturas):
        """Eliminar una previatura existente."""
        service = PreviaturaService()
        prev = materias_con_previaturas["prev_p2"]

        service.delete(prev.id, session)
        assert service.get_by_id(prev.id, session) is None

    def test_eliminar_previatura_inexistente(self, session):
        """Eliminar previatura que no existe lanza error."""
        service = PreviaturaService()
        with pytest.raises(ValueError, match="no encontrada"):
            service.delete(9999, session)


# ══════════════════════════════════════════════════════════════════════════════
# Validaciones de creacion
# ══════════════════════════════════════════════════════════════════════════════

class TestPreviaturaValidaciones:
    """Validaciones al crear previaturas."""

    def test_misma_materia_rechazada(self, session, materias_con_previaturas):
        """No se puede crear previatura de una materia consigo misma."""
        service = PreviaturaService()
        m1 = materias_con_previaturas["prog1"]

        with pytest.raises(ValueError, match="no puede ser previatura de si misma"):
            service.create(
                PreviaturaCreate(
                    materia_id=m1.id,
                    materia_previa_id=m1.id,
                    tipo_requerido=TipoPreviatura.APROBADA,
                ),
                session,
            )

    def test_materia_inexistente(self, session, materias_con_previaturas):
        """Materia que no existe lanza error."""
        service = PreviaturaService()
        m1 = materias_con_previaturas["prog1"]

        with pytest.raises(ValueError, match="no encontrada"):
            service.create(
                PreviaturaCreate(
                    materia_id=9999,
                    materia_previa_id=m1.id,
                    tipo_requerido=TipoPreviatura.APROBADA,
                ),
                session,
            )

    def test_materia_previa_inexistente(self, session, materias_con_previaturas):
        """Materia previa que no existe lanza error."""
        service = PreviaturaService()
        m1 = materias_con_previaturas["prog1"]

        with pytest.raises(ValueError, match="no encontrada"):
            service.create(
                PreviaturaCreate(
                    materia_id=m1.id,
                    materia_previa_id=9999,
                    tipo_requerido=TipoPreviatura.APROBADA,
                ),
                session,
            )

    def test_diferente_programa_rechazado(self, session, materias_con_previaturas, politica_base100):
        """Materias de programas distintos no pueden tener previaturas entre si."""
        from v2.models.programa import Programa
        from v2.models.enums import TipoPrograma, AreaPrograma

        otro_prog = Programa(
            nombre="Otro Programa",
            tipo=TipoPrograma.CURSO_CORTO,
            area=AreaPrograma.GENERAL,
            activo=True,
        )
        session.add(otro_prog)
        session.commit()
        session.refresh(otro_prog)

        m_otro = Materia(
            programa_id=otro_prog.id, nombre="Materia Otro",
            codigo="MO_T", semestre=1, creditos=5,
            politica_id=politica_base100.id, activo=True,
        )
        session.add(m_otro)
        session.commit()
        session.refresh(m_otro)

        service = PreviaturaService()
        m1 = materias_con_previaturas["prog1"]

        with pytest.raises(ValueError, match="mismo programa"):
            service.create(
                PreviaturaCreate(
                    materia_id=m_otro.id,
                    materia_previa_id=m1.id,
                    tipo_requerido=TipoPreviatura.APROBADA,
                ),
                session,
            )

    def test_previatura_duplicada_rechazada(self, session, materias_con_previaturas):
        """No se puede duplicar una previatura existente."""
        service = PreviaturaService()
        m1 = materias_con_previaturas["prog1"]
        m2 = materias_con_previaturas["prog2"]

        # P2 ya requiere P1, intentar crear la misma
        with pytest.raises(ValueError, match="ya existe"):
            service.create(
                PreviaturaCreate(
                    materia_id=m2.id,
                    materia_previa_id=m1.id,
                    tipo_requerido=TipoPreviatura.APROBADA,
                ),
                session,
            )

    def test_ciclo_directo_rechazado(self, session, materias_con_previaturas):
        """Ciclo directo A→B + B→A es rechazado."""
        service = PreviaturaService()
        m1 = materias_con_previaturas["prog1"]
        m2 = materias_con_previaturas["prog2"]

        # P2 ya requiere P1, intentar P1 requiere P2
        with pytest.raises(ValueError, match="ciclo"):
            service.create(
                PreviaturaCreate(
                    materia_id=m1.id,
                    materia_previa_id=m2.id,
                    tipo_requerido=TipoPreviatura.APROBADA,
                ),
                session,
            )

    def test_ciclo_indirecto_rechazado(self, session, materias_con_previaturas):
        """
        P1->P2->P3 ya existe; cerrar P1 requiere P3 arma el circulo.

        Antes solo se miraba el arco inverso, asi que este pasaba y despues
        colgaba a cualquiera que recorriera la cadena.
        """
        service = PreviaturaService()
        m1 = materias_con_previaturas["prog1"]
        m3 = materias_con_previaturas["prog3"]

        with pytest.raises(ValueError, match="ciclo"):
            service.create(
                PreviaturaCreate(
                    materia_id=m1.id,
                    materia_previa_id=m3.id,
                    tipo_requerido=TipoPreviatura.APROBADA,
                ),
                session,
            )

    def test_el_error_dice_cual_es_el_ciclo(self, session, materias_con_previaturas):
        """En una malla grande, saber que hay un ciclo no alcanza: hay que ver cual."""
        service = PreviaturaService()
        m1 = materias_con_previaturas["prog1"]
        m3 = materias_con_previaturas["prog3"]

        with pytest.raises(ValueError) as error:
            service.create(
                PreviaturaCreate(
                    materia_id=m1.id,
                    materia_previa_id=m3.id,
                    tipo_requerido=TipoPreviatura.APROBADA,
                ),
                session,
            )

        mensaje = str(error.value)
        for nombre in ("Programacion 1", "Programacion 2", "Programacion 3"):
            assert nombre in mensaje, mensaje

    def test_cadena_larga_sin_ciclo_se_permite(
        self, session, programa, politica_base100, materias_con_previaturas
    ):
        """El recorrido no puede confundir 'llegue lejos' con 'volvi al inicio'."""
        service = PreviaturaService()
        m4 = Materia(
            nombre="Programacion 4", codigo="P4", programa_id=programa.id,
            semestre=4, creditos=10, politica_id=politica_base100.id,
        )
        session.add(m4)
        session.commit()
        session.refresh(m4)

        prev = service.create(
            PreviaturaCreate(
                materia_id=m4.id,
                materia_previa_id=materias_con_previaturas["prog3"].id,
                tipo_requerido=TipoPreviatura.APROBADA,
            ),
            session,
        )
        assert prev.id is not None

    def test_no_confunde_ramas_paralelas(
        self, session, programa, politica_base100, materias_con_previaturas
    ):
        """
        Dos materias distintas pueden requerir la misma previa sin que eso sea
        un ciclo. El recorrido pasa dos veces por el mismo nodo y no debe
        interpretarlo como vuelta al origen.
        """
        service = PreviaturaService()
        m1 = materias_con_previaturas["prog1"]
        electiva = Materia(
            nombre="Electiva", codigo="EL1", programa_id=programa.id,
            semestre=3, creditos=5, politica_id=politica_base100.id,
        )
        session.add(electiva)
        session.commit()
        session.refresh(electiva)

        # Electiva requiere P1, igual que P2
        prev = service.create(
            PreviaturaCreate(
                materia_id=electiva.id, materia_previa_id=m1.id,
                tipo_requerido=TipoPreviatura.APROBADA,
            ),
            session,
        )
        assert prev.id is not None

    def test_ciclo_de_otro_programa_no_bloquea(
        self, session, politica_base100, materias_con_previaturas
    ):
        """
        El grafo se carga por programa. Una materia homonima de otra carrera no
        tiene que interferir: ya se valida antes que ambas sean del mismo
        programa, esto cubre que el recorrido tampoco las mezcle.
        """
        from v2.models.programa import Programa
        from v2.models.enums import TipoPrograma

        otro = Programa(
            nombre="Otra carrera", descripcion="x", tipo=TipoPrograma.CARRERA,
            duracion_semestres=4, activo=True,
        )
        session.add(otro)
        session.commit()
        session.refresh(otro)

        a = Materia(nombre="A", codigo="OA1", programa_id=otro.id, semestre=1,
                    creditos=5, politica_id=politica_base100.id)
        b = Materia(nombre="B", codigo="OB1", programa_id=otro.id, semestre=2,
                    creditos=5, politica_id=politica_base100.id)
        session.add(a)
        session.add(b)
        session.commit()
        session.refresh(a)
        session.refresh(b)

        service = PreviaturaService()
        prev = service.create(
            PreviaturaCreate(
                materia_id=b.id, materia_previa_id=a.id,
                tipo_requerido=TipoPreviatura.APROBADA,
            ),
            session,
        )
        assert prev.id is not None


class TestDeteccionDeCiclosCargados:
    """
    El script de verificacion busca ciclos ya presentes en la base, para los que
    se hayan cargado antes de la validacion o por SQL directo.
    """

    def test_encuentra_un_ciclo_cargado_a_mano(
        self, session, materias_con_previaturas
    ):
        from v2.scripts.verificar_ciclos_previaturas import buscar_ciclos

        assert buscar_ciclos(session) == []

        # P1 requiere P3 cierra P1->P2->P3->P1, salteando el servicio
        session.add(Previatura(
            materia_id=materias_con_previaturas["prog1"].id,
            materia_previa_id=materias_con_previaturas["prog3"].id,
            tipo_requerido=TipoPreviatura.APROBADA,
        ))
        session.commit()

        ciclos = buscar_ciclos(session)
        assert len(ciclos) == 1

        ids_del_ciclo = set(ciclos[0])
        assert ids_del_ciclo == {
            materias_con_previaturas["prog1"].id,
            materias_con_previaturas["prog2"].id,
            materias_con_previaturas["prog3"].id,
        }

    def test_una_malla_sana_no_reporta_nada(self, session, materias_con_previaturas):
        from v2.scripts.verificar_ciclos_previaturas import buscar_ciclos

        assert buscar_ciclos(session) == []


# ══════════════════════════════════════════════════════════════════════════════
# Malla curricular
# ══════════════════════════════════════════════════════════════════════════════

class TestMallaCurricular:
    """Malla curricular del programa."""

    def test_malla_agrupada_por_semestre(self, session, programa, materias_con_previaturas):
        """La malla agrupa correctamente por semestre."""
        service = PreviaturaService()
        malla = service.get_malla_programa(programa.id, session)

        assert malla["programa_id"] == programa.id
        assert 1 in malla["semestres"]
        assert 2 in malla["semestres"]
        assert 3 in malla["semestres"]
        assert len(malla["semestres"][1]) == 1  # Prog1
        assert len(malla["semestres"][2]) == 1  # Prog2
        assert len(malla["semestres"][3]) == 1  # Prog3

    def test_malla_incluye_previaturas(self, session, programa, materias_con_previaturas):
        """Materias en la malla incluyen sus previaturas."""
        service = PreviaturaService()
        malla = service.get_malla_programa(programa.id, session)

        # Prog1 (sem 1) no tiene previaturas
        prog1_data = malla["semestres"][1][0]
        assert prog1_data["previaturas"] == []

        # Prog2 (sem 2) requiere Prog1
        prog2_data = malla["semestres"][2][0]
        assert len(prog2_data["previaturas"]) == 1
        assert prog2_data["previaturas"][0]["materia_previa_nombre"] == "Programacion 1"

    def test_malla_programa_vacio(self, session):
        """Programa sin materias retorna malla vacia."""
        from v2.models.programa import Programa
        from v2.models.enums import TipoPrograma

        prog = Programa(nombre="Vacio", tipo=TipoPrograma.TALLER, activo=True)
        session.add(prog)
        session.commit()
        session.refresh(prog)

        service = PreviaturaService()
        malla = service.get_malla_programa(prog.id, session)
        assert malla["semestres"] == {}


# ══════════════════════════════════════════════════════════════════════════════
# Validacion de previaturas en inscripcion
# ══════════════════════════════════════════════════════════════════════════════

class TestValidarPreviaturasInscripcion:
    """Validacion de previaturas al inscribir a una materia."""

    def test_materia_sin_previaturas_cumple(self, session, alumno, materias_con_previaturas):
        """Materia sin previaturas siempre cumple."""
        service = InscripcionMateriaService()
        m1 = materias_con_previaturas["prog1"]

        cumple, faltantes = service.validar_previaturas(
            alumno.id, m1.id, session,
        )
        assert cumple is True
        assert faltantes == []

    def test_previatura_no_cursada_falla(self, session, alumno, materias_con_previaturas):
        """Sin inscripcion en la previa, falla."""
        service = InscripcionMateriaService()
        m2 = materias_con_previaturas["prog2"]

        cumple, faltantes = service.validar_previaturas(
            alumno.id, m2.id, session,
        )
        assert cumple is False
        assert len(faltantes) == 1
        assert "Programacion 1" in faltantes[0]

    def test_previatura_aprobada_cumple(self, session, alumno, materias_con_previaturas):
        """Inscripcion APROBADO en la previa cumple para tipo APROBADA."""
        service = InscripcionMateriaService()
        m1 = materias_con_previaturas["prog1"]
        m2 = materias_con_previaturas["prog2"]

        # Crear instancia de cursado y inscripcion aprobada en P1
        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        insc = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.APROBADO,
        )
        session.add(insc)
        session.commit()

        cumple, faltantes = service.validar_previaturas(
            alumno.id, m2.id, session,
        )
        assert cumple is True
        assert faltantes == []

    def test_previatura_exonerada_cumple_para_tipo_aprobada(
        self, session, alumno, materias_con_previaturas
    ):
        """Inscripcion EXONERADO cumple para tipo APROBADA (exonerado es mejor que aprobado)."""
        service = InscripcionMateriaService()
        m1 = materias_con_previaturas["prog1"]
        m2 = materias_con_previaturas["prog2"]

        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        insc = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.EXONERADO,
        )
        session.add(insc)
        session.commit()

        cumple, faltantes = service.validar_previaturas(
            alumno.id, m2.id, session,
        )
        assert cumple is True

    def test_previatura_tipo_exonerada_requiere_exoneracion(
        self, session, alumno, materias_con_previaturas
    ):
        """Tipo EXONERADA no acepta APROBADO (solo EXONERADO)."""
        service = InscripcionMateriaService()
        m1 = materias_con_previaturas["prog1"]
        m2 = materias_con_previaturas["prog2"]

        # Cambiar la previatura de P2→P1 a tipo EXONERADA
        prev = materias_con_previaturas["prev_p2"]
        prev.tipo_requerido = TipoPreviatura.EXONERADA
        session.add(prev)
        session.commit()

        # Inscripcion APROBADO (no exonerado)
        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        insc = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.APROBADO,
        )
        session.add(insc)
        session.commit()

        cumple, faltantes = service.validar_previaturas(
            alumno.id, m2.id, session,
        )
        assert cumple is False
        assert "exonerar" in faltantes[0].lower()

    def test_previatura_cursando_no_cumple(
        self, session, alumno, materias_con_previaturas
    ):
        """Estado CURSANDO no cumple previaturas."""
        service = InscripcionMateriaService()
        m1 = materias_con_previaturas["prog1"]
        m2 = materias_con_previaturas["prog2"]

        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.EN_CURSO,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        insc = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.CURSANDO,
        )
        session.add(insc)
        session.commit()

        cumple, faltantes = service.validar_previaturas(
            alumno.id, m2.id, session,
        )
        assert cumple is False

    def test_previatura_reprobada_no_cumple(
        self, session, alumno, materias_con_previaturas
    ):
        """Estado REPROBADO no cumple previaturas."""
        service = InscripcionMateriaService()
        m1 = materias_con_previaturas["prog1"]
        m2 = materias_con_previaturas["prog2"]

        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        insc = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.REPROBADO,
        )
        session.add(insc)
        session.commit()

        cumple, faltantes = service.validar_previaturas(
            alumno.id, m2.id, session,
        )
        assert cumple is False

    def test_previatura_revalidada_cumple(
        self, session, alumno, materias_con_previaturas
    ):
        """
        REVALIDADA habilita la siguiente materia. Una materia convalidada de otra
        institucion otorga creditos, asi que tambien tiene que abrir la cadena.
        """
        service = InscripcionMateriaService()
        m1 = materias_con_previaturas["prog1"]
        m2 = materias_con_previaturas["prog2"]

        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        insc = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.REVALIDADA,
            motivo_revalida="Aprobada en UTEC - 2024",
            creditos_obtenidos=m1.creditos,
        )
        session.add(insc)
        session.commit()

        cumple, faltantes = service.validar_previaturas(
            alumno.id, m2.id, session,
        )
        assert cumple is True
        assert faltantes == []

    def test_previatura_revalidada_cumple_tipo_exonerada(
        self, session, alumno, materias_con_previaturas
    ):
        """
        REVALIDADA tambien satisface una previatura de tipo EXONERADA: el alumno
        no puede volver a cursar lo que ya revalido, asi que exigirle la
        exoneracion lo dejaria trabado sin salida.
        """
        service = InscripcionMateriaService()
        m1 = materias_con_previaturas["prog1"]
        m2 = materias_con_previaturas["prog2"]

        prev = materias_con_previaturas["prev_p2"]
        prev.tipo_requerido = TipoPreviatura.EXONERADA
        session.add(prev)
        session.commit()

        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        session.add(InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.REVALIDADA,
            creditos_obtenidos=m1.creditos,
        ))
        session.commit()

        cumple, faltantes = service.validar_previaturas(
            alumno.id, m2.id, session,
        )
        assert cumple is True

    def test_recursada_alcanza_con_que_una_cumpla(
        self, session, alumno, materias_con_previaturas
    ):
        """
        Con varias inscripciones en la previa, basta que alguna alcance el tipo
        requerido. Antes se miraba una sola fila y el resultado dependia del
        orden que devolviera la base.
        """
        service = InscripcionMateriaService()
        m1 = materias_con_previaturas["prog1"]
        m2 = materias_con_previaturas["prog2"]

        prev = materias_con_previaturas["prev_p2"]
        prev.tipo_requerido = TipoPreviatura.EXONERADA
        session.add(prev)
        session.commit()

        # 2024: aprobo por examen (no alcanza para tipo EXONERADA)
        ic_2024 = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2024,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        # 2025: exonero (si alcanza)
        ic_2025 = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add_all([ic_2024, ic_2025])
        session.commit()
        session.refresh(ic_2024)
        session.refresh(ic_2025)

        session.add_all([
            InscripcionMateria(
                alumno_id=alumno.id,
                instancia_cursado_id=ic_2024.id,
                estado=EstadoInscripcionMateria.APROBADO,
            ),
            InscripcionMateria(
                alumno_id=alumno.id,
                instancia_cursado_id=ic_2025.id,
                estado=EstadoInscripcionMateria.EXONERADO,
            ),
        ])
        session.commit()

        cumple, faltantes = service.validar_previaturas(
            alumno.id, m2.id, session,
        )
        assert cumple is True, f"Deberia alcanzar con la exoneracion de 2025: {faltantes}"

    def test_cadena_de_previaturas(
        self, session, alumno, materias_con_previaturas
    ):
        """Para P3 necesita P2 aprobado (que a su vez necesita P1)."""
        service = InscripcionMateriaService()
        m1 = materias_con_previaturas["prog1"]
        m2 = materias_con_previaturas["prog2"]
        m3 = materias_con_previaturas["prog3"]

        # Aprobar P1
        ic1 = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic1)
        session.commit()
        session.refresh(ic1)

        insc1 = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic1.id,
            estado=EstadoInscripcionMateria.APROBADO,
        )
        session.add(insc1)
        session.commit()

        # Sin aprobar P2, P3 no cumple
        cumple, faltantes = service.validar_previaturas(
            alumno.id, m3.id, session,
        )
        assert cumple is False
        assert "Programacion 2" in faltantes[0]

        # Aprobar P2
        ic2 = InstanciaCursado(
            materia_id=m2.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic2)
        session.commit()
        session.refresh(ic2)

        insc2 = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic2.id,
            estado=EstadoInscripcionMateria.APROBADO,
        )
        session.add(insc2)
        session.commit()

        # Ahora P3 cumple
        cumple, faltantes = service.validar_previaturas(
            alumno.id, m3.id, session,
        )
        assert cumple is True


# ══════════════════════════════════════════════════════════════════════════════
# Mapa de previaturas (vista alumno)
# ══════════════════════════════════════════════════════════════════════════════

class TestMapaPreviaturas:
    """Mapa de previaturas con estado del alumno."""

    def test_mapa_sin_inscripciones(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Alumno sin inscripciones ve todo como 'pendiente'."""
        service = InscripcionMateriaService()
        mapa = service.get_mapa_previaturas(
            alumno.id, programa.id, session,
        )
        assert len(mapa) == 3
        for item in mapa:
            assert item["estado_alumno"] == "pendiente"

    def test_mapa_con_materia_aprobada(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Alumno con P1 aprobada ve estado correcto."""
        m1 = materias_con_previaturas["prog1"]
        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        insc = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.APROBADO,
        )
        session.add(insc)
        session.commit()

        service = InscripcionMateriaService()
        mapa = service.get_mapa_previaturas(
            alumno.id, programa.id, session,
        )

        estados = {item["nombre"]: item["estado_alumno"] for item in mapa}
        assert estados["Programacion 1"] == "aprobado"
        assert estados["Programacion 2"] == "pendiente"
        assert estados["Programacion 3"] == "pendiente"

    def test_mapa_muestra_revalidada(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Una materia revalidada se muestra como tal, no como 'pendiente'."""
        m1 = materias_con_previaturas["prog1"]
        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        session.add(InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.REVALIDADA,
            creditos_obtenidos=m1.creditos,
        ))
        session.commit()

        service = InscripcionMateriaService()
        mapa = service.get_mapa_previaturas(alumno.id, programa.id, session)

        estados = {item["nombre"]: item["estado_alumno"] for item in mapa}
        assert estados["Programacion 1"] == "revalidada"

    def test_mapa_revalidada_le_gana_a_un_intento_previo(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """
        Si el alumno reprobo y despues revalido, el mapa muestra la revalida.
        Antes REVALIDADA no estaba en la tabla de prioridad y perdia contra
        cualquier otro estado, incluso contra abandono.
        """
        m1 = materias_con_previaturas["prog1"]
        ic_repro = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2024,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        ic_reval = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2025,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add_all([ic_repro, ic_reval])
        session.commit()
        session.refresh(ic_repro)
        session.refresh(ic_reval)

        session.add_all([
            InscripcionMateria(
                alumno_id=alumno.id,
                instancia_cursado_id=ic_repro.id,
                estado=EstadoInscripcionMateria.REPROBADO,
            ),
            InscripcionMateria(
                alumno_id=alumno.id,
                instancia_cursado_id=ic_reval.id,
                estado=EstadoInscripcionMateria.REVALIDADA,
                creditos_obtenidos=m1.creditos,
            ),
        ])
        session.commit()

        service = InscripcionMateriaService()
        mapa = service.get_mapa_previaturas(alumno.id, programa.id, session)

        estados = {item["nombre"]: item["estado_alumno"] for item in mapa}
        assert estados["Programacion 1"] == "revalidada"

    def test_mapa_incluye_previaturas(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """El mapa incluye las previaturas de cada materia."""
        service = InscripcionMateriaService()
        mapa = service.get_mapa_previaturas(
            alumno.id, programa.id, session,
        )

        mapa_dict = {item["nombre"]: item for item in mapa}
        assert len(mapa_dict["Programacion 1"]["previaturas"]) == 0
        assert len(mapa_dict["Programacion 2"]["previaturas"]) == 1
        assert mapa_dict["Programacion 2"]["previaturas"][0]["nombre"] == "Programacion 1"
