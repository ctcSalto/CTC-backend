from typing import Optional, List
from decimal import Decimal
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_examen import InstanciaExamen
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.materia import Materia
from v2.models.politica_examen import PoliticaExamen
from v2.models.enums import EstadoInscripcionMateria, EstadoInscripcionExamen

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class InscripcionExamenService(BaseServiceWithFilters[InscripcionExamen]):
    def __init__(self):
        super().__init__(InscripcionExamen)

    # -- Inscribir a examen ---------------------------------------------------

    def inscribir_examen(
        self,
        inscripcion_materia_id: int,
        instancia_examen_id: int,
        session: Session,
        bypass_periodo: bool = False,
    ) -> InscripcionExamen:
        """
        Inscribe un estudiante a un examen.
        Validaciones:
          - La inscripcion_materia debe estar en estado A_EXAMEN
          - No debe tener otra inscripcion INSCRIPTO en la misma instancia
          - La instancia debe estar activa (salvo bypass_periodo para admin)
          - La materia debe tener politica_examen_id
        """
        # 1. Validar inscripcion materia
        inscripcion = session.exec(
            select(InscripcionMateria).where(InscripcionMateria.id == inscripcion_materia_id)
        ).first()
        if not inscripcion:
            raise ValueError(f"Inscripcion a materia {inscripcion_materia_id} no encontrada")
        if inscripcion.estado != EstadoInscripcionMateria.A_EXAMEN:
            raise ValueError(
                f"La inscripcion debe estar en estado A_EXAMEN, estado actual: {inscripcion.estado.value}"
            )

        # 2. Validar instancia de examen
        instancia = session.exec(
            select(InstanciaExamen).where(InstanciaExamen.id == instancia_examen_id)
        ).first()
        if not instancia:
            raise ValueError(f"Instancia de examen {instancia_examen_id} no encontrada")

        if not bypass_periodo:
            ahora = datetime.now(get_uruguay_tz()).replace(tzinfo=None)
            if not instancia.habilitado:
                raise ValueError("La instancia de examen no esta habilitada")
            if ahora < instancia.fecha_inicio_inscripcion or ahora > instancia.fecha_fin_inscripcion:
                raise ValueError("Fuera del plazo de inscripcion a examen")

        # 3. Verificar duplicado
        duplicado = session.exec(
            select(InscripcionExamen).where(
                InscripcionExamen.inscripcion_materia_id == inscripcion_materia_id,
                InscripcionExamen.instancia_examen_id == instancia_examen_id,
                InscripcionExamen.estado == EstadoInscripcionExamen.INSCRIPTO,
            )
        ).first()
        if duplicado:
            raise ValueError("Ya existe una inscripcion pendiente a examen en esta instancia")

        # 4. Obtener materia via instancia_cursado y validar política de examen
        ic = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
        materia = session.get(Materia, ic.materia_id) if ic else None
        if not materia or not materia.politica_examen_id:
            raise ValueError("La materia no tiene politica de examen configurada")

        # 5. Crear snapshot de politica de examen
        snapshot = self._crear_snapshot_politica_examen(materia.politica_examen_id, session)

        # 6. Validar max oportunidades de rendicion
        politica = session.get(PoliticaExamen, materia.politica_examen_id)
        max_oportunidades = politica.max_oportunidades if politica else 5

        rendiciones_previas = self._contar_rendiciones_previas(
            inscripcion_materia_id, session
        )
        if rendiciones_previas >= max_oportunidades:
            raise ValueError(
                f"Superaste el maximo de oportunidades ({max_oportunidades}). "
                "Debes recursar la materia."
            )
        numero_rendicion = rendiciones_previas + 1

        # 7. Crear inscripcion
        inscripcion_examen = InscripcionExamen(
            inscripcion_materia_id=inscripcion_materia_id,
            instancia_examen_id=instancia_examen_id,
            snapshot_politica_examen=snapshot,
            numero_rendicion=numero_rendicion,
        )
        session.add(inscripcion_examen)
        session.commit()
        session.refresh(inscripcion_examen)

        # Notificación (best-effort, no crítica)
        try:
            from v2.services import get_v2_services
            from v2.models.usuario import Usuario
            from v2.models.materia import Materia
            usuario = session.get(Usuario, inscripcion_materia.usuario_id)
            instancia = session.get(InstanciaExamen, instancia_examen_id)
            ic_obj = session.get(InstanciaCursado, inscripcion_materia.instancia_cursado_id)
            materia = session.get(Materia, ic_obj.materia_id) if ic_obj else None
            if usuario and instancia and materia:
                get_v2_services().notificationService.notificar_inscripcion_examen(
                    inscripcion_examen, usuario, materia, instancia, session
                )
        except Exception:
            pass

        return inscripcion_examen

    # -- Calificar examen -----------------------------------------------------

    def calificar_examen(
        self,
        inscripcion_examen_id: int,
        nota_examen: Decimal,
        session: Session,
    ) -> InscripcionExamen:
        """
        Califica un examen y actualiza el estado de la inscripcion materia.
        - nota >= umbral_aprobacion -> APROBADO (examen y materia)
        - nota < umbral_aprobacion -> REPROBADO (examen), materia queda A_EXAMEN
        """
        ie = session.exec(
            select(InscripcionExamen).where(InscripcionExamen.id == inscripcion_examen_id)
        ).first()
        if not ie:
            raise ValueError(f"Inscripcion a examen {inscripcion_examen_id} no encontrada")
        if ie.estado != EstadoInscripcionExamen.INSCRIPTO:
            raise ValueError(
                f"Solo se puede calificar una inscripcion en estado INSCRIPTO, actual: {ie.estado.value}"
            )

        snapshot = ie.snapshot_politica_examen or {}
        nota_maxima = Decimal(str(snapshot.get("nota_maxima", 100)))
        umbral = Decimal(str(snapshot.get("umbral_aprobacion", 60)))

        nota = Decimal(str(nota_examen))
        if nota < 0 or nota > nota_maxima:
            raise ValueError(f"La nota debe estar entre 0 y {nota_maxima}")

        ie.nota_examen = nota

        if nota >= umbral:
            ie.estado = EstadoInscripcionExamen.APROBADO
            self._aprobar_materia(ie.inscripcion_materia_id, nota, session)
        else:
            ie.estado = EstadoInscripcionExamen.REPROBADO
            # Verificar si agotó todas las oportunidades
            max_oport = int(snapshot.get("max_oportunidades", 5))
            rendiciones = self._contar_rendiciones_previas(ie.inscripcion_materia_id, session)
            if rendiciones >= max_oport:
                self._reprobar_materia_por_rendiciones(ie.inscripcion_materia_id, max_oport, session)

        session.add(ie)
        session.commit()
        session.refresh(ie)
        return ie

    # -- Marcar ausente -------------------------------------------------------

    def marcar_ausente(
        self,
        inscripcion_examen_id: int,
        session: Session,
    ) -> InscripcionExamen:
        """Marca al estudiante como ausente. La materia queda en A_EXAMEN."""
        ie = session.exec(
            select(InscripcionExamen).where(InscripcionExamen.id == inscripcion_examen_id)
        ).first()
        if not ie:
            raise ValueError(f"Inscripcion a examen {inscripcion_examen_id} no encontrada")
        if ie.estado != EstadoInscripcionExamen.INSCRIPTO:
            raise ValueError(
                f"Solo se puede marcar ausente una inscripcion en estado INSCRIPTO, actual: {ie.estado.value}"
            )

        ie.estado = EstadoInscripcionExamen.AUSENTE
        session.add(ie)
        session.commit()
        session.refresh(ie)
        return ie

    # -- Consultas ------------------------------------------------------------

    def get_examenes_estudiante(
        self,
        inscripcion_materia_id: int,
        session: Session,
    ) -> List[InscripcionExamen]:
        """Historial de examenes de una inscripcion a materia"""
        return list(session.exec(
            select(InscripcionExamen)
            .where(InscripcionExamen.inscripcion_materia_id == inscripcion_materia_id)
            .order_by(InscripcionExamen.fecha_inscripcion.desc())
        ).all())

    def get_examenes_instancia(
        self,
        instancia_examen_id: int,
        session: Session,
    ) -> List[dict]:
        """Lista de inscripciones a una instancia de examen."""
        resultados = session.exec(
            select(InscripcionExamen, InscripcionMateria)
            .join(InscripcionMateria, InscripcionExamen.inscripcion_materia_id == InscripcionMateria.id)
            .where(InscripcionExamen.instancia_examen_id == instancia_examen_id)
        ).all()

        from v2.models.usuario import Usuario
        items = []
        for ie, im in resultados:
            usuario = session.exec(
                select(Usuario).where(Usuario.id == im.usuario_id)
            ).first()
            ic = session.get(InstanciaCursado, im.instancia_cursado_id)
            materia = session.get(Materia, ic.materia_id) if ic else None
            items.append({
                "inscripcion_examen_id": ie.id,
                "inscripcion_materia_id": im.id,
                "usuario_id": im.usuario_id,
                "nombre": usuario.nombre if usuario else "",
                "apellido": usuario.apellido if usuario else "",
                "materia_nombre": materia.nombre if materia else "",
                "materia_id": materia.id if materia else None,
                "nota_examen": float(ie.nota_examen) if ie.nota_examen is not None else None,
                "estado": ie.estado.value,
                "fecha_inscripcion": ie.fecha_inscripcion.isoformat(),
            })
        return items

    def get_by_id(self, inscripcion_examen_id: int, session: Session) -> Optional[InscripcionExamen]:
        return session.exec(
            select(InscripcionExamen).where(InscripcionExamen.id == inscripcion_examen_id)
        ).first()

    # -- Desinscribir ---------------------------------------------------------

    def desinscribir_examen(
        self,
        inscripcion_examen_id: int,
        session: Session,
    ):
        """
        Desinscribirse de un examen (soft-delete).
        - Solo si esta en estado INSCRIPTO
        - Solo hasta 72 horas antes de la fecha del examen (configurable)
        """
        ie = session.exec(
            select(InscripcionExamen).where(InscripcionExamen.id == inscripcion_examen_id)
        ).first()
        if not ie:
            raise ValueError(f"Inscripcion a examen {inscripcion_examen_id} no encontrada")
        if ie.estado != EstadoInscripcionExamen.INSCRIPTO:
            raise ValueError("Solo se puede desinscribir una inscripcion en estado INSCRIPTO")

        # Validar plazo de baja (72 horas antes del examen)
        instancia = session.get(InstanciaExamen, ie.instancia_examen_id)
        if instancia and instancia.fecha_examen:
            plazo_horas = int(os.getenv("PLAZO_BAJA_EXAMEN_HORAS", "72"))
            tz = get_uruguay_tz()
            ahora = datetime.now(tz).replace(tzinfo=None)
            limite = instancia.fecha_examen - timedelta(hours=plazo_horas)
            if ahora > limite:
                raise ValueError(
                    f"No puedes darte de baja. El plazo es hasta {plazo_horas} horas antes del examen."
                )

        # Soft-delete: marcar como BAJA con fecha
        ie.estado = EstadoInscripcionExamen.BAJA
        ie.fecha_baja = datetime.now(get_uruguay_tz())
        session.add(ie)
        session.commit()

    # -- Helpers internos -----------------------------------------------------

    def _crear_snapshot_politica_examen(
        self, politica_examen_id: int, session: Session
    ) -> dict:
        """Crea snapshot de la politica de examen al momento de inscripcion"""
        politica = session.exec(
            select(PoliticaExamen).where(PoliticaExamen.id == politica_examen_id)
        ).first()
        if not politica:
            raise ValueError(f"Politica de examen {politica_examen_id} no encontrada")
        return {
            "politica_examen_id": politica.id,
            "nombre": politica.nombre,
            "nota_maxima": float(politica.nota_maxima),
            "umbral_aprobacion": float(politica.umbral_aprobacion),
            "max_oportunidades": politica.max_oportunidades,
        }

    def _aprobar_materia(
        self,
        inscripcion_materia_id: int,
        nota_examen: Decimal,
        session: Session,
    ):
        """Actualiza la inscripcion a materia a APROBADO tras aprobar examen"""
        inscripcion = session.exec(
            select(InscripcionMateria).where(InscripcionMateria.id == inscripcion_materia_id)
        ).first()
        if not inscripcion:
            return

        ic = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
        materia = session.get(Materia, ic.materia_id) if ic else None
        creditos = materia.creditos if materia else 0

        inscripcion.estado = EstadoInscripcionMateria.APROBADO
        inscripcion.nota_final = nota_examen
        inscripcion.creditos_obtenidos = creditos
        inscripcion.fecha_cierre = datetime.now(get_uruguay_tz())

        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)

    def _contar_rendiciones_previas(
        self, inscripcion_materia_id: int, session: Session
    ) -> int:
        """Cuenta rendiciones previas (APROBADO, REPROBADO o AUSENTE — no INSCRIPTO ni BAJA)"""
        from sqlalchemy import func
        estados_contables = [
            EstadoInscripcionExamen.APROBADO,
            EstadoInscripcionExamen.REPROBADO,
            EstadoInscripcionExamen.AUSENTE,
        ]
        count = session.exec(
            select(func.count(InscripcionExamen.id)).where(
                InscripcionExamen.inscripcion_materia_id == inscripcion_materia_id,
                InscripcionExamen.estado.in_(estados_contables),
            )
        ).one()
        return count

    def _reprobar_materia_por_rendiciones(
        self, inscripcion_materia_id: int, max_oportunidades: int, session: Session
    ):
        """Marca la inscripcion a materia como REPROBADO por agotar rendiciones"""
        inscripcion = session.get(InscripcionMateria, inscripcion_materia_id)
        if not inscripcion:
            return
        inscripcion.estado = EstadoInscripcionMateria.REPROBADO
        inscripcion.fecha_cierre = datetime.now(get_uruguay_tz())
        inscripcion.motivo_cierre = f"Agotadas las {max_oportunidades} oportunidades de examen. Debe recursar."
        session.add(inscripcion)

        # Notificación (best-effort)
        try:
            from v2.services import get_v2_services
            from v2.models.usuario import Usuario
            from v2.models.materia import Materia
            usuario = session.get(Usuario, inscripcion.usuario_id)
            ic_obj = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
            materia = session.get(Materia, ic_obj.materia_id) if ic_obj else None
            rendiciones = self._contar_rendiciones_previas(inscripcion_materia_id, session)
            if usuario and materia:
                get_v2_services().notificationService.notificar_reprobado_rendiciones(
                    inscripcion, usuario, materia, rendiciones, max_oportunidades, session
                )
        except Exception:
            pass
