"""
Tests del flujo completo de inscripcion a materia.

Cubre:
- Inscripcion exitosa (con periodo activo, sin previaturas)
- Validacion de periodo de inscripcion
- Validacion de previaturas en inscripcion
- Duplicado (ya inscripto)
- Materia inactiva
- Instancia de cursado inexistente
- skip_periodo para admin
- Creacion de snapshots al inscribir
- Desinscripcion de materia
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.materia import Materia
from v2.models.enums import (
    EstadoInscripcionMateria, EstadoInstanciaCursado,
)
from v2.services.inscripcion_service import InscripcionMateriaService


# ══════════════════════════════════════════════════════════════════════════════
# Inscripcion exitosa
# ══════════════════════════════════════════════════════════════════════════════

class TestInscripcionExitosa:
    """Flujo de inscripcion a materia exitoso."""

    def test_inscribir_materia_sin_previaturas(
        self, session, usuario_estudiante, materias_con_previaturas,
        instancia_cursado_completa, periodo_activo,
    ):
        """Inscripcion a Prog1 (sin previaturas) con periodo activo."""
        service = InscripcionMateriaService()
        ic = instancia_cursado_completa["instancia"]

        insc = service.inscribir_materia(
            usuario_id=usuario_estudiante.id,
            instancia_cursado_id=ic.id,
            session=session,
        )
        assert insc.id is not None
        assert insc.usuario_id == usuario_estudiante.id
        assert insc.instancia_cursado_id == ic.id
        assert insc.estado == EstadoInscripcionMateria.CURSANDO
        assert insc.faltas == 0
        assert insc.creditos_obtenidos == 0

    def test_inscripcion_crea_snapshot_politica(
        self, session, usuario_estudiante, materias_con_previaturas,
        instancia_cursado_completa, periodo_activo,
    ):
        """La inscripcion crea un snapshot de la politica de calificacion."""
        service = InscripcionMateriaService()
        ic = instancia_cursado_completa["instancia"]

        insc = service.inscribir_materia(
            usuario_id=usuario_estudiante.id,
            instancia_cursado_id=ic.id,
            session=session,
        )
        assert insc.snapshot_politica is not None
        assert "nota_maxima" in insc.snapshot_politica
        assert "umbral_examen" in insc.snapshot_politica
        assert "umbral_exoneracion" in insc.snapshot_politica
        assert insc.snapshot_politica["nota_maxima"] == 100.0

    def test_inscripcion_crea_snapshot_instancias(
        self, session, usuario_estudiante, materias_con_previaturas,
        instancia_cursado_completa, periodo_activo,
    ):
        """La inscripcion crea un snapshot de las instancias de evaluacion."""
        service = InscripcionMateriaService()
        ic = instancia_cursado_completa["instancia"]

        insc = service.inscribir_materia(
            usuario_id=usuario_estudiante.id,
            instancia_cursado_id=ic.id,
            session=session,
        )
        assert insc.snapshot_instancias is not None
        assert len(insc.snapshot_instancias) == 2
        nombres = [s["nombre"] for s in insc.snapshot_instancias]
        assert "Parcial 1" in nombres
        assert "Parcial 2" in nombres

    def test_skip_periodo_para_admin(
        self, session, usuario_estudiante, materias_con_previaturas,
        instancia_cursado_completa,
    ):
        """Con skip_periodo=True no requiere periodo activo (inscripcion manual admin)."""
        service = InscripcionMateriaService()
        ic = instancia_cursado_completa["instancia"]

        # Sin periodo creado, pero con skip_periodo=True
        insc = service.inscribir_materia(
            usuario_id=usuario_estudiante.id,
            instancia_cursado_id=ic.id,
            session=session,
            skip_periodo=True,
        )
        assert insc.id is not None
        assert insc.estado == EstadoInscripcionMateria.CURSANDO


# ══════════════════════════════════════════════════════════════════════════════
# Validacion de periodo
# ══════════════════════════════════════════════════════════════════════════════

class TestInscripcionPeriodo:
    """Validacion del periodo de inscripcion."""

    def test_sin_periodo_activo_falla(
        self, session, usuario_estudiante, materias_con_previaturas,
        instancia_cursado_completa,
    ):
        """Sin periodo activo, la inscripcion falla."""
        service = InscripcionMateriaService()
        ic = instancia_cursado_completa["instancia"]

        with pytest.raises(ValueError, match="periodo de inscripcion activo"):
            service.inscribir_materia(
                usuario_id=usuario_estudiante.id,
                instancia_cursado_id=ic.id,
                session=session,
            )

    def test_periodo_cerrado_falla(
        self, session, usuario_estudiante, materias_con_previaturas,
        instancia_cursado_completa, periodo_cerrado,
    ):
        """Periodo cerrado (fecha_fin pasada) falla."""
        service = InscripcionMateriaService()
        ic = instancia_cursado_completa["instancia"]

        with pytest.raises(ValueError, match="periodo de inscripcion activo"):
            service.inscribir_materia(
                usuario_id=usuario_estudiante.id,
                instancia_cursado_id=ic.id,
                session=session,
            )


# ══════════════════════════════════════════════════════════════════════════════
# Validaciones de inscripcion
# ══════════════════════════════════════════════════════════════════════════════

class TestInscripcionValidaciones:
    """Validaciones al inscribir a una materia."""

    def test_instancia_cursado_inexistente(self, session, usuario_estudiante):
        """Instancia de cursado que no existe lanza error."""
        service = InscripcionMateriaService()

        with pytest.raises(ValueError, match="no encontrada"):
            service.inscribir_materia(
                usuario_id=usuario_estudiante.id,
                instancia_cursado_id=9999,
                session=session,
                skip_periodo=True,
            )

    def test_materia_inactiva(
        self, session, usuario_estudiante, materias_con_previaturas,
        politica_base100, programa,
    ):
        """Materia inactiva rechaza inscripcion."""
        # Crear materia inactiva
        m_inactiva = Materia(
            programa_id=programa.id, nombre="Materia Inactiva",
            codigo="MI_T", semestre=1, creditos=5,
            politica_id=politica_base100.id, activo=False,
        )
        session.add(m_inactiva)
        session.commit()
        session.refresh(m_inactiva)

        ic = InstanciaCursado(
            materia_id=m_inactiva.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.EN_CURSO,
        )
        session.add(ic)
        session.commit()
        session.refresh(ic)

        service = InscripcionMateriaService()

        with pytest.raises(ValueError, match="no esta activa"):
            service.inscribir_materia(
                usuario_id=usuario_estudiante.id,
                instancia_cursado_id=ic.id,
                session=session,
                skip_periodo=True,
            )

    def test_duplicado_cursando_rechazado(
        self, session, usuario_estudiante, materias_con_previaturas,
        instancia_cursado_completa, periodo_activo,
    ):
        """No se puede inscribir dos veces en la misma instancia."""
        service = InscripcionMateriaService()
        ic = instancia_cursado_completa["instancia"]

        # Primera inscripcion OK
        service.inscribir_materia(
            usuario_id=usuario_estudiante.id,
            instancia_cursado_id=ic.id,
            session=session,
        )

        # Segunda inscripcion falla
        with pytest.raises(ValueError, match="Ya estas inscripto"):
            service.inscribir_materia(
                usuario_id=usuario_estudiante.id,
                instancia_cursado_id=ic.id,
                session=session,
            )

    def test_previaturas_no_cumplidas_rechazado(
        self, session, usuario_estudiante, materias_con_previaturas,
        politica_base100, programa, periodo_activo,
    ):
        """Inscripcion a Prog2 sin aprobar Prog1 falla."""
        m2 = materias_con_previaturas["prog2"]

        ic2 = InstanciaCursado(
            materia_id=m2.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.EN_CURSO,
        )
        session.add(ic2)
        session.commit()
        session.refresh(ic2)

        service = InscripcionMateriaService()

        with pytest.raises(ValueError, match="previaturas"):
            service.inscribir_materia(
                usuario_id=usuario_estudiante.id,
                instancia_cursado_id=ic2.id,
                session=session,
            )

    def test_inscripcion_con_previaturas_cumplidas(
        self, session, usuario_estudiante, materias_con_previaturas,
        politica_base100, programa, periodo_activo,
    ):
        """Inscripcion a Prog2 con Prog1 aprobada funciona."""
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
            usuario_id=usuario_estudiante.id,
            instancia_cursado_id=ic1.id,
            estado=EstadoInscripcionMateria.APROBADO,
        )
        session.add(insc1)
        session.commit()

        # Inscribir a Prog2
        ic2 = InstanciaCursado(
            materia_id=m2.id, anio_lectivo=2026,
            estado=EstadoInstanciaCursado.EN_CURSO,
        )
        session.add(ic2)
        session.commit()
        session.refresh(ic2)

        service = InscripcionMateriaService()
        insc2 = service.inscribir_materia(
            usuario_id=usuario_estudiante.id,
            instancia_cursado_id=ic2.id,
            session=session,
        )
        assert insc2.id is not None
        assert insc2.estado == EstadoInscripcionMateria.CURSANDO


# ══════════════════════════════════════════════════════════════════════════════
# Desinscripcion de materia
# ══════════════════════════════════════════════════════════════════════════════

class TestDesinscripcion:
    """Desinscripcion de materia por el alumno."""

    def test_desinscribir_exitoso(
        self, session, usuario_estudiante, materias_con_previaturas,
        instancia_cursado_completa, periodo_activo,
    ):
        """Desinscribirse con estado CURSANDO y periodo activo."""
        service = InscripcionMateriaService()
        ic = instancia_cursado_completa["instancia"]

        insc = service.inscribir_materia(
            usuario_id=usuario_estudiante.id,
            instancia_cursado_id=ic.id,
            session=session,
        )
        inscripcion_id = insc.id

        service.desinscribir_materia(inscripcion_id, usuario_estudiante.id, session)

        # Verificar que se elimino
        assert service.get_by_id(inscripcion_id, session) is None

    def test_desinscribir_no_cursando_falla(
        self, session, usuario_estudiante, inscripcion_cursando,
    ):
        """No se puede desinscribir si no esta CURSANDO."""
        service = InscripcionMateriaService()

        inscripcion_cursando.estado = EstadoInscripcionMateria.A_EXAMEN
        session.add(inscripcion_cursando)
        session.commit()

        with pytest.raises(ValueError, match="CURSANDO"):
            service.desinscribir_materia(
                inscripcion_cursando.id, usuario_estudiante.id, session,
            )

    def test_desinscribir_otro_usuario_falla(
        self, session, usuario_docente, inscripcion_cursando, periodo_activo,
    ):
        """No se puede desinscribir la inscripcion de otro usuario."""
        service = InscripcionMateriaService()

        with pytest.raises(ValueError, match="No es tu inscripcion"):
            service.desinscribir_materia(
                inscripcion_cursando.id, usuario_docente.id, session,
            )

    def test_desinscribir_inscripcion_inexistente(self, session, usuario_estudiante):
        """Desinscribir inscripcion que no existe lanza error."""
        service = InscripcionMateriaService()

        with pytest.raises(ValueError, match="no encontrada"):
            service.desinscribir_materia(9999, usuario_estudiante.id, session)

    def test_desinscribir_sin_periodo_falla(
        self, session, usuario_estudiante, inscripcion_cursando,
    ):
        """No se puede desinscribir fuera de periodo de inscripcion."""
        service = InscripcionMateriaService()

        # Sin periodo activo creado
        with pytest.raises(ValueError, match="periodo"):
            service.desinscribir_materia(
                inscripcion_cursando.id, usuario_estudiante.id, session,
            )
