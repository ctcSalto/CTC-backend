"""
Motor de calificaciones — función pura sin acceso a DB.
Recibe datos y retorna el estado calculado de una inscripción.
"""
from decimal import Decimal
from v2.models.enums import EstadoInscripcionMateria


def calcular_estado(
    nota_curso: Decimal,
    snapshot_politica: dict,
    creditos_materia: int,
    todas_instancias_calificadas: bool,
) -> dict:
    """
    Calcula el estado de una inscripción basándose en la nota acumulada
    y la política de calificación snapshot.

    Reglas:
    - Si no todas las instancias están calificadas → CURSANDO
    - umbral_exoneracion y nota >= umbral → EXONERADO (creditos = materia.creditos)
    - umbral_examen y nota >= umbral → A_EXAMEN (sin creditos aún)
    - sin umbral_examen y nota >= umbral_aprobacion → APROBADO (curso corto)
    - nota < mínimo aplicable → REPROBADO (creditos = 0)

    Retorna: {estado, nota_curso, nota_final, creditos_obtenidos}
    """
    nota = Decimal(str(nota_curso))

    # Si faltan instancias por calificar, sigue cursando
    if not todas_instancias_calificadas:
        return {
            "estado": EstadoInscripcionMateria.CURSANDO,
            "nota_curso": nota,
            "nota_final": None,
            "creditos_obtenidos": 0,
        }

    # Extraer umbrales del snapshot
    umbral_exoneracion = (
        Decimal(str(snapshot_politica["umbral_exoneracion"]))
        if snapshot_politica.get("umbral_exoneracion") is not None
        else None
    )
    umbral_examen = (
        Decimal(str(snapshot_politica["umbral_examen"]))
        if snapshot_politica.get("umbral_examen") is not None
        else None
    )
    umbral_aprobacion = (
        Decimal(str(snapshot_politica["umbral_aprobacion"]))
        if snapshot_politica.get("umbral_aprobacion") is not None
        else Decimal("0")
    )

    # 1. ¿Exonera?
    if umbral_exoneracion is not None and nota >= umbral_exoneracion:
        return {
            "estado": EstadoInscripcionMateria.EXONERADO,
            "nota_curso": nota,
            "nota_final": nota,
            "creditos_obtenidos": creditos_materia,
        }

    # 2. ¿Va a examen?
    if umbral_examen is not None:
        if nota >= umbral_examen:
            return {
                "estado": EstadoInscripcionMateria.A_EXAMEN,
                "nota_curso": nota,
                "nota_final": None,  # se define en el examen
                "creditos_obtenidos": 0,
            }
        else:
            # Nota por debajo del umbral de examen → reprobado
            return {
                "estado": EstadoInscripcionMateria.REPROBADO,
                "nota_curso": nota,
                "nota_final": nota,
                "creditos_obtenidos": 0,
            }

    # 3. Curso corto (sin umbral_examen): solo aprobación directa
    if nota >= umbral_aprobacion:
        return {
            "estado": EstadoInscripcionMateria.APROBADO,
            "nota_curso": nota,
            "nota_final": nota,
            "creditos_obtenidos": creditos_materia,
        }

    return {
        "estado": EstadoInscripcionMateria.REPROBADO,
        "nota_curso": nota,
        "nota_final": nota,
        "creditos_obtenidos": 0,
    }
