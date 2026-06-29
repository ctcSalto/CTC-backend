from typing import Optional, List
from decimal import Decimal
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.calificacion import Calificacion
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
from v2.models.docente_materia import DocenteMateria
from v2.models.enums import EstadoInscripcionMateria
from v2.services.grading_engine import calcular_estado

import os
from datetime import datetime
from zoneinfo import ZoneInfo


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class CalificacionService(BaseServiceWithFilters[Calificacion]):
    def __init__(self):
        super().__init__(Calificacion)

    # ── Guardar calificación individual ─────────────────────────────────────

    def guardar_calificacion(
        self,
        docente_id: int,
        inscripcion_id: int,
        instancia_evaluacion_id: int,
        nota: Decimal,
        session: Session,
        equipo_id: Optional[int] = None,
        observaciones: Optional[str] = None,
    ) -> Calificacion:
        """
        Carga o actualiza una calificación (upsert por inscripcion+instancia).
        Recalcula automáticamente el estado de la inscripción.
        """
        # 1. Validar inscripción
        inscripcion = session.exec(
            select(InscripcionMateria).where(InscripcionMateria.id == inscripcion_id)
        ).first()
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")
        if inscripcion.estado not in (
            EstadoInscripcionMateria.CURSANDO,
            EstadoInscripcionMateria.A_EXAMEN,
        ):
            raise ValueError(
                f"No se puede calificar una inscripcion en estado {inscripcion.estado.value}"
            )

        # 2. Validar instancia de evaluación
        instancia = session.exec(
            select(MateriaInstanciaEvaluacion).where(
                MateriaInstanciaEvaluacion.id == instancia_evaluacion_id
            )
        ).first()
        if not instancia:
            raise ValueError(f"Instancia de evaluacion {instancia_evaluacion_id} no encontrada")

        # 3. Validar rango de nota
        nota_decimal = Decimal(str(nota))
        if nota_decimal < 0 or nota_decimal > instancia.peso_maximo:
            raise ValueError(
                f"La nota debe estar entre 0 y {instancia.peso_maximo} (peso maximo de la instancia)"
            )

        # 4. Validar equipo si la instancia es grupal
        if instancia.es_grupal and not equipo_id:
            raise ValueError("La instancia es grupal, se requiere equipo_id")

        # 5. Upsert: buscar calificación existente
        existente = session.exec(
            select(Calificacion).where(
                Calificacion.inscripcion_id == inscripcion_id,
                Calificacion.instancia_evaluacion_id == instancia_evaluacion_id,
            )
        ).first()

        if existente:
            existente.nota = nota_decimal
            existente.docente_id = docente_id
            existente.equipo_id = equipo_id
            existente.observaciones = observaciones
            existente.fecha = datetime.now(get_uruguay_tz())
            session.add(existente)
            session.commit()
            session.refresh(existente)
            calificacion = existente
        else:
            calificacion = Calificacion(
                inscripcion_id=inscripcion_id,
                instancia_evaluacion_id=instancia_evaluacion_id,
                nota=nota_decimal,
                equipo_id=equipo_id,
                docente_id=docente_id,
                observaciones=observaciones,
            )
            session.add(calificacion)
            session.commit()
            session.refresh(calificacion)

        # 6. Recalcular estado
        self._recalcular_estado(inscripcion_id, session)

        return calificacion

    # ── Carga masiva ────────────────────────────────────────────────────────

    def guardar_batch(
        self,
        docente_id: int,
        instancia_evaluacion_id: int,
        calificaciones: list,
        session: Session,
    ) -> dict:
        """
        Carga masiva de notas para una instancia.
        Retorna {exitosos: int, errores: [{inscripcion_id, error}]}
        """
        exitosos = 0
        errores = []

        for item in calificaciones:
            try:
                self.guardar_calificacion(
                    docente_id=docente_id,
                    inscripcion_id=item.inscripcion_id,
                    instancia_evaluacion_id=instancia_evaluacion_id,
                    nota=item.nota,
                    session=session,
                    equipo_id=item.equipo_id,
                    observaciones=item.observaciones,
                )
                exitosos += 1
            except ValueError as e:
                errores.append({
                    "inscripcion_id": item.inscripcion_id,
                    "error": str(e),
                })

        return {"exitosos": exitosos, "errores": errores}

    # ── Consultas ───────────────────────────────────────────────────────────

    def get_calificaciones_inscripcion(
        self, inscripcion_id: int, session: Session
    ) -> List[Calificacion]:
        """Todas las calificaciones de una inscripción"""
        return list(session.exec(
            select(Calificacion)
            .where(Calificacion.inscripcion_id == inscripcion_id)
            .order_by(Calificacion.instancia_evaluacion_id)
        ).all())

    def get_calificaciones_instancia_cursado(
        self,
        instancia_cursado_id: int,
        instancia_evaluacion_id: int,
        session: Session,
    ) -> list:
        """
        Retorna las notas de todos los alumnos en una instancia de evaluación específica.
        Para vista docente: "lista de alumnos de Primer Parcial"
        """
        from v2.models.usuario import Usuario

        # Obtener inscripciones de la instancia de cursado
        inscripciones = session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.instancia_cursado_id == instancia_cursado_id,
            )
        ).all()

        resultado = []
        for insc in inscripciones:
            usuario = session.exec(
                select(Usuario).where(Usuario.id == insc.usuario_id)
            ).first()

            calificacion = session.exec(
                select(Calificacion).where(
                    Calificacion.inscripcion_id == insc.id,
                    Calificacion.instancia_evaluacion_id == instancia_evaluacion_id,
                )
            ).first()

            resultado.append({
                "inscripcion_id": insc.id,
                "usuario_id": insc.usuario_id,
                "nombre": usuario.nombre if usuario else "",
                "apellido": usuario.apellido if usuario else "",
                "nota": float(calificacion.nota) if calificacion else None,
                "calificacion_id": calificacion.id if calificacion else None,
                "observaciones": calificacion.observaciones if calificacion else None,
            })

        return resultado

    # ── Nota final directa ──────────────────────────────────────────────────

    def cargar_nota_final_directa(
        self,
        docente_id: int,
        inscripcion_id: int,
        nota: Decimal,
        session: Session,
    ) -> InscripcionMateria:
        """
        Profesor carga nota final ya promediada, sin pasar por instancias de evaluación.
        Ejecuta el grading engine con todas_instancias_calificadas=True.
        """
        inscripcion = session.exec(
            select(InscripcionMateria).where(InscripcionMateria.id == inscripcion_id)
        ).first()
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")
        if inscripcion.estado != EstadoInscripcionMateria.CURSANDO:
            raise ValueError(
                f"Solo se puede cargar nota final directa en estado CURSANDO (actual: {inscripcion.estado.value})"
            )

        snapshot_pol = inscripcion.snapshot_politica or {}
        nota_maxima = Decimal(str(snapshot_pol.get("nota_maxima", 100)))
        nota_decimal = Decimal(str(nota))

        if nota_decimal < 0 or nota_decimal > nota_maxima:
            raise ValueError(f"La nota debe estar entre 0 y {nota_maxima}")

        # Obtener créditos de la materia via instancia_cursado
        from v2.models.instancia_cursado import InstanciaCursado
        from v2.models.materia import Materia
        instancia_cursado = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
        materia = session.get(Materia, instancia_cursado.materia_id) if instancia_cursado else None
        creditos = materia.creditos if materia else 0

        # Calcular estado con el grading engine
        resultado = calcular_estado(
            nota_curso=nota_decimal,
            snapshot_politica=snapshot_pol,
            creditos_materia=creditos,
            todas_instancias_calificadas=True,
        )

        # Actualizar inscripción
        inscripcion.nota_final_directa = nota_decimal
        inscripcion.nota_curso = resultado["nota_curso"]
        inscripcion.nota_final = resultado["nota_final"]
        inscripcion.estado = resultado["estado"]
        inscripcion.creditos_obtenidos = resultado["creditos_obtenidos"]

        if resultado["estado"] in (
            EstadoInscripcionMateria.EXONERADO,
            EstadoInscripcionMateria.APROBADO,
            EstadoInscripcionMateria.REPROBADO,
        ):
            inscripcion.fecha_cierre = datetime.now(get_uruguay_tz())

        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)
        return inscripcion

    # ── Recálculo automático de estado ──────────────────────────────────────

    def _recalcular_estado(self, inscripcion_id: int, session: Session):
        """
        Recalcula el estado de la inscripción basándose en las calificaciones
        actuales y los snapshots de la política/instancias.
        """
        inscripcion = session.exec(
            select(InscripcionMateria).where(InscripcionMateria.id == inscripcion_id)
        ).first()
        if not inscripcion:
            return

        # No tocar estados manuales
        if inscripcion.estado in (
            EstadoInscripcionMateria.PERDIDO_INASISTENCIA,
            EstadoInscripcionMateria.ABANDONO,
        ):
            return

        snapshot_pol = inscripcion.snapshot_politica or {}
        snapshot_inst = inscripcion.snapshot_instancias or []

        if not snapshot_pol or not snapshot_inst:
            return

        # Cargar todas las calificaciones
        calificaciones = session.exec(
            select(Calificacion).where(Calificacion.inscripcion_id == inscripcion_id)
        ).all()

        # Sumar notas
        nota_total = Decimal("0")
        instancias_calificadas = set()
        for cal in calificaciones:
            nota_total += cal.nota
            instancias_calificadas.add(cal.instancia_evaluacion_id)

        # Verificar si todas las instancias del snapshot están calificadas
        ids_snapshot = {inst["id"] for inst in snapshot_inst}
        todas_calificadas = ids_snapshot.issubset(instancias_calificadas)

        # Obtener créditos de la materia via instancia_cursado
        from v2.models.instancia_cursado import InstanciaCursado
        from v2.models.materia import Materia
        instancia_cursado = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
        materia = session.get(Materia, instancia_cursado.materia_id) if instancia_cursado else None
        creditos = materia.creditos if materia else 0

        # Calcular con el motor
        resultado = calcular_estado(
            nota_curso=nota_total,
            snapshot_politica=snapshot_pol,
            creditos_materia=creditos,
            todas_instancias_calificadas=todas_calificadas,
        )

        # Actualizar inscripción
        inscripcion.estado = resultado["estado"]
        inscripcion.nota_curso = resultado["nota_curso"]
        inscripcion.nota_final = resultado["nota_final"]
        inscripcion.creditos_obtenidos = resultado["creditos_obtenidos"]

        # Si se cerró la inscripción (estado final), marcar fecha
        if resultado["estado"] in (
            EstadoInscripcionMateria.EXONERADO,
            EstadoInscripcionMateria.APROBADO,
            EstadoInscripcionMateria.REPROBADO,
        ):
            inscripcion.fecha_cierre = datetime.now(get_uruguay_tz())

        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)

    # ── Validar asignación docente ──────────────────────────────────────────

    def validar_docente_instancia_cursado(
        self, docente_id: int, instancia_cursado_id: int, session: Session
    ) -> bool:
        """Verifica que el docente esté asignado a la instancia de cursado."""
        asignacion = session.exec(
            select(DocenteMateria).where(
                DocenteMateria.docente_id == docente_id,
                DocenteMateria.instancia_cursado_id == instancia_cursado_id,
            )
        ).first()
        return asignacion is not None
