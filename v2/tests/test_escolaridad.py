"""
Tests de consultas del alumno: escolaridad, materias disponibles,
mis materias y detalle de materia.

Cubre:
- get_escolaridad: historial academico agrupado por semestre
- get_materias_disponibles: materias inscribibles con previaturas
- get_mis_materias: materias del alumno en un anio lectivo
- get_detalle_materia: detalle completo con calificaciones
"""
import pytest
from decimal import Decimal

from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.calificacion import Calificacion
from v2.models.enums import (
    EstadoInscripcionMateria, EstadoInstanciaCursado,
)
from v2.services.inscripcion_service import InscripcionMateriaService
from v2.services.calificacion_service import CalificacionService


# ══════════════════════════════════════════════════════════════════════════════
# Escolaridad
# ══════════════════════════════════════════════════════════════════════════════

def materias_del_semestre(escolaridad: dict, semestre: int) -> list:
    """Materias de un semestre dentro de la lista de grupos de escolaridad."""
    for grupo in escolaridad["semestres"]:
        if grupo["semestre"] == semestre:
            return grupo["materias"]
    return []


class TestEscolaridad:
    """Escolaridad completa del alumno en un programa."""

    def test_escolaridad_sin_inscripciones(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Sin inscripciones, todas las materias aparecen como sin_inscripcion."""
        service = InscripcionMateriaService()
        esc = service.get_escolaridad(alumno.id, programa.id, session)

        assert esc["alumno_id"] == alumno.id
        assert esc["programa_id"] == programa.id
        assert esc["total_creditos"] == 0
        assert esc["total_creditos_posibles"] == 30  # 3 materias * 10 creditos

        # semestres es una lista ordenada de grupos
        semestres = esc["semestres"]
        assert [grupo["semestre"] for grupo in semestres] == sorted(
            grupo["semestre"] for grupo in semestres
        )

        # Todas las materias en semestres
        total_materias = sum(len(grupo["materias"]) for grupo in semestres)
        assert total_materias == 3

        # Todas sin inscripcion, con los campos de inscripcion en None
        for grupo in semestres:
            for mat in grupo["materias"]:
                assert mat["estado"] == "sin_inscripcion"
                assert mat["creditos_obtenidos"] == 0
                assert mat["inscripcion_id"] is None
                assert mat["anio_lectivo"] is None
                assert mat["nota_curso"] is None
                assert mat["nota_final"] is None
                assert mat["faltas"] == 0

    def test_escolaridad_con_materia_aprobada(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Materia aprobada suma creditos y muestra estado correcto."""
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
            nota_final=Decimal("75"),
            creditos_obtenidos=10,
        )
        session.add(insc)
        session.commit()

        service = InscripcionMateriaService()
        esc = service.get_escolaridad(alumno.id, programa.id, session)

        assert esc["total_creditos"] == 10
        assert esc["total_creditos_posibles"] == 30

        # Prog1 en semestre 1 esta aprobada
        sem1 = materias_del_semestre(esc, 1)
        assert len(sem1) == 1
        assert sem1[0]["estado"] == EstadoInscripcionMateria.APROBADO
        assert sem1[0]["creditos_obtenidos"] == 10
        assert sem1[0]["inscripcion_id"] == insc.id
        assert sem1[0]["anio_lectivo"] == 2025

    def test_escolaridad_multiples_inscripciones_toma_reciente(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Con multiples inscripciones en la misma materia, toma la mas reciente."""
        m1 = materias_con_previaturas["prog1"]

        # Inscripcion 2025: reprobado
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
            estado=EstadoInscripcionMateria.REPROBADO,
            creditos_obtenidos=0,
        )
        session.add(insc1)
        session.commit()

        # Inscripcion 2026: aprobado
        ic2 = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.FINALIZADA,
        )
        session.add(ic2)
        session.commit()
        session.refresh(ic2)

        insc2 = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic2.id,
            estado=EstadoInscripcionMateria.APROBADO,
            creditos_obtenidos=10,
        )
        session.add(insc2)
        session.commit()

        service = InscripcionMateriaService()
        esc = service.get_escolaridad(alumno.id, programa.id, session)

        # Debe tomar la de 2026 (aprobado)
        sem1 = materias_del_semestre(esc, 1)
        assert sem1[0]["estado"] == EstadoInscripcionMateria.APROBADO
        assert sem1[0]["anio_lectivo"] == 2026
        assert esc["total_creditos"] == 10

    def test_escolaridad_reporta_faltas(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Las faltas de la inscripcion se reflejan en la escolaridad."""
        m1 = materias_con_previaturas["prog1"]

        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.EN_CURSO,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        insc = InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.CURSANDO,
            nota_curso=Decimal("40"),
            faltas=4,
        )
        session.add(insc)
        session.commit()

        service = InscripcionMateriaService()
        esc = service.get_escolaridad(alumno.id, programa.id, session)

        sem1 = materias_del_semestre(esc, 1)
        assert sem1[0]["faltas"] == 4
        assert sem1[0]["nota_curso"] == Decimal("40")

    def test_escolaridad_filas_tienen_misma_forma(
        self, session, alumno, programa, materias_con_previaturas
    ):
        """Con y sin inscripcion, todas las filas exponen las mismas claves."""
        m1 = materias_con_previaturas["prog1"]

        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.EN_CURSO,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        session.add(InscripcionMateria(
            alumno_id=alumno.id,
            instancia_cursado_id=ic.id,
            estado=EstadoInscripcionMateria.CURSANDO,
        ))
        session.commit()

        service = InscripcionMateriaService()
        esc = service.get_escolaridad(alumno.id, programa.id, session)

        filas = [mat for grupo in esc["semestres"] for mat in grupo["materias"]]
        # Hay al menos una fila de cada tipo
        estados = {fila["estado"] for fila in filas}
        assert EstadoInscripcionMateria.CURSANDO in estados
        assert "sin_inscripcion" in estados

        claves = {frozenset(fila.keys()) for fila in filas}
        assert len(claves) == 1, "Las filas de escolaridad no tienen la misma forma"


