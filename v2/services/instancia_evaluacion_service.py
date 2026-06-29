from typing import Optional, List
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.materia_instancia_evaluacion import (
    MateriaInstanciaEvaluacion,
    InstanciaEvaluacionCreate,
    InstanciaEvaluacionUpdate,
)


class InstanciaEvaluacionService(BaseServiceWithFilters[MateriaInstanciaEvaluacion]):
    def __init__(self):
        super().__init__(MateriaInstanciaEvaluacion)

    def get_by_id(
        self, instancia_id: int, session: Session
    ) -> Optional[MateriaInstanciaEvaluacion]:
        return session.exec(
            select(MateriaInstanciaEvaluacion).where(
                MateriaInstanciaEvaluacion.id == instancia_id
            )
        ).first()

    def get_by_instancia_cursado(
        self, instancia_cursado_id: int, session: Session
    ) -> List[MateriaInstanciaEvaluacion]:
        """Obtiene instancias de evaluación de una instancia de cursado."""
        return list(session.exec(
            select(MateriaInstanciaEvaluacion)
            .where(
                MateriaInstanciaEvaluacion.instancia_cursado_id == instancia_cursado_id,
            )
            .order_by(MateriaInstanciaEvaluacion.orden)
        ).all())

    def create(
        self, data: InstanciaEvaluacionCreate, session: Session
    ) -> MateriaInstanciaEvaluacion:
        # Validar que la instancia de cursado exista
        from v2.models.instancia_cursado import InstanciaCursado
        instancia_cursado = session.get(InstanciaCursado, data.instancia_cursado_id)
        if not instancia_cursado:
            raise ValueError(f"Instancia de cursado {data.instancia_cursado_id} no encontrada")

        instancia = MateriaInstanciaEvaluacion(**data.model_dump())
        session.add(instancia)
        session.commit()
        session.refresh(instancia)
        return instancia

    def update(
        self,
        instancia_id: int,
        data: InstanciaEvaluacionUpdate,
        session: Session,
    ) -> MateriaInstanciaEvaluacion:
        instancia = self.get_by_id(instancia_id, session)
        if not instancia:
            raise ValueError(f"Instancia de evaluacion {instancia_id} no encontrada")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(instancia, key, value)

        session.add(instancia)
        session.commit()
        session.refresh(instancia)
        return instancia

    def delete(self, instancia_id: int, session: Session) -> None:
        instancia = self.get_by_id(instancia_id, session)
        if not instancia:
            raise ValueError(f"Instancia de evaluacion {instancia_id} no encontrada")

        # Verificar que no tenga calificaciones
        from v2.models.calificacion import Calificacion
        calificacion = session.exec(
            select(Calificacion).where(
                Calificacion.instancia_evaluacion_id == instancia_id
            )
        ).first()
        if calificacion:
            raise ValueError(
                "No se puede eliminar: la instancia tiene calificaciones registradas"
            )

        session.delete(instancia)
        session.commit()
