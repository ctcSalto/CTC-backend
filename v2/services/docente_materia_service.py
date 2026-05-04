from typing import Optional, List
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.docente_materia import (
    DocenteMateria,
    DocenteMateriaCreate,
    DocenteMateriaUpdate,
)
from v2.models.usuario import Usuario
from v2.models.enums import RolUsuario


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
        # Validar que el docente exista y tenga rol DOCENTE
        docente = session.exec(
            select(Usuario).where(Usuario.id == data.docente_id)
        ).first()
        if not docente:
            raise ValueError(f"Usuario {data.docente_id} no encontrado")
        if docente.rol != RolUsuario.DOCENTE:
            raise ValueError(
                f"El usuario {data.docente_id} no tiene rol DOCENTE"
            )

        # Validar que la instancia de cursado exista
        from v2.models.instancia_cursado import InstanciaCursado
        instancia = session.get(InstanciaCursado, data.instancia_cursado_id)
        if not instancia:
            raise ValueError(f"Instancia de cursado {data.instancia_cursado_id} no encontrada")

        # Validar que no exista la misma asignacion
        existente = session.exec(
            select(DocenteMateria).where(
                DocenteMateria.docente_id == data.docente_id,
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
