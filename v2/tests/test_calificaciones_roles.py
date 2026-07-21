"""
Tests del sistema de calificaciones, grading engine y control de acceso por roles.

Cubre:
- Grading engine (funcion pura calcular_estado)
- Calificacion individual y batch
- Recalculo automatico de estado
- Nota final directa
- Sistema de faltas
- Validacion de roles (estudiante, docente, admin)
"""
import pytest
from decimal import Decimal

from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.calificacion import Calificacion
from v2.models.enums import (
    EstadoInscripcionMateria, RolUsuario,
)
from v2.services.grading_engine import calcular_estado
from v2.services.calificacion_service import CalificacionService
from v2.services.inscripcion_service import InscripcionMateriaService
from v2.auth.security import create_v2_token, verify_v2_token


# ══════════════════════════════════════════════════════════════════════════════
# Grading Engine (funcion pura)
# ══════════════════════════════════════════════════════════════════════════════

class TestGradingEngine:
    """Motor de calificaciones: calcular_estado()."""

    def _snapshot_base100(self):
        """Politica tipica base 100 con examen y exoneracion."""
        return {
            "nota_maxima": 100.0,
            "umbral_aprobacion": 60.0,
            "umbral_examen": 25.0,
            "umbral_exoneracion": 86.0,
        }

    def _snapshot_curso_corto(self):
        """Politica de curso corto (sin examen ni exoneracion)."""
        return {
            "nota_maxima": 100.0,
            "umbral_aprobacion": 60.0,
            "umbral_examen": None,
            "umbral_exoneracion": None,
        }

    # -- No todas las instancias calificadas --

    def test_incompleto_sigue_cursando(self):
        """Sin todas las instancias calificadas → CURSANDO."""
        resultado = calcular_estado(
            nota_curso=Decimal("50"),
            snapshot_politica=self._snapshot_base100(),
            creditos_materia=10,
            todas_instancias_calificadas=False,
        )
        assert resultado["estado"] == EstadoInscripcionMateria.CURSANDO
        assert resultado["creditos_obtenidos"] == 0
        assert resultado["nota_final"] is None

    # -- Exoneracion --

    def test_exoneracion_en_86(self):
        """Nota >= 86 con todas calificadas → EXONERADO."""
        resultado = calcular_estado(
            nota_curso=Decimal("86"),
            snapshot_politica=self._snapshot_base100(),
            creditos_materia=10,
            todas_instancias_calificadas=True,
        )
        assert resultado["estado"] == EstadoInscripcionMateria.EXONERADO
        assert resultado["creditos_obtenidos"] == 10
        assert resultado["nota_final"] == Decimal("86")

    def test_exoneracion_en_100(self):
        """Nota maxima → EXONERADO."""
        resultado = calcular_estado(
            nota_curso=Decimal("100"),
            snapshot_politica=self._snapshot_base100(),
            creditos_materia=10,
            todas_instancias_calificadas=True,
        )
        assert resultado["estado"] == EstadoInscripcionMateria.EXONERADO
        assert resultado["creditos_obtenidos"] == 10

    def test_exoneracion_en_85_no_exonera(self):
        """Nota 85 (< 86) no exonera."""
        resultado = calcular_estado(
            nota_curso=Decimal("85"),
            snapshot_politica=self._snapshot_base100(),
            creditos_materia=10,
            todas_instancias_calificadas=True,
        )
        assert resultado["estado"] != EstadoInscripcionMateria.EXONERADO

    # -- A examen --

    def test_a_examen_en_25(self):
        """Nota >= 25 y < 86 → A_EXAMEN."""
        resultado = calcular_estado(
            nota_curso=Decimal("50"),
            snapshot_politica=self._snapshot_base100(),
            creditos_materia=10,
            todas_instancias_calificadas=True,
        )
        assert resultado["estado"] == EstadoInscripcionMateria.A_EXAMEN
        assert resultado["creditos_obtenidos"] == 0
        assert resultado["nota_final"] is None

    def test_a_examen_limite_exacto(self):
        """Nota exactamente 25 → A_EXAMEN."""
        resultado = calcular_estado(
            nota_curso=Decimal("25"),
            snapshot_politica=self._snapshot_base100(),
            creditos_materia=10,
            todas_instancias_calificadas=True,
        )
        assert resultado["estado"] == EstadoInscripcionMateria.A_EXAMEN

    # -- Reprobado --

    def test_reprobado_bajo_examen(self):
        """Nota < 25 → REPROBADO."""
        resultado = calcular_estado(
            nota_curso=Decimal("24"),
            snapshot_politica=self._snapshot_base100(),
            creditos_materia=10,
            todas_instancias_calificadas=True,
        )
        assert resultado["estado"] == EstadoInscripcionMateria.REPROBADO
        assert resultado["creditos_obtenidos"] == 0

    def test_reprobado_nota_cero(self):
        """Nota 0 → REPROBADO."""
        resultado = calcular_estado(
            nota_curso=Decimal("0"),
            snapshot_politica=self._snapshot_base100(),
            creditos_materia=10,
            todas_instancias_calificadas=True,
        )
        assert resultado["estado"] == EstadoInscripcionMateria.REPROBADO

    # -- Curso corto (aprobacion directa) --

    def test_curso_corto_aprobado(self):
        """Curso corto: nota >= 60 → APROBADO directamente."""
        resultado = calcular_estado(
            nota_curso=Decimal("75"),
            snapshot_politica=self._snapshot_curso_corto(),
            creditos_materia=5,
            todas_instancias_calificadas=True,
        )
        assert resultado["estado"] == EstadoInscripcionMateria.APROBADO
        assert resultado["creditos_obtenidos"] == 5

    def test_curso_corto_reprobado(self):
        """Curso corto: nota < 60 → REPROBADO."""
        resultado = calcular_estado(
            nota_curso=Decimal("40"),
            snapshot_politica=self._snapshot_curso_corto(),
            creditos_materia=5,
            todas_instancias_calificadas=True,
        )
        assert resultado["estado"] == EstadoInscripcionMateria.REPROBADO
        assert resultado["creditos_obtenidos"] == 0

    def test_curso_corto_limite_exacto(self):
        """Curso corto: nota exactamente 60 → APROBADO."""
        resultado = calcular_estado(
            nota_curso=Decimal("60"),
            snapshot_politica=self._snapshot_curso_corto(),
            creditos_materia=5,
            todas_instancias_calificadas=True,
        )
        assert resultado["estado"] == EstadoInscripcionMateria.APROBADO


