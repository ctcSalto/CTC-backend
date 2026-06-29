from typing import Optional
from datetime import datetime
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.periodo_inscripcion_materia import (
    PeriodoInscripcionMateria,
    PeriodoInscripcionMateriaCreate,
    PeriodoInscripcionMateriaUpdate,
)

import os
from zoneinfo import ZoneInfo


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class PeriodoInscripcionService(BaseServiceWithFilters[PeriodoInscripcionMateria]):
    def __init__(self):
        super().__init__(PeriodoInscripcionMateria)

    def get_by_id(self, periodo_id: int, session: Session) -> Optional[PeriodoInscripcionMateria]:
        return session.exec(
            select(PeriodoInscripcionMateria).where(PeriodoInscripcionMateria.id == periodo_id)
        ).first()

    def create(self, data: PeriodoInscripcionMateriaCreate, session: Session) -> PeriodoInscripcionMateria:
        # Validar que el programa exista
        from v2.models.programa import Programa
        programa = session.exec(
            select(Programa).where(Programa.id == data.programa_id)
        ).first()
        if not programa:
            raise ValueError(f"Programa {data.programa_id} no encontrado")

        periodo = PeriodoInscripcionMateria(**data.model_dump())
        session.add(periodo)
        session.commit()
        session.refresh(periodo)
        return periodo

    def update(
        self, periodo_id: int, data: PeriodoInscripcionMateriaUpdate, session: Session
    ) -> PeriodoInscripcionMateria:
        periodo = self.get_by_id(periodo_id, session)
        if not periodo:
            raise ValueError(f"Periodo de inscripcion {periodo_id} no encontrado")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(periodo, key, value)

        session.add(periodo)
        session.commit()
        session.refresh(periodo)
        return periodo

    def delete(self, periodo_id: int, session: Session) -> None:
        periodo = self.get_by_id(periodo_id, session)
        if not periodo:
            raise ValueError(f"Periodo de inscripcion {periodo_id} no encontrado")

        session.delete(periodo)
        session.commit()

    def get_periodo_activo(
        self, programa_id: int, anio_lectivo: int, session: Session
    ) -> Optional[PeriodoInscripcionMateria]:
        """Busca un periodo de inscripcion activo (habilitado y dentro de fechas)"""
        ahora = datetime.now(get_uruguay_tz())
        return session.exec(
            select(PeriodoInscripcionMateria).where(
                PeriodoInscripcionMateria.programa_id == programa_id,
                PeriodoInscripcionMateria.anio_lectivo == anio_lectivo,
                PeriodoInscripcionMateria.habilitado == True,
                PeriodoInscripcionMateria.fecha_inicio <= ahora,
                PeriodoInscripcionMateria.fecha_fin >= ahora,
            )
        ).first()
