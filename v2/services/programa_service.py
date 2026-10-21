from typing import Optional, List
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.programa import Programa, ProgramaCreate, ProgramaUpdate


class ProgramaService(BaseServiceWithFilters[Programa]):
    def __init__(self):
        super().__init__(Programa)

    def get_by_id(self, programa_id: int, session: Session) -> Optional[Programa]:
        return session.exec(
            select(Programa).where(Programa.id == programa_id)
        ).first()

    def get_con_materias(self, programa_id: int, session: Session) -> Optional[Programa]:
        return session.exec(
            select(Programa)
            .where(Programa.id == programa_id)
            .options(selectinload(Programa.materias))
        ).first()

    def create(self, data: ProgramaCreate, session: Session) -> Programa:
        programa = Programa(**data.model_dump())
        session.add(programa)
        session.commit()
        session.refresh(programa)
        return programa

    def update(
        self, programa_id: int, data: ProgramaUpdate, session: Session
    ) -> Programa:
        programa = self.get_by_id(programa_id, session)
        if not programa:
            raise ValueError(f"Programa {programa_id} no encontrado")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(programa, key, value)

        session.add(programa)
        session.commit()
        session.refresh(programa)
        return programa

    def delete(self, programa_id: int, session: Session) -> None:
        programa = self.get_by_id(programa_id, session)
        if not programa:
            raise ValueError(f"Programa {programa_id} no encontrado")

        # Verificar que no tenga materias
        from v2.models.materia import Materia
        materia = session.exec(
            select(Materia).where(Materia.programa_id == programa_id)
        ).first()
        if materia:
            raise ValueError(
                "No se puede eliminar: el programa tiene materias asignadas"
            )

        # Un programa sin materias puede tener igual alumnos inscriptos o periodos
        # cargados. Sin estos guards el borrado no fallaba con un mensaje sino con
        # una violacion de foreign key, que sale como 500.
        from v2.models.inscripcion_programa import InscripcionPrograma
        inscripcion = session.exec(
            select(InscripcionPrograma).where(
                InscripcionPrograma.programa_id == programa_id
            )
        ).first()
        if inscripcion:
            raise ValueError(
                "No se puede eliminar: el programa tiene alumnos inscriptos"
            )

        from v2.models.periodo_inscripcion_materia import PeriodoInscripcionMateria
        periodo = session.exec(
            select(PeriodoInscripcionMateria).where(
                PeriodoInscripcionMateria.programa_id == programa_id
            )
        ).first()
        if periodo:
            raise ValueError(
                "No se puede eliminar: el programa tiene periodos de inscripcion cargados"
            )

        session.delete(programa)
        session.commit()