# ══════════════════════════════════════════════════════════════════════════════
# CalificacionService: Guardar calificacion individual
# ══════════════════════════════════════════════════════════════════════════════

class TestGuardarCalificacion:
    """Carga de calificaciones individuales."""

    def test_guardar_calificacion_nueva(
        self, session, usuario_docente, inscripcion_cursando, instancia_cursado_completa
    ):
        """Crear una calificacion nueva."""
        service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]

        cal = service.guardar_calificacion(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            instancia_evaluacion_id=ev1.id,
            nota=Decimal("25"),
            session=session,
        )
        assert cal.id is not None
        assert cal.nota == Decimal("25")
        assert cal.cargado_por_id == usuario_docente.id

    def test_upsert_calificacion_existente(
        self, session, usuario_docente, inscripcion_cursando, instancia_cursado_completa
    ):
        """Guardar la misma calificacion dos veces actualiza (upsert)."""
        service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]

        cal1 = service.guardar_calificacion(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            instancia_evaluacion_id=ev1.id,
            nota=Decimal("20"),
            session=session,
        )
        cal2 = service.guardar_calificacion(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            instancia_evaluacion_id=ev1.id,
            nota=Decimal("28"),
            session=session,
        )
        assert cal1.id == cal2.id
        assert cal2.nota == Decimal("28")

    def test_nota_fuera_de_rango_rechazada(
        self, session, usuario_docente, inscripcion_cursando, instancia_cursado_completa
    ):
        """Nota mayor al peso_maximo es rechazada."""
        service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]  # peso_maximo=30

        with pytest.raises(ValueError, match="entre 0 y"):
            service.guardar_calificacion(
                cargado_por_id=usuario_docente.id,
                inscripcion_id=inscripcion_cursando.id,
                instancia_evaluacion_id=ev1.id,
                nota=Decimal("31"),
                session=session,
            )

    def test_nota_negativa_rechazada(
        self, session, usuario_docente, inscripcion_cursando, instancia_cursado_completa
    ):
        """Nota negativa es rechazada."""
        service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]

        with pytest.raises(ValueError, match="entre 0 y"):
            service.guardar_calificacion(
                cargado_por_id=usuario_docente.id,
                inscripcion_id=inscripcion_cursando.id,
                instancia_evaluacion_id=ev1.id,
                nota=Decimal("-1"),
                session=session,
            )

    def test_calificar_inscripcion_inexistente(self, session, usuario_docente, instancia_cursado_completa):
        """Inscripcion que no existe lanza error."""
        service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]

        with pytest.raises(ValueError, match="no encontrada"):
            service.guardar_calificacion(
                cargado_por_id=usuario_docente.id,
                inscripcion_id=9999,
                instancia_evaluacion_id=ev1.id,
                nota=Decimal("10"),
                session=session,
            )

    def test_calificar_evaluacion_inexistente(
        self, session, usuario_docente, inscripcion_cursando
    ):
        """Instancia de evaluacion que no existe lanza error."""
        service = CalificacionService()

        with pytest.raises(ValueError, match="no encontrada"):
            service.guardar_calificacion(
                cargado_por_id=usuario_docente.id,
                inscripcion_id=inscripcion_cursando.id,
                instancia_evaluacion_id=9999,
                nota=Decimal("10"),
                session=session,
            )


