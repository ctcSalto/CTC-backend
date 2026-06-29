from typing import Optional, List
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.materia import Materia, MateriaCreate, MateriaUpdate


class MateriaService(BaseServiceWithFilters[Materia]):
    def __init__(self):
        super().__init__(Materia)

    def get_by_id(self, materia_id: int, session: Session) -> Optional[Materia]:
        return session.exec(
            select(Materia).where(Materia.id == materia_id)
        ).first()

    def get_by_programa(self, programa_id: int, session: Session) -> List[Materia]:
        return session.exec(
            select(Materia)
            .where(Materia.programa_id == programa_id)
            .order_by(Materia.semestre, Materia.nombre)
        ).all()

    def create(self, data: MateriaCreate, session: Session) -> Materia:
        # Validar que el programa exista
        from v2.models.programa import Programa
        programa = session.exec(
            select(Programa).where(Programa.id == data.programa_id)
        ).first()
        if not programa:
            raise ValueError(f"Programa {data.programa_id} no encontrado")

        # Validar que la politica de calificacion exista
        from v2.models.politica_calificacion import PoliticaCalificacion
        politica = session.exec(
            select(PoliticaCalificacion).where(PoliticaCalificacion.id == data.politica_id)
        ).first()
        if not politica:
            raise ValueError(f"Politica de calificacion {data.politica_id} no encontrada")

        # Validar politica de examen si se proporciona
        if data.politica_examen_id:
            from v2.models.politica_examen import PoliticaExamen
            politica_examen = session.exec(
                select(PoliticaExamen).where(PoliticaExamen.id == data.politica_examen_id)
            ).first()
            if not politica_examen:
                raise ValueError(f"Politica de examen {data.politica_examen_id} no encontrada")

        materia = Materia(**data.model_dump())
        session.add(materia)
        session.commit()
        session.refresh(materia)
        return materia

    def update(
        self, materia_id: int, data: MateriaUpdate, session: Session
    ) -> Materia:
        materia = self.get_by_id(materia_id, session)
        if not materia:
            raise ValueError(f"Materia {materia_id} no encontrada")

        update_data = data.model_dump(exclude_unset=True)

        # Validar FK si se actualiza politica_id
        if "politica_id" in update_data:
            from v2.models.politica_calificacion import PoliticaCalificacion
            politica = session.exec(
                select(PoliticaCalificacion).where(
                    PoliticaCalificacion.id == update_data["politica_id"]
                )
            ).first()
            if not politica:
                raise ValueError(
                    f"Politica de calificacion {update_data['politica_id']} no encontrada"
                )

        # Validar FK si se actualiza politica_examen_id
        if "politica_examen_id" in update_data and update_data["politica_examen_id"] is not None:
            from v2.models.politica_examen import PoliticaExamen
            politica_examen = session.exec(
                select(PoliticaExamen).where(
                    PoliticaExamen.id == update_data["politica_examen_id"]
                )
            ).first()
            if not politica_examen:
                raise ValueError(
                    f"Politica de examen {update_data['politica_examen_id']} no encontrada"
                )

        for key, value in update_data.items():
            setattr(materia, key, value)

        session.add(materia)
        session.commit()
        session.refresh(materia)
        return materia

    def delete(self, materia_id: int, session: Session) -> None:
        materia = self.get_by_id(materia_id, session)
        if not materia:
            raise ValueError(f"Materia {materia_id} no encontrada")

        # Verificar que no tenga inscripciones
        from v2.models.inscripcion_materia import InscripcionMateria
        inscripcion = session.exec(
            select(InscripcionMateria).where(InscripcionMateria.materia_id == materia_id)
        ).first()
        if inscripcion:
            raise ValueError(
                "No se puede eliminar: la materia tiene inscripciones registradas"
            )

        session.delete(materia)
        session.commit()
