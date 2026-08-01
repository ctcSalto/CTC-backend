from sqlmodel import Session, select
from typing import List

from v2.models.materia import Materia
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.programa import Programa
from v2.models.enums import EstadoInscripcionMateria


class EgresoService:
    """Servicio para verificar requisitos de egreso de un alumno en un programa."""

    # Estados en los que la materia se considera cumplida para el egreso: los
    # tres otorgan creditos. A_EXAMEN no entra, la materia todavia no esta cerrada.
    ESTADOS_CUMPLIDA = (
        EstadoInscripcionMateria.APROBADO,
        EstadoInscripcionMateria.EXONERADO,
        EstadoInscripcionMateria.REVALIDADA,
    )

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

        # 3. Inscripciones del alumno que dan la materia por cumplida.
        # No alcanza con APROBADO: EXONERADO tambien otorga creditos (lo asigna
        # grading_engine al cerrar el curso) y REVALIDADA tambien (lo asigna
        # revalidar()). Contando solo APROBADO, un alumno que exonero todo veia
        # cero creditos y no podia egresar nunca.
        filas = list(session.exec(
            select(InscripcionMateria, InstanciaCursado)
            .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .where(
                InscripcionMateria.alumno_id == alumno_id,
                InstanciaCursado.materia_id.in_(materia_ids),
                InscripcionMateria.estado.in_(self.ESTADOS_CUMPLIDA),
            )
        ).all())

        # Una materia puede tener varias inscripciones cumplidas (recursadas).
        # Nos queda la del anio lectivo mas reciente, igual criterio que la
        # escolaridad, para que las notas del detalle no dependan del orden que
        # devuelva la base.
        cumplida_por_materia: dict[int, tuple[InscripcionMateria, int]] = {}
        for insc, ic in filas:
            elegida = cumplida_por_materia.get(ic.materia_id)
            if elegida is None or ic.anio_lectivo > elegida[1]:
                cumplida_por_materia[ic.materia_id] = (insc, ic.anio_lectivo)

        creditos_obtenidos = sum(
            m.creditos for m in materias if m.id in cumplida_por_materia
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
            elegida = cumplida_por_materia.get(m.id)
            if elegida:
                insc, anio_lectivo = elegida
                # El estado importa: una materia revalidada no tiene notas, y sin
                # este campo el cliente no puede distinguirla de una aprobada.
                info["estado"] = insc.estado.value
                info["anio_lectivo"] = anio_lectivo
                # Comparar con None y no por verdad: una nota 0 es una nota, y
                # con `if insc.nota_final` se informaba como "sin nota".
                info["nota_final"] = float(insc.nota_final) if insc.nota_final is not None else None
                info["nota_curso"] = float(insc.nota_curso) if insc.nota_curso is not None else None
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