# ══════════════════════════════════════════════════════════════════════════════
# Recalculo automatico de estado
# ══════════════════════════════════════════════════════════════════════════════

class TestRecalculoEstado:
    """El estado se recalcula automaticamente al cargar notas."""

    def test_parcial_unico_sigue_cursando(
        self, session, usuario_docente, inscripcion_cursando, instancia_cursado_completa
    ):
        """Con solo 1 de 2 parciales calificados, sigue CURSANDO."""
        service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]

        service.guardar_calificacion(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            instancia_evaluacion_id=ev1.id,
            nota=Decimal("30"),
            session=session,
        )

        session.refresh(inscripcion_cursando)
        assert inscripcion_cursando.estado == EstadoInscripcionMateria.CURSANDO

    def test_ambos_parciales_exoneracion(
        self, session, usuario_docente, inscripcion_cursando, instancia_cursado_completa
    ):
        """Con ambos parciales y nota >= 86 → EXONERADO."""
        service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]
        ev2 = instancia_cursado_completa["eval2"]

        # Parcial 1: 28/30
        service.guardar_calificacion(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            instancia_evaluacion_id=ev1.id,
            nota=Decimal("28"),
            session=session,
        )
        # Parcial 2: 60/70 → total 88
        service.guardar_calificacion(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            instancia_evaluacion_id=ev2.id,
            nota=Decimal("60"),
            session=session,
        )

        session.refresh(inscripcion_cursando)
        assert inscripcion_cursando.estado == EstadoInscripcionMateria.EXONERADO
        assert inscripcion_cursando.nota_curso == Decimal("88")
        assert inscripcion_cursando.creditos_obtenidos == 10

    def test_ambos_parciales_a_examen(
        self, session, usuario_docente, inscripcion_cursando, instancia_cursado_completa
    ):
        """Con nota entre 25 y 85 → A_EXAMEN."""
        service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]
        ev2 = instancia_cursado_completa["eval2"]

        # Parcial 1: 15/30
        service.guardar_calificacion(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            instancia_evaluacion_id=ev1.id,
            nota=Decimal("15"),
            session=session,
        )
        # Parcial 2: 35/70 → total 50
        service.guardar_calificacion(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            instancia_evaluacion_id=ev2.id,
            nota=Decimal("35"),
            session=session,
        )

        session.refresh(inscripcion_cursando)
        assert inscripcion_cursando.estado == EstadoInscripcionMateria.A_EXAMEN

    def test_ambos_parciales_reprobado(
        self, session, usuario_docente, inscripcion_cursando, instancia_cursado_completa
    ):
        """Con nota < 25 → REPROBADO."""
        service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]
        ev2 = instancia_cursado_completa["eval2"]

        # Parcial 1: 5/30
        service.guardar_calificacion(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            instancia_evaluacion_id=ev1.id,
            nota=Decimal("5"),
            session=session,
        )
        # Parcial 2: 15/70 → total 20
        service.guardar_calificacion(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            instancia_evaluacion_id=ev2.id,
            nota=Decimal("15"),
            session=session,
        )

        session.refresh(inscripcion_cursando)
        assert inscripcion_cursando.estado == EstadoInscripcionMateria.REPROBADO


