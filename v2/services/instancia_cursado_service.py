from sqlmodel import Session, select
from typing import Optional, List
from decimal import Decimal

from v2.models.instancia_cursado import InstanciaCursado
from v2.models.enums import EstadoInstanciaCursado
from database.services.filter.filters import BaseServiceWithFilters


class InstanciaCursadoService(BaseServiceWithFilters[InstanciaCursado]):
    def __init__(self):
        super().__init__(InstanciaCursado)

    def get_by_materia_anio(
        self, materia_id: int, anio_lectivo: int, session: Session
    ) -> Optional[InstanciaCursado]:
        """Helper de compatibilidad: busca instancia por materia + año."""
        return session.exec(
            select(InstanciaCursado).where(
                InstanciaCursado.materia_id == materia_id,
                InstanciaCursado.anio_lectivo == anio_lectivo,
            )
        ).first()

    def get_activas(self, anio_lectivo: int, session: Session) -> List[InstanciaCursado]:
        """Lista instancias activas (no canceladas) para un año."""
        return list(session.exec(
            select(InstanciaCursado).where(
                InstanciaCursado.anio_lectivo == anio_lectivo,
                InstanciaCursado.estado != EstadoInstanciaCursado.CANCELADA,
            )
        ).all())

    def actualizar_estadisticas(self, instancia_id: int, session: Session) -> InstanciaCursado:
        """Recalcula estadísticas de la instancia (aprobados, reprobados, etc.)."""
        from v2.models.inscripcion_materia import InscripcionMateria
        from v2.models.enums import EstadoInscripcionMateria

        instancia = session.get(InstanciaCursado, instancia_id)
        if not instancia:
            raise ValueError(f"Instancia de cursado no encontrada: {instancia_id}")

        inscripciones = session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.instancia_cursado_id == instancia_id
            )
        ).all()

        total = len(inscripciones)
        por_estado = {}
        for insc in inscripciones:
            estado = insc.estado.value
            por_estado[estado] = por_estado.get(estado, 0) + 1

        # Calcular promedios y tasas
        notas = [float(i.nota_curso) for i in inscripciones if i.nota_curso is not None]
        promedio_notas = round(sum(notas) / len(notas), 2) if notas else None

        aprobados = por_estado.get(EstadoInscripcionMateria.APROBADO.value, 0) + por_estado.get(EstadoInscripcionMateria.EXONERADO.value, 0)
        tasa_aprobacion = round(aprobados / total * 100, 2) if total > 0 else 0

        # Tasa de asistencia basada en faltas
        if instancia.faltas_maximas and instancia.faltas_maximas > 0:
            faltas_promedio = sum(i.faltas for i in inscripciones) / total if total > 0 else 0
            tasa_asistencia = round((1 - faltas_promedio / instancia.faltas_maximas) * 100, 2)
        else:
            tasa_asistencia = None

        instancia.estadisticas = {
            "total_inscriptos": total,
            "por_estado": por_estado,
            "promedio_notas": promedio_notas,
            "tasa_aprobacion": tasa_aprobacion,
            "tasa_asistencia": tasa_asistencia,
        }
        session.flush()
        session.refresh(instancia)
        return instancia

    def get_detalle_completo(self, instancia_id: int, session: Session) -> dict:
        """Detalle completo de una instancia de cursado para el docente."""
        from v2.models.inscripcion_materia import InscripcionMateria
        from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
        from v2.models.materia import Materia

        instancia = session.get(InstanciaCursado, instancia_id)
        if not instancia:
            raise ValueError(f"Instancia de cursado no encontrada: {instancia_id}")

        materia = session.get(Materia, instancia.materia_id)
        total_inscriptos = len(list(session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.instancia_cursado_id == instancia_id
            )
        ).all()))

        evaluaciones = session.exec(
            select(MateriaInstanciaEvaluacion).where(
                MateriaInstanciaEvaluacion.instancia_cursado_id == instancia_id,
            ).order_by(MateriaInstanciaEvaluacion.orden)
        ).all()

        return {
            "instancia_cursado_id": instancia.id,
            "materia_id": instancia.materia_id,
            "materia_nombre": materia.nombre if materia else "",
            "materia_codigo": materia.codigo if materia else "",
            "anio_lectivo": instancia.anio_lectivo,
            "salon": instancia.salon,
            "horario": instancia.horario,
            "fecha_inicio": instancia.fecha_inicio.isoformat() if instancia.fecha_inicio else None,
            "fecha_fin": instancia.fecha_fin.isoformat() if instancia.fecha_fin else None,
            "estado": instancia.estado.value,
            "cupo_maximo": instancia.cupo_maximo,
            "faltas_maximas": instancia.faltas_maximas,
            "total_inscriptos": total_inscriptos,
            "evaluaciones": [
                {
                    "id": ev.id,
                    "nombre": ev.nombre,
                    "peso_maximo": float(ev.peso_maximo) if ev.peso_maximo else None,
                    "orden": ev.orden,
                    "es_grupal": ev.es_grupal,
                    "activo": ev.activo,
                }
                for ev in evaluaciones
            ],
        }

    def get_resultados(self, instancia_id: int, session: Session) -> dict:
        """Tabla completa de resultados para acta de cursado."""
        from v2.models.inscripcion_materia import InscripcionMateria
        from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
        from v2.models.calificacion import Calificacion
        from v2.models.usuario import Usuario
        from v2.models.alumno import Alumno
        from v2.models.materia import Materia

        instancia = session.get(InstanciaCursado, instancia_id)
        if not instancia:
            raise ValueError(f"Instancia de cursado no encontrada: {instancia_id}")

        materia = session.get(Materia, instancia.materia_id)

        # Evaluaciones
        evaluaciones = list(session.exec(
            select(MateriaInstanciaEvaluacion).where(
                MateriaInstanciaEvaluacion.instancia_cursado_id == instancia_id,
            ).order_by(MateriaInstanciaEvaluacion.orden)
        ).all())

        # Inscripciones
        inscripciones = list(session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.instancia_cursado_id == instancia_id
            )
        ).all())

        alumnos = []
        for insc in inscripciones:
            usuario = session.exec(
                select(Usuario)
                .join(Alumno, Alumno.usuario_id == Usuario.id)
                .where(Alumno.id == insc.alumno_id)
            ).first()

            # Calificaciones por evaluación
            calificaciones = session.exec(
                select(Calificacion).where(Calificacion.inscripcion_id == insc.id)
            ).all()
            cal_por_eval = {c.instancia_evaluacion_id: float(c.nota) if c.nota is not None else None for c in calificaciones}

            notas_evaluaciones = []
            for ev in evaluaciones:
                notas_evaluaciones.append({
                    "instancia_evaluacion_id": ev.id,
                    "nombre": ev.nombre,
                    "nota": cal_por_eval.get(ev.id),
                })

            alumnos.append({
                "inscripcion_id": insc.id,
                "alumno_id": insc.alumno_id,
                "nombre": usuario.nombre if usuario else "",
                "apellido": usuario.apellido if usuario else "",
                "estado": insc.estado.value,
                "nota_curso": float(insc.nota_curso) if insc.nota_curso else None,
                "nota_final": float(insc.nota_final) if insc.nota_final else None,
                "faltas": insc.faltas,
                "notas_evaluaciones": notas_evaluaciones,
            })

        return {
            "instancia_cursado_id": instancia.id,
            "materia_nombre": materia.nombre if materia else "",
            "materia_codigo": materia.codigo if materia else "",
            "anio_lectivo": instancia.anio_lectivo,
            "estado": instancia.estado.value,
            "evaluaciones": [{"id": ev.id, "nombre": ev.nombre, "orden": ev.orden} for ev in evaluaciones],
            "alumnos": alumnos,
        }
