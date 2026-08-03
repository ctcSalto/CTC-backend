"""
Excepciones de previatura otorgadas por bedelia.

Habilitan a un alumno a cursar una materia sin tener aprobada una previatura
puntual. NO convalidan la materia adeudada: la aprobacion que consiga cursando
bajo excepcion no habilita la materia siguiente mientras la deuda siga abierta.
Ese efecto sale de la regla de cumplimiento pleno en InscripcionMateriaService,
no de una marca guardada aca.
"""
from typing import Optional, List
from datetime import datetime
import os
from zoneinfo import ZoneInfo

from sqlmodel import Session, select, col

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.excepcion_previatura import (
    ExcepcionPreviatura,
    ExcepcionPreviaturaCreate,
)
from v2.models.previatura import Previatura
from v2.models.materia import Materia
from v2.models.alumno import Alumno


def get_uruguay_tz():
    return ZoneInfo(os.getenv('TIME_ZONE', 'America/Montevideo'))


class ExcepcionPreviaturaService(BaseServiceWithFilters[ExcepcionPreviatura]):
    def __init__(self):
        super().__init__(ExcepcionPreviatura)

    def get_by_id(self, excepcion_id: int, session: Session) -> Optional[ExcepcionPreviatura]:
        return session.get(ExcepcionPreviatura, excepcion_id)

    def otorgar(
        self,
        data: ExcepcionPreviaturaCreate,
        otorgada_por_id: int,
        session: Session,
    ) -> ExcepcionPreviatura:
        """Otorga una excepcion para una previatura puntual y un anio lectivo."""
        if not data.motivo or not data.motivo.strip():
            raise ValueError("El motivo de la excepcion es obligatorio")

        alumno = session.get(Alumno, data.alumno_id)
        if not alumno:
            raise ValueError(f"Alumno {data.alumno_id} no encontrado")

        previatura = session.get(Previatura, data.previatura_id)
        if not previatura:
            raise ValueError(f"Previatura {data.previatura_id} no encontrada")

        vigente = self._buscar_vigente(
            data.alumno_id, data.previatura_id, data.anio_lectivo, session
        )
        if vigente:
            raise ValueError(
                f"Ya existe una excepcion vigente para ese alumno y esa previatura "
                f"en {data.anio_lectivo} (id {vigente.id})"
            )

        excepcion = ExcepcionPreviatura(
            alumno_id=data.alumno_id,
            previatura_id=data.previatura_id,
            anio_lectivo=data.anio_lectivo,
            motivo=data.motivo.strip(),
            otorgada_por_id=otorgada_por_id,
        )
        session.add(excepcion)
        session.commit()
        session.refresh(excepcion)
        return excepcion

    def revocar(
        self,
        excepcion_id: int,
        motivo: str,
        revocada_por_id: int,
        session: Session,
    ) -> ExcepcionPreviatura:
        """
        Da de baja una excepcion.

        No toca las inscripciones que se hayan hecho al amparo de ella: si el
        alumno ya se inscribio, esa cursada sigue su curso. Lo que deja de valer
        es la habilitacion para inscribirse de nuevo.
        """
        excepcion = session.get(ExcepcionPreviatura, excepcion_id)
        if not excepcion:
            raise ValueError(f"Excepcion {excepcion_id} no encontrada")
        if excepcion.revocada:
            raise ValueError("La excepcion ya estaba revocada")
        if not motivo or not motivo.strip():
            raise ValueError("El motivo de la revocacion es obligatorio")

        excepcion.revocada = True
        excepcion.fecha_revocacion = datetime.now(get_uruguay_tz())
        excepcion.motivo_revocacion = motivo.strip()
        excepcion.revocada_por_id = revocada_por_id

        session.add(excepcion)
        session.commit()
        session.refresh(excepcion)
        return excepcion

    def listar_de_alumno(
        self,
        alumno_id: int,
        session: Session,
        anio_lectivo: Optional[int] = None,
        incluir_revocadas: bool = False,
    ) -> List[dict]:
        """Excepciones de un alumno con los nombres de las materias resueltos."""
        stmt = select(ExcepcionPreviatura).where(
            ExcepcionPreviatura.alumno_id == alumno_id
        )
        if anio_lectivo is not None:
            stmt = stmt.where(ExcepcionPreviatura.anio_lectivo == anio_lectivo)
        if not incluir_revocadas:
            stmt = stmt.where(ExcepcionPreviatura.revocada == False)

        excepciones = list(session.exec(
            stmt.order_by(col(ExcepcionPreviatura.fecha_otorgamiento).desc())
        ).all())
        if not excepciones:
            return []

        # Nombres en lote, para no consultar por excepcion
        previatura_ids = {e.previatura_id for e in excepciones}
        previaturas = {
            p.id: p for p in session.exec(
                select(Previatura).where(col(Previatura.id).in_(previatura_ids))
            ).all()
        }
        materia_ids = set()
        for prev in previaturas.values():
            materia_ids.update({prev.materia_id, prev.materia_previa_id})
        nombres = {}
        if materia_ids:
            nombres = {
                mid: nombre for mid, nombre in session.exec(
                    select(Materia.id, Materia.nombre).where(
                        col(Materia.id).in_(materia_ids)
                    )
                ).all()
            }

        resultado = []
        for e in excepciones:
            prev = previaturas.get(e.previatura_id)
            resultado.append({
                "id": e.id,
                "alumno_id": e.alumno_id,
                "previatura_id": e.previatura_id,
                "anio_lectivo": e.anio_lectivo,
                "motivo": e.motivo,
                "otorgada_por_id": e.otorgada_por_id,
                "fecha_otorgamiento": e.fecha_otorgamiento.isoformat(),
                "revocada": e.revocada,
                "fecha_revocacion": e.fecha_revocacion.isoformat() if e.fecha_revocacion else None,
                "motivo_revocacion": e.motivo_revocacion,
                "revocada_por_id": e.revocada_por_id,
                "vigente": not e.revocada,
                "materia_id": prev.materia_id if prev else None,
                "materia_nombre": nombres.get(prev.materia_id) if prev else None,
                "materia_previa_id": prev.materia_previa_id if prev else None,
                "materia_previa_nombre": nombres.get(prev.materia_previa_id) if prev else None,
                "id_rastreo": e.id_rastreo,
            })
        return resultado

    @staticmethod
    def _buscar_vigente(
        alumno_id: int, previatura_id: int, anio_lectivo: int, session: Session
    ) -> Optional[ExcepcionPreviatura]:
        return session.exec(
            select(ExcepcionPreviatura).where(
                ExcepcionPreviatura.alumno_id == alumno_id,
                ExcepcionPreviatura.previatura_id == previatura_id,
                ExcepcionPreviatura.anio_lectivo == anio_lectivo,
                ExcepcionPreviatura.revocada == False,
            )
        ).first()