# ══════════════════════════════════════════════════════════════════════════════
# Batch de calificaciones
# ══════════════════════════════════════════════════════════════════════════════

class TestCalificacionBatch:
    """Carga masiva de calificaciones."""

    def test_batch_exitoso(
        self, session, usuario_docente, usuario_estudiante,
        inscripcion_cursando, instancia_cursado_completa
    ):
        """Carga masiva funciona correctamente."""
        from v2.models.calificacion import CalificacionBatchItem

        service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]

        items = [
            CalificacionBatchItem(
                inscripcion_id=inscripcion_cursando.id,
                nota=Decimal("25"),
            ),
        ]
        resultado = service.guardar_batch(
            cargado_por_id=usuario_docente.id,
            instancia_evaluacion_id=ev1.id,
            calificaciones=items,
            session=session,
        )
        assert resultado["exitosos"] == 1
        assert resultado["errores"] == []

    def test_batch_con_error_parcial(
        self, session, usuario_docente, inscripcion_cursando, instancia_cursado_completa
    ):
        """Batch con un item invalido reporta error sin frenar el resto."""
        from v2.models.calificacion import CalificacionBatchItem

        service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]

        items = [
            CalificacionBatchItem(inscripcion_id=inscripcion_cursando.id, nota=Decimal("20")),
            CalificacionBatchItem(inscripcion_id=9999, nota=Decimal("10")),  # no existe
        ]
        resultado = service.guardar_batch(
            cargado_por_id=usuario_docente.id,
            instancia_evaluacion_id=ev1.id,
            calificaciones=items,
            session=session,
        )
        assert resultado["exitosos"] == 1
        assert len(resultado["errores"]) == 1
        assert resultado["errores"][0]["inscripcion_id"] == 9999


# ══════════════════════════════════════════════════════════════════════════════
# Nota final directa
# ══════════════════════════════════════════════════════════════════════════════

