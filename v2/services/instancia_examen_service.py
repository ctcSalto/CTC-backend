from sqlmodel import Session, select
from typing import Optional, List

from v2.models.instancia_examen import InstanciaExamen
from v2.models.docente_instancia_examen import DocenteInstanciaExamen
from v2.models.enums import EstadoInstanciaExamen
from database.services.filter.filters import BaseServiceWithFilters

import os
from datetime import datetime
from zoneinfo import ZoneInfo


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class InstanciaExamenService(BaseServiceWithFilters[InstanciaExamen]):
    def __init__(self):
        super().__init__(InstanciaExamen)

    def get_instancias_materia(
        self, materia_id: int, session: Session
    ) -> List[InstanciaExamen]:
        """Lista instancias de examen de una materia."""
        return list(session.exec(
            select(InstanciaExamen).where(
                InstanciaExamen.materia_id == materia_id
            ).order_by(InstanciaExamen.fecha_examen.desc())
        ).all())

    def get_activas(self, session: Session) -> List[InstanciaExamen]:
        """Instancias con inscripción abierta ahora."""
        ahora = datetime.now(get_uruguay_tz()).replace(tzinfo=None)
        return list(session.exec(
            select(InstanciaExamen).where(
                InstanciaExamen.habilitado == True,
                InstanciaExamen.fecha_inicio_inscripcion <= ahora,
                InstanciaExamen.fecha_fin_inscripcion >= ahora,
            )
        ).all())

    def asignar_profesor(
        self, instancia_examen_id: int, docente_id: int, session: Session
    ) -> DocenteInstanciaExamen:
        """Asigna un profesor a una instancia de examen."""
        # Verificar que no exista
        existente = session.exec(
            select(DocenteInstanciaExamen).where(
                DocenteInstanciaExamen.instancia_examen_id == instancia_examen_id,
                DocenteInstanciaExamen.docente_id == docente_id,
            )
        ).first()
        if existente:
            raise ValueError("Este docente ya está asignado a esta instancia de examen")

        asignacion = DocenteInstanciaExamen(
            instancia_examen_id=instancia_examen_id,
            docente_id=docente_id,
        )
        session.add(asignacion)
        session.flush()
        session.refresh(asignacion)
        return asignacion

    def get_profesores(
        self, instancia_examen_id: int, session: Session
    ) -> List[DocenteInstanciaExamen]:
        """Lista profesores asignados a una instancia de examen."""
        return list(session.exec(
            select(DocenteInstanciaExamen).where(
                DocenteInstanciaExamen.instancia_examen_id == instancia_examen_id
            )
        ).all())