# ══════════════════════════════════════════════════════════════════════════════
# Materias disponibles
# ══════════════════════════════════════════════════════════════════════════════

class TestMateriasDisponibles:
    """Materias a las que el alumno puede inscribirse."""

    def test_materias_disponibles_sin_inscripciones(
        self, session, alumno, programa, materias_con_previaturas,
    ):
        """Sin inscripciones, solo materias sin previaturas son inscribibles."""
        # Crear instancias de cursado para todas las materias
        for key in ["prog1", "prog2", "prog3"]:
            m = materias_con_previaturas[key]
            ic = InstanciaCursado(
                materia_id=m.id, anio_lectivo=2026,
                estado=EstadoInstanciaCursado.EN_CURSO,
            )
            session.add(ic)
        session.commit()

        service = InscripcionMateriaService()
        disponibles = service.get_materias_disponibles(
            alumno.id, programa.id, 2026, session,
        )

        assert len(disponibles) == 3
        disp_dict = {d["nombre"]: d for d in disponibles}

        # Prog1: puede inscribirse (sin previaturas)
        assert disp_dict["Programacion 1"]["puede_inscribirse"] is True
        assert disp_dict["Programacion 1"]["previaturas_faltantes"] == []

        # Prog2: no puede (falta Prog1)
        assert disp_dict["Programacion 2"]["puede_inscribirse"] is False
        assert len(disp_dict["Programacion 2"]["previaturas_faltantes"]) == 1

        # Prog3: no puede (falta Prog2)
        assert disp_dict["Programacion 3"]["puede_inscribirse"] is False

    def test_materias_disponibles_con_previa_aprobada(
        self, session, alumno, programa, materias_con_previaturas,
    ):
        """Con Prog1 aprobada, Prog2 se habilita."""
        m1 = materias_con_previaturas["prog1"]
        m2 = materias_con_previaturas["prog2"]

        # Aprobar Prog1
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

        # Crear instancias 2026
        for key in ["prog2", "prog3"]:
            m = materias_con_previaturas[key]
            ic = InstanciaCursado(
                materia_id=m.id, anio_lectivo=2026,
                estado=EstadoInstanciaCursado.EN_CURSO,
            )
            session.add(ic)
        session.commit()

        service = InscripcionMateriaService()
        disponibles = service.get_materias_disponibles(
            alumno.id, programa.id, 2026, session,
        )

        disp_dict = {d["nombre"]: d for d in disponibles}

        # Prog1 no aparece (ya aprobada)
        assert "Programacion 1" not in disp_dict

        # Prog2 ahora puede inscribirse
        assert disp_dict["Programacion 2"]["puede_inscribirse"] is True

    def test_materia_cursando_no_aparece(
        self, session, alumno, programa, materias_con_previaturas,
    ):
        """Materia actualmente cursando no aparece en disponibles."""
        m1 = materias_con_previaturas["prog1"]

        ic = InstanciaCursado(
            materia_id=m1.id, anio_lectivo=2026,
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

        service = InscripcionMateriaService()
        disponibles = service.get_materias_disponibles(
            alumno.id, programa.id, 2026, session,
        )

        nombres = [d["nombre"] for d in disponibles]
        assert "Programacion 1" not in nombres

    def test_sin_instancia_cursado_no_inscribible(
        self, session, alumno, programa, materias_con_previaturas,
    ):
        """Materia sin instancia de cursado en el anio no es inscribible."""
        service = InscripcionMateriaService()
        disponibles = service.get_materias_disponibles(
            alumno.id, programa.id, 2026, session,
        )

        # Prog1 cumple previaturas pero no tiene instancia
        disp_dict = {d["nombre"]: d for d in disponibles}
        assert disp_dict["Programacion 1"]["puede_inscribirse"] is False
        assert disp_dict["Programacion 1"]["instancia_cursado_id"] is None


# ══════════════════════════════════════════════════════════════════════════════
# Mis materias
# ══════════════════════════════════════════════════════════════════════════════

class TestMisMaterias:
    """Materias del alumno en un anio lectivo."""

    def test_mis_materias_vacio(self, session, alumno):
        """Sin inscripciones retorna lista vacia."""
        service = InscripcionMateriaService()
        resultado = service.get_mis_materias(alumno.id, 2026, session)
        assert resultado == []

    def test_mis_materias_con_inscripcion(
        self, session, alumno, inscripcion_cursando, instancia_cursado_completa,
    ):
        """Muestra materia inscripta con sus datos."""
        service = InscripcionMateriaService()
        resultado = service.get_mis_materias(alumno.id, 2026, session)

        assert len(resultado) == 1
        mat = resultado[0]
        assert mat["materia_nombre"] == "Programacion 1"
        assert mat["estado"] == "cursando"
        assert mat["faltas"] == 0
        assert mat["faltas_maximas"] == 5

    def test_mis_materias_otro_anio_no_muestra(
        self, session, alumno, inscripcion_cursando,
    ):
        """Inscripcion de 2026 no aparece al consultar 2025."""
        service = InscripcionMateriaService()
        resultado = service.get_mis_materias(alumno.id, 2025, session)
        assert resultado == []


# ══════════════════════════════════════════════════════════════════════════════
# Detalle de materia
# ══════════════════════════════════════════════════════════════════════════════

class TestDetalleMateria:
    """Detalle completo de una inscripcion para el alumno."""

    def test_detalle_basico(
        self, session, alumno, inscripcion_cursando,
        instancia_cursado_completa,
    ):
        """Detalle devuelve toda la informacion de la inscripcion."""
        service = InscripcionMateriaService()
        detalle = service.get_detalle_materia(
            inscripcion_cursando.id, alumno.id, session,
        )

        assert detalle["inscripcion_id"] == inscripcion_cursando.id
        assert detalle["estado"] == "cursando"
        assert detalle["materia_nombre"] == "Programacion 1"
        assert detalle["faltas"] == 0
        assert detalle["faltas_maximas"] == 5
        assert detalle["creditos"] == 10
        assert detalle["snapshot_politica"] is not None
        assert detalle["calificaciones"] == []

    def test_detalle_con_calificaciones(
        self, session, alumno, usuario_docente,
        inscripcion_cursando, instancia_cursado_completa,
    ):
        """Detalle incluye calificaciones cargadas."""
        cal_service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]

        cal_service.guardar_calificacion(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            instancia_evaluacion_id=ev1.id,
            nota=Decimal("25"),
            session=session,
        )

        service = InscripcionMateriaService()
        detalle = service.get_detalle_materia(
            inscripcion_cursando.id, alumno.id, session,
        )

        assert len(detalle["calificaciones"]) == 1
        assert detalle["calificaciones"][0]["nota"] == 25.0
        assert detalle["calificaciones"][0]["instancia_evaluacion_nombre"] == "Parcial 1"

    def test_detalle_otro_usuario_falla(
        self, session, otro_alumno, inscripcion_cursando,
    ):
        """No se puede ver el detalle de la inscripcion de otro alumno."""
        service = InscripcionMateriaService()

        with pytest.raises(ValueError, match="No es tu inscripcion"):
            service.get_detalle_materia(
                inscripcion_cursando.id, otro_alumno.id, session,
            )

    def test_detalle_inscripcion_inexistente(self, session, alumno):
        """Detalle de inscripcion inexistente lanza error."""
        service = InscripcionMateriaService()

        with pytest.raises(ValueError, match="no encontrada"):
            service.get_detalle_materia(9999, alumno.id, session)

    def test_detalle_refleja_faltas(
        self, session, alumno, inscripcion_cursando,
        instancia_cursado_completa,
    ):
        """Detalle muestra las faltas actualizadas."""
        insc_service = InscripcionMateriaService()

        # Registrar 3 faltas
        for _ in range(3):
            insc_service.registrar_falta(inscripcion_cursando.id, session)

        detalle = insc_service.get_detalle_materia(
            inscripcion_cursando.id, alumno.id, session,
        )
        assert detalle["faltas"] == 3

    def test_detalle_refleja_nota_curso(
        self, session, alumno, usuario_docente,
        inscripcion_cursando, instancia_cursado_completa,
    ):
        """Detalle muestra nota_curso actualizada tras calificaciones."""
        cal_service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]
        ev2 = instancia_cursado_completa["eval2"]

        cal_service.guardar_calificacion(
            usuario_docente.id, inscripcion_cursando.id, ev1.id,
            Decimal("28"), session,
        )
        cal_service.guardar_calificacion(
            usuario_docente.id, inscripcion_cursando.id, ev2.id,
            Decimal("60"), session,
        )

        service = InscripcionMateriaService()
        detalle = service.get_detalle_materia(
            inscripcion_cursando.id, alumno.id, session,
        )

        assert detalle["nota_curso"] == 88.0
        assert detalle["estado"] == "exonerado"
        assert detalle["creditos_obtenidos"] == 10
