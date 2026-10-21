from typing import Optional
from decimal import Decimal
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.politica_examen import (
    PoliticaExamen,
    PoliticaExamenCreate,
    PoliticaExamenUpdate,
)


class PoliticaExamenService(BaseServiceWithFilters[PoliticaExamen]):
    def __init__(self):
        super().__init__(PoliticaExamen)

    def get_by_id(self, politica_id: int, session: Session) -> Optional[PoliticaExamen]:
        return session.exec(
            select(PoliticaExamen).where(PoliticaExamen.id == politica_id)
        ).first()

    @staticmethod
    def _validar(
        nota_maxima: Optional[Decimal],
        umbral_aprobacion: Optional[Decimal],
        max_oportunidades: Optional[int],
    ) -> None:
        """Coherencia de la politica de examen."""
        errores = []

        if nota_maxima is None or nota_maxima <= 0:
            errores.append("nota_maxima debe ser mayor a 0")

        if umbral_aprobacion is not None:
            if umbral_aprobacion <= 0:
                errores.append(
                    "umbral_aprobacion debe ser mayor a 0: en 0 cualquier nota aprueba"
                )
            elif nota_maxima is not None and nota_maxima > 0 and umbral_aprobacion > nota_maxima:
                errores.append(
                    f"umbral_aprobacion ({umbral_aprobacion}) supera nota_maxima "
                    f"({nota_maxima}): el examen seria inaprobable"
                )

        if max_oportunidades is not None and max_oportunidades < 1:
            errores.append(
                "max_oportunidades debe ser al menos 1: en 0 nadie podria rendir"
            )

        if errores:
            raise ValueError("Politica de examen invalida: " + "; ".join(errores))

    def create(self, data: PoliticaExamenCreate, session: Session) -> PoliticaExamen:
        self._validar(data.nota_maxima, data.umbral_aprobacion, data.max_oportunidades)
        politica = PoliticaExamen(**data.model_dump())
        session.add(politica)
        session.commit()
        session.refresh(politica)
        return politica

    def update(
        self, politica_id: int, data: PoliticaExamenUpdate, session: Session
    ) -> PoliticaExamen:
        politica = self.get_by_id(politica_id, session)
        if not politica:
            raise ValueError(f"Politica de examen {politica_id} no encontrada")

        update_data = data.model_dump(exclude_unset=True)

        # Igual que en las politicas de calificacion: se valida el combinado y
        # antes de mutar el objeto de la sesion.
        combinado = {
            campo: update_data.get(campo, getattr(politica, campo))
            for campo in ("nota_maxima", "umbral_aprobacion", "max_oportunidades")
        }
        self._validar(**combinado)

        for key, value in update_data.items():
            setattr(politica, key, value)

        session.add(politica)
        session.commit()
        session.refresh(politica)
        return politica

    def delete(self, politica_id: int, session: Session) -> None:
        politica = self.get_by_id(politica_id, session)
        if not politica:
            raise ValueError(f"Politica de examen {politica_id} no encontrada")

        # Verificar que no tenga materias asignadas
        from v2.models.materia import Materia
        materias = session.exec(
            select(Materia).where(Materia.politica_examen_id == politica_id)
        ).first()
        if materias:
            raise ValueError(
                "No se puede eliminar: hay materias usando esta politica de examen"
            )

        session.delete(politica)
        session.commit()