class TestNotaFinalDirecta:
    """Profesor carga nota final sin pasar por parciales."""

    def test_nota_final_directa_exoneracion(
        self, session, usuario_docente, inscripcion_cursando
    ):
        """Nota directa >= 86 → EXONERADO."""
        service = CalificacionService()

        insc = service.cargar_nota_final_directa(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            nota=Decimal("90"),
            session=session,
        )
        assert insc.estado == EstadoInscripcionMateria.EXONERADO
        assert insc.nota_final_directa == Decimal("90")
        assert insc.creditos_obtenidos == 10

    def test_nota_final_directa_a_examen(
        self, session, usuario_docente, inscripcion_cursando
    ):
        """Nota directa entre 25 y 85 → A_EXAMEN."""
        service = CalificacionService()

        insc = service.cargar_nota_final_directa(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            nota=Decimal("50"),
            session=session,
        )
        assert insc.estado == EstadoInscripcionMateria.A_EXAMEN

    def test_nota_final_directa_reprobado(
        self, session, usuario_docente, inscripcion_cursando
    ):
        """Nota directa < 25 → REPROBADO."""
        service = CalificacionService()

        insc = service.cargar_nota_final_directa(
            cargado_por_id=usuario_docente.id,
            inscripcion_id=inscripcion_cursando.id,
            nota=Decimal("10"),
            session=session,
        )
        assert insc.estado == EstadoInscripcionMateria.REPROBADO

    def test_nota_fuera_de_rango(
        self, session, usuario_docente, inscripcion_cursando
    ):
        """Nota > nota_maxima es rechazada."""
        service = CalificacionService()

        with pytest.raises(ValueError, match="entre 0 y"):
            service.cargar_nota_final_directa(
                cargado_por_id=usuario_docente.id,
                inscripcion_id=inscripcion_cursando.id,
                nota=Decimal("150"),
                session=session,
            )

    def test_nota_directa_solo_cursando(
        self, session, usuario_docente, inscripcion_cursando
    ):
        """Solo se puede cargar nota directa en estado CURSANDO."""
        service = CalificacionService()
        inscripcion_cursando.estado = EstadoInscripcionMateria.A_EXAMEN
        session.add(inscripcion_cursando)
        session.commit()

        with pytest.raises(ValueError, match="CURSANDO"):
            service.cargar_nota_final_directa(
                cargado_por_id=usuario_docente.id,
                inscripcion_id=inscripcion_cursando.id,
                nota=Decimal("50"),
                session=session,
            )


# ══════════════════════════════════════════════════════════════════════════════
# Sistema de faltas
# ══════════════════════════════════════════════════════════════════════════════

class TestSistemaFaltas:
    """Registro de faltas y perdida por inasistencia."""

    def test_registrar_falta_incrementa(self, session, inscripcion_cursando):
        """Registrar falta incrementa el contador."""
        service = InscripcionMateriaService()

        insc = service.registrar_falta(inscripcion_cursando.id, session)
        assert insc.faltas == 1

        insc = service.registrar_falta(inscripcion_cursando.id, session)
        assert insc.faltas == 2

    def test_quitar_falta_decrementa(self, session, inscripcion_cursando):
        """Quitar falta decrementa el contador."""
        service = InscripcionMateriaService()

        service.registrar_falta(inscripcion_cursando.id, session)
        service.registrar_falta(inscripcion_cursando.id, session)
        insc = service.quitar_falta(inscripcion_cursando.id, session)
        assert insc.faltas == 1

    def test_quitar_falta_minimo_cero(self, session, inscripcion_cursando):
        """Quitar falta no baja de 0."""
        service = InscripcionMateriaService()

        insc = service.quitar_falta(inscripcion_cursando.id, session)
        assert insc.faltas == 0

    def test_perdido_inasistencia_automatico(self, session, inscripcion_cursando):
        """Al alcanzar faltas_maximas, cambia a PERDIDO_INASISTENCIA."""
        service = InscripcionMateriaService()

        # faltas_maximas = 5 (definido en fixture)
        for i in range(5):
            insc = service.registrar_falta(inscripcion_cursando.id, session)

        assert insc.estado == EstadoInscripcionMateria.PERDIDO_INASISTENCIA
        assert insc.faltas == 5
        assert insc.creditos_obtenidos == 0
        assert insc.fecha_cierre is not None

    def test_falta_solo_cursando(self, session, inscripcion_cursando):
        """Solo se pueden registrar faltas en estado CURSANDO."""
        service = InscripcionMateriaService()

        inscripcion_cursando.estado = EstadoInscripcionMateria.A_EXAMEN
        session.add(inscripcion_cursando)
        session.commit()

        with pytest.raises(ValueError, match="CURSANDO"):
            service.registrar_falta(inscripcion_cursando.id, session)

    def test_falta_inscripcion_inexistente(self, session):
        """Falta en inscripcion inexistente lanza error."""
        service = InscripcionMateriaService()

        with pytest.raises(ValueError, match="no encontrada"):
            service.registrar_falta(9999, session)


# ══════════════════════════════════════════════════════════════════════════════
# Validacion de roles en tokens
# ══════════════════════════════════════════════════════════════════════════════

