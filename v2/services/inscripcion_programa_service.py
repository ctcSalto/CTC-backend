from sqlmodel import Session, select
from typing import Optional, List

from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.enums import EstadoInscripcionPrograma
from database.services.filter.filters import BaseServiceWithFilters


class InscripcionProgramaService(BaseServiceWithFilters[InscripcionPrograma]):
    def __init__(self):
        super().__init__(InscripcionPrograma)

    def inscribir_programa(
        self, alumno_id: int, programa_id: int, anio_ingreso: int, session: Session
    ) -> InscripcionPrograma:
        """Inscribe un alumno a un programa. Valida que no exista inscripción activa duplicada."""
        existente = session.exec(
            select(InscripcionPrograma).where(
                InscripcionPrograma.alumno_id == alumno_id,
                InscripcionPrograma.programa_id == programa_id,
                InscripcionPrograma.estado == EstadoInscripcionPrograma.ACTIVA,
            )
        ).first()
        if existente:
            raise ValueError(f"El alumno ya tiene una inscripción activa en este programa (ID: {existente.id})")

        inscripcion = InscripcionPrograma(
            alumno_id=alumno_id,
            programa_id=programa_id,
            anio_ingreso=anio_ingreso,
        )
        session.add(inscripcion)
        session.flush()
        session.refresh(inscripcion)
        return inscripcion

    def get_programas_alumno(self, alumno_id: int, session: Session) -> List[InscripcionPrograma]:
        """Lista todas las inscripciones a programas de un alumno."""
        return list(session.exec(
            select(InscripcionPrograma).where(
                InscripcionPrograma.alumno_id == alumno_id
            )
        ).all())

    def cambiar_estado(
        self, inscripcion_id: int, nuevo_estado: EstadoInscripcionPrograma, session: Session
    ) -> InscripcionPrograma:
        """Cambia el estado de una inscripción a programa."""
        inscripcion = session.get(InscripcionPrograma, inscripcion_id)
        if not inscripcion:
            raise ValueError(f"Inscripción a programa no encontrada: {inscripcion_id}")
        inscripcion.estado = nuevo_estado
        session.flush()
        session.refresh(inscripcion)
        return inscripcion
