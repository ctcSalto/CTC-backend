from typing import Optional
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.politica_calificacion import (
    PoliticaCalificacion,
    PoliticaCalificacionCreate,
    PoliticaCalificacionUpdate,
)


class PoliticaCalificacionService(BaseServiceWithFilters[PoliticaCalificacion]):
    def __init__(self):
        super().__init__(PoliticaCalificacion)

    def get_by_id(self, politica_id: int, session: Session) -> Optional[PoliticaCalificacion]:
        return session.exec(
            select(PoliticaCalificacion).where(PoliticaCalificacion.id == politica_id)
        ).first()

    def create(self, data: PoliticaCalificacionCreate, session: Session) -> PoliticaCalificacion:
        politica = PoliticaCalificacion(**data.model_dump())
        session.add(politica)
        session.commit()
        session.refresh(politica)
        return politica

    def update(
        self, politica_id: int, data: PoliticaCalificacionUpdate, session: Session
    ) -> PoliticaCalificacion:
        politica = self.get_by_id(politica_id, session)
        if not politica:
            raise ValueError(f"Politica de calificacion {politica_id} no encontrada")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(politica, key, value)

        session.add(politica)
        session.commit()
        session.refresh(politica)
        return politica

    def delete(self, politica_id: int, session: Session) -> None:
        politica = self.get_by_id(politica_id, session)
        if not politica:
            raise ValueError(f"Politica de calificacion {politica_id} no encontrada")

        # Verificar que no tenga materias asignadas
        from v2.models.materia import Materia
        materias = session.exec(
            select(Materia).where(Materia.politica_id == politica_id)
        ).first()
        if materias:
            raise ValueError(
                "No se puede eliminar: hay materias usando esta politica de calificacion"
            )

        session.delete(politica)
        session.commit()