class TestRolesToken:
    """Validacion de roles via JWT."""

    def test_token_estudiante(self, usuario_estudiante):
        """Token de estudiante tiene rol correcto."""
        token = create_v2_token(
            usuario_estudiante.email,
            usuario_estudiante.id,
            usuario_estudiante.rol.value,
        )
        payload = verify_v2_token(token)
        assert payload["rol"] == "estudiante"

    def test_token_docente(self, usuario_docente):
        """Token de docente tiene rol correcto."""
        token = create_v2_token(
            usuario_docente.email,
            usuario_docente.id,
            usuario_docente.rol.value,
        )
        payload = verify_v2_token(token)
        assert payload["rol"] == "docente"

    def test_token_admin(self, usuario_admin):
        """Token de admin tiene rol correcto."""
        token = create_v2_token(
            usuario_admin.email,
            usuario_admin.id,
            usuario_admin.rol.value,
        )
        payload = verify_v2_token(token)
        assert payload["rol"] == "administrativo"

    def test_token_preserva_usuario_id(self, usuario_estudiante):
        """Token preserva el usuario_id correcto."""
        token = create_v2_token(
            usuario_estudiante.email,
            usuario_estudiante.id,
            usuario_estudiante.rol.value,
        )
        payload = verify_v2_token(token)
        assert payload["usuario_id"] == usuario_estudiante.id


# ══════════════════════════════════════════════════════════════════════════════
# Validacion de asignacion docente
# ══════════════════════════════════════════════════════════════════════════════

class TestValidarDocenteAsignacion:
    """El docente solo puede operar en instancias asignadas."""

    def test_docente_asignado(
        self, session, usuario_docente, asignacion_docente, instancia_cursado_completa
    ):
        """Docente asignado pasa la validacion."""
        service = CalificacionService()
        ic = instancia_cursado_completa["instancia"]

        resultado = service.validar_docente_instancia_cursado(
            usuario_docente.id, ic.id, session,
        )
        assert resultado is True

    def test_docente_no_asignado(
        self, session, profesor, instancia_cursado_completa
    ):
        """Profesor sin asignacion falla la validacion."""
        service = CalificacionService()
        ic = instancia_cursado_completa["instancia"]

        resultado = service.validar_docente_instancia_cursado(
            profesor.id, ic.id, session,
        )
        assert resultado is False

    def test_otro_docente_no_asignado(
        self, session, otro_profesor, asignacion_docente, instancia_cursado_completa
    ):
        """Un profesor distinto al asignado falla la validacion."""
        service = CalificacionService()
        ic = instancia_cursado_completa["instancia"]

        resultado = service.validar_docente_instancia_cursado(
            otro_profesor.id, ic.id, session,
        )
        assert resultado is False


# ══════════════════════════════════════════════════════════════════════════════
# Consultas de calificaciones
# ══════════════════════════════════════════════════════════════════════════════

class TestConsultasCalificaciones:
    """Consultas de calificaciones por inscripcion y por instancia."""

    def test_calificaciones_de_inscripcion(
        self, session, usuario_docente, inscripcion_cursando, instancia_cursado_completa
    ):
        """Obtener todas las calificaciones de una inscripcion."""
        service = CalificacionService()
        ev1 = instancia_cursado_completa["eval1"]
        ev2 = instancia_cursado_completa["eval2"]

        service.guardar_calificacion(
            usuario_docente.id, inscripcion_cursando.id, ev1.id,
            Decimal("20"), session,
        )
        service.guardar_calificacion(
            usuario_docente.id, inscripcion_cursando.id, ev2.id,
            Decimal("50"), session,
        )

        cals = service.get_calificaciones_inscripcion(inscripcion_cursando.id, session)
        assert len(cals) == 2

    def test_inscripcion_sin_calificaciones(self, session, inscripcion_cursando):
        """Inscripcion sin calificaciones retorna lista vacia."""
        service = CalificacionService()
        cals = service.get_calificaciones_inscripcion(inscripcion_cursando.id, session)
        assert len(cals) == 0
