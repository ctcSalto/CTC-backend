from typing import Optional, List
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.docente_materia import (
    DocenteMateria,
    DocenteMateriaCreate,
    DocenteMateriaUpdate,
)
from v2.models.profesor import Profesor


class DocenteMateriaService(BaseServiceWithFilters[DocenteMateria]):
    def __init__(self):
        super().__init__(DocenteMateria)

    def get_by_id(
        self, asignacion_id: int, session: Session
    ) -> Optional[DocenteMateria]:
        return session.exec(
            select(DocenteMateria).where(DocenteMateria.id == asignacion_id)
        ).first()

    def get_by_instancia_cursado(
        self, instancia_cursado_id: int, session: Session
    ) -> List[DocenteMateria]:
        return list(session.exec(
            select(DocenteMateria).where(
                DocenteMateria.instancia_cursado_id == instancia_cursado_id,
            )
        ).all())

    def assign(self, data: DocenteMateriaCreate, session: Session) -> DocenteMateria:
        # Validar que el perfil de profesor exista. Ya no hace falta chequear el rol
        # del usuario por separado: tener fila en `profesor` ES la afirmacion de que
        # esa persona es docente, y la FK lo garantiza a nivel de base de datos.
        profesor = session.get(Profesor, data.profesor_id)
        if not profesor:
            raise ValueError(f"Profesor {data.profesor_id} no encontrado")

        # Validar que la instancia de cursado exista
        from v2.models.instancia_cursado import InstanciaCursado
        instancia = session.get(InstanciaCursado, data.instancia_cursado_id)
        if not instancia:
            raise ValueError(f"Instancia de cursado {data.instancia_cursado_id} no encontrada")

        # Validar que no exista la misma asignacion
        existente = session.exec(
            select(DocenteMateria).where(
                DocenteMateria.profesor_id == data.profesor_id,
                DocenteMateria.instancia_cursado_id == data.instancia_cursado_id,
            )
        ).first()
        if existente:
            raise ValueError(
                "Este docente ya esta asignado a esta instancia de cursado"
            )

        asignacion = DocenteMateria(**data.model_dump())
        session.add(asignacion)
        session.commit()
        session.refresh(asignacion)
        return asignacion

    def update(
        self,
        asignacion_id: int,
        data: DocenteMateriaUpdate,
        session: Session,
    ) -> DocenteMateria:
        asignacion = self.get_by_id(asignacion_id, session)
        if not asignacion:
            raise ValueError(f"Asignacion {asignacion_id} no encontrada")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(asignacion, key, value)

        session.add(asignacion)
        session.commit()
        session.refresh(asignacion)
        return asignacion

    def delete(self, asignacion_id: int, session: Session) -> None:
        asignacion = self.get_by_id(asignacion_id, session)
        if not asignacion:
            raise ValueError(f"Asignacion {asignacion_id} no encontrada")

        session.delete(asignacion)
        session.commit()
