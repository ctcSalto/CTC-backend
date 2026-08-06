"""
Mesas de examen.

La mesa define el periodo contra el que se cuenta el tope de examenes de un
alumno. Ver v2/models/mesa_examen.py para el porque.
"""
from typing import List, Optional

from sqlmodel import Session, select, col, func

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.mesa_examen import (
    MesaExamen, MesaExamenCreate, MesaExamenUpdate,
)
from v2.models.instancia_examen import InstanciaExamen


class MesaExamenService(BaseServiceWithFilters[MesaExamen]):
    def __init__(self):
        super().__init__(MesaExamen)

    def get_by_id(self, mesa_id: int, session: Session) -> Optional[MesaExamen]:
        return session.get(MesaExamen, mesa_id)

    def crear(self, data: MesaExamenCreate, session: Session) -> MesaExamen:
        self._validar(
            data.fecha_inicio_inscripcion,
            data.fecha_fin_inscripcion,
            data.max_examenes,
        )

        mesa = MesaExamen(**data.model_dump())
        session.add(mesa)
        session.commit()
        session.refresh(mesa)
        return mesa

    def actualizar(
        self, mesa_id: int, data: MesaExamenUpdate, session: Session
    ) -> MesaExamen:
        mesa = session.get(MesaExamen, mesa_id)
        if not mesa:
            raise ValueError(f"Mesa de examen {mesa_id} no encontrada")

        valores = data.model_dump(exclude_unset=True)
        self._validar(
            valores.get("fecha_inicio_inscripcion", mesa.fecha_inicio_inscripcion),
            valores.get("fecha_fin_inscripcion", mesa.fecha_fin_inscripcion),
            valores.get("max_examenes", mesa.max_examenes),
        )

        for campo, valor in valores.items():
            setattr(mesa, campo, valor)

        session.add(mesa)
        session.commit()
        session.refresh(mesa)
        return mesa

    def listar(
        self,
        session: Session,
        anio_lectivo: Optional[int] = None,
        incluir_inactivas: bool = False,
    ) -> List[dict]:
        """Mesas con la cantidad de examenes que tiene cada una."""
        stmt = select(MesaExamen)
        if anio_lectivo is not None:
            stmt = stmt.where(MesaExamen.anio_lectivo == anio_lectivo)
        if not incluir_inactivas:
            stmt = stmt.where(MesaExamen.activo == True)

        mesas = list(session.exec(
            stmt.order_by(
                col(MesaExamen.anio_lectivo).desc(),
                col(MesaExamen.fecha_inicio_inscripcion).desc(),
            )
        ).all())
        if not mesas:
            return []

        # Conteo en lote, para no consultar una vez por mesa
        conteos = dict(session.exec(
            select(
                InstanciaExamen.mesa_examen_id,
                func.count(InstanciaExamen.id),
            )
            .where(col(InstanciaExamen.mesa_examen_id).in_(
                [m.id for m in mesas]
            ))
            .group_by(InstanciaExamen.mesa_examen_id)
        ).all())

        return [
            {
                "id": p.id,
                "nombre": p.nombre,
                "anio_lectivo": p.anio_lectivo,
                "fecha_inicio_inscripcion": p.fecha_inicio_inscripcion.isoformat(),
                "fecha_fin_inscripcion": p.fecha_fin_inscripcion.isoformat(),
                "max_examenes": p.max_examenes,
                "activo": p.activo,
                "examenes": conteos.get(p.id, 0),
                "id_rastreo": p.id_rastreo,
            }
            for p in mesas
        ]

    def eliminar(self, mesa_id: int, session: Session) -> None:
        """
        Borra la mesa, siempre que no tenga examenes colgando.

        Con examenes asignados, borrarla los dejaria sin periodo y volverian a
        contarse por mes calendario sin que nadie se entere. Para dar de baja una
        mesa vieja esta `activo`.
        """
        mesa = session.get(MesaExamen, mesa_id)
        if not mesa:
            raise ValueError(f"Mesa de examen {mesa_id} no encontrada")

        examenes = session.exec(
            select(func.count(InstanciaExamen.id)).where(
                InstanciaExamen.mesa_examen_id == mesa_id
            )
        ).one()
        if examenes:
            raise ValueError(
                f"La mesa tiene {examenes} examenes asignados. Desasignalos "
                f"primero, o marcala como inactiva en vez de borrarla."
            )

        session.delete(mesa)
        session.commit()

    @staticmethod
    def _validar(inicio, fin, max_examenes) -> None:
        if inicio and fin and inicio > fin:
            raise ValueError("La inscripcion no puede cerrar antes de abrir")
        if max_examenes is not None and max_examenes < 1:
            raise ValueError("El maximo de examenes tiene que ser al menos 1")
