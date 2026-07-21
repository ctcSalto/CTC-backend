from sqlmodel import Session, select
from typing import List

from v2.models.materia import Materia
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.programa import Programa
from v2.models.enums import EstadoInscripcionMateria


class EgresoService:
    """Servicio para verificar requisitos de egreso de un alumno en un programa."""

    def verificar_egreso(
        self,
        alumno_id: int,
        programa_id: int,
        session: Session,
    ) -> dict:
        """
        Verifica si un alumno cumple los requisitos de egreso de un programa.
        Retorna detalle de materias aprobadas, pendientes, créditos y porcentaje.
        """
        # 1. Obtener programa y sus créditos requeridos
        programa = session.get(Programa, programa_id)
        if not programa:
            raise ValueError(f"Programa {programa_id} no encontrado")

        # 2. Obtener todas las materias activas del programa
        materias = list(session.exec(
            select(Materia).where(
                Materia.programa_id == programa_id,
                Materia.activo == True,
            )
        ).all())

        materia_ids = [m.id for m in materias]
        creditos_totales = sum(m.creditos for m in materias)
        creditos_requeridos = programa.creditos_requeridos or creditos_totales

        # 3. Obtener inscripciones APROBADAS del alumno en materias del programa
        # Navegamos via InstanciaCursado para conectar inscripcion → materia
        inscripciones_aprobadas = list(session.exec(
            select(InscripcionMateria, InstanciaCursado)
            .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .where(
                InscripcionMateria.alumno_id == alumno_id,
                InstanciaCursado.materia_id.in_(materia_ids),
                InscripcionMateria.estado == EstadoInscripcionMateria.APROBADO,
            )
        ).all())

        # Materias aprobadas (usar set para evitar duplicados si aprobó en distintas instancias)
        materias_aprobadas_ids = set()
        for insc, ic in inscripciones_aprobadas:
            materias_aprobadas_ids.add(ic.materia_id)

        creditos_obtenidos = sum(
            m.creditos for m in materias if m.id in materias_aprobadas_ids
        )

        # 4. Construir detalle
        materias_aprobadas = []
        materias_pendientes = []

        for m in materias:
            info = {
                "materia_id": m.id,
                "nombre": m.nombre,
                "codigo": m.codigo,
                "semestre": m.semestre,
                "creditos": m.creditos,
            }
            if m.id in materias_aprobadas_ids:
                # Buscar la nota final de la inscripcion aprobada
                for insc, ic in inscripciones_aprobadas:
                    if ic.materia_id == m.id:
                        info["nota_final"] = float(insc.nota_final) if insc.nota_final else None
                        info["nota_curso"] = float(insc.nota_curso) if insc.nota_curso else None
                        break
                materias_aprobadas.append(info)
            else:
                materias_pendientes.append(info)

        porcentaje_avance = round(
            (creditos_obtenidos / creditos_requeridos * 100) if creditos_requeridos > 0 else 0,
            2,
        )

        cumple = creditos_obtenidos >= creditos_requeridos and len(materias_pendientes) == 0

        return {
            "cumple": cumple,
            "programa_id": programa_id,
            "programa_nombre": programa.nombre,
            "creditos_obtenidos": creditos_obtenidos,
            "creditos_requeridos": creditos_requeridos,
            "creditos_totales_plan": creditos_totales,
            "materias_aprobadas": len(materias_aprobadas),
            "materias_pendientes": len(materias_pendientes),
            "materias_totales": len(materias),
            "porcentaje_avance": porcentaje_avance,
            "detalle_aprobadas": materias_aprobadas,
            "detalle_pendientes": materias_pendientes,
        }
