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

    def crear(self, data, session: Session) -> InstanciaExamen:
        """
        Crea la instancia completando la ventana de inscripcion desde la mesa.

        Si viene con `mesa_examen_id` y sin fechas, se copian de la mesa: es
        el dato que antes habia que repetir en cada examen, con el riesgo de que
        dos examenes de la misma mesa terminaran con ventanas distintas.

        Es una copia al crear, no una herencia viva. Editar la mesa despues no
        reescribe los examenes ya cargados, y a proposito: la ventana efectiva
        sigue siendo la de la instancia, que es la que leen el chequeo de plazo,
        las notificaciones y los proximos eventos. Un solo lugar de lectura.
        """
        from v2.models.mesa_examen import MesaExamen

        valores = data.model_dump(exclude_unset=True)
        mesa_id = valores.get("mesa_examen_id")

        mesa = None
        if mesa_id is not None:
            mesa = session.get(MesaExamen, mesa_id)
            if not mesa:
                raise ValueError(f"Mesa de examen {mesa_id} no encontrada")
            if not mesa.activo:
                raise ValueError(f"La mesa '{mesa.nombre}' esta inactiva")

        for campo in ("fecha_inicio_inscripcion", "fecha_fin_inscripcion"):
            if valores.get(campo) is None:
                if mesa is None:
                    raise ValueError(
                        f"Falta {campo}. Se puede omitir solo si se indica una "
                        f"mesa de examen, para copiarla de ahi."
                    )
                valores[campo] = getattr(mesa, campo)

        if valores["fecha_inicio_inscripcion"] > valores["fecha_fin_inscripcion"]:
            raise ValueError(
                "La inscripcion no puede cerrar antes de abrir"
            )

        instancia = InstanciaExamen(**valores)
        session.add(instancia)
        session.flush()
        session.refresh(instancia)
        return instancia

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
        self, instancia_examen_id: int, profesor_id: int, session: Session
    ) -> DocenteInstanciaExamen:
        """Asigna un profesor a una instancia de examen."""
        # Verificar que no exista
        existente = session.exec(
            select(DocenteInstanciaExamen).where(
                DocenteInstanciaExamen.instancia_examen_id == instancia_examen_id,
                DocenteInstanciaExamen.profesor_id == profesor_id,
            )
        ).first()
        if existente:
            raise ValueError("Este docente ya está asignado a esta instancia de examen")

        asignacion = DocenteInstanciaExamen(
            instancia_examen_id=instancia_examen_id,
            profesor_id=profesor_id,
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
