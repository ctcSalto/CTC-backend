from typing import Optional, List
from decimal import Decimal
from sqlmodel import Session, select, col

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_examen import InstanciaExamen
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.materia import Materia
from v2.models.politica_examen import PoliticaExamen
from v2.models.usuario import Usuario
from v2.models.alumno import Alumno
from v2.models.enums import EstadoInscripcionMateria, EstadoInscripcionExamen

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


def _usuario_de_alumno(alumno_id: int, session: Session) -> Optional[Usuario]:
    """
    Resuelve el Usuario (la persona) detras de un perfil de alumno.
    Necesario para nombres y notificaciones: esos datos viven en Usuario,
    no en el perfil academico.
    """
    alumno = session.get(Alumno, alumno_id)
    return session.get(Usuario, alumno.usuario_id) if alumno else None


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
        # El id_rastreo de la notificación se adjunta a la respuesta para que
        # quien inscribió pueda verificar después si el email se entregó
        # (ver GET /v2/admin/notificaciones/rastreo/{id_rastreo}).
        object.__setattr__(inscripcion_examen, "id_rastreo_notificacion", None)
        try:
            from v2.services import get_v2_services
            usuario = _usuario_de_alumno(inscripcion.alumno_id, session)
            instancia = session.get(InstanciaExamen, instancia_examen_id)
            ic_obj = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
            mat_notif = session.get(Materia, ic_obj.materia_id) if ic_obj else None
            if usuario and instancia and mat_notif:
                resultado = get_v2_services().notificationService.notificar_inscripcion_examen(
                    inscripcion_examen, usuario, mat_notif, instancia, session
                )
                object.__setattr__(inscripcion_examen, "id_rastreo_notificacion", resultado.get("id_rastreo"))
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

        items = []
        for ie, im in resultados:
            usuario = _usuario_de_alumno(im.alumno_id, session)
            ic = session.get(InstanciaCursado, im.instancia_cursado_id)
            materia = session.get(Materia, ic.materia_id) if ic else None
            items.append({
                "inscripcion_examen_id": ie.id,
                "inscripcion_materia_id": im.id,
                "alumno_id": im.alumno_id,
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

        ahora = datetime.now(get_uruguay_tz())

        inscripcion.estado = EstadoInscripcionMateria.APROBADO
        inscripcion.nota_final = nota_examen
        inscripcion.creditos_obtenidos = creditos
        inscripcion.fecha_cierre = ahora
        session.add(inscripcion)

        # Con la materia aprobada, cualquier otra inscripcion a examen pendiente
        # dejo de tener sentido: el alumno ya no tiene que rendir nada. Si se
        # dejaran en INSCRIPTO quedarian apuntando a una materia cerrada, saldrian
        # en las listas del docente y contarian como rendicion al calificarlas.
        pendientes = session.exec(
            select(InscripcionExamen).where(
                InscripcionExamen.inscripcion_materia_id == inscripcion_materia_id,
                InscripcionExamen.estado == EstadoInscripcionExamen.INSCRIPTO,
            )
        ).all()
        for pendiente in pendientes:
            pendiente.estado = EstadoInscripcionExamen.BAJA
            pendiente.fecha_baja = ahora
            session.add(pendiente)

        session.commit()
        session.refresh(inscripcion)

    # -- Precarga en lote ------------------------------------------------------

    @staticmethod
    def _politicas_por_id(politica_ids, session: Session) -> dict:
        ids = {pid for pid in politica_ids if pid is not None}
        if not ids:
            return {}
        return {
            p.id: p for p in session.exec(
                select(PoliticaExamen).where(col(PoliticaExamen.id).in_(ids))
            ).all()
        }

    @staticmethod
    def _contar_rendiciones_en_lote(inscripcion_ids: List[int], session: Session) -> dict:
        """Rendiciones consumidas por inscripcion. Mismo criterio que el conteo individual."""
        if not inscripcion_ids:
            return {}
        from sqlalchemy import func

        filas = session.exec(
            select(
                InscripcionExamen.inscripcion_materia_id,
                func.count(InscripcionExamen.id),
            )
            .where(
                col(InscripcionExamen.inscripcion_materia_id).in_(inscripcion_ids),
                col(InscripcionExamen.estado).in_([
                    EstadoInscripcionExamen.APROBADO,
                    EstadoInscripcionExamen.REPROBADO,
                    EstadoInscripcionExamen.AUSENTE,
                ]),
            )
            .group_by(InscripcionExamen.inscripcion_materia_id)
        ).all()
        return {insc_id: total for insc_id, total in filas}

    @staticmethod
    def _instancias_abiertas(materia_ids: List[int], ahora, session: Session) -> dict:
        """Instancias de examen con la inscripcion abierta, agrupadas por materia."""
        if not materia_ids:
            return {}

        instancias = session.exec(
            select(InstanciaExamen)
            .where(
                col(InstanciaExamen.materia_id).in_(materia_ids),
                InstanciaExamen.habilitado == True,
                InstanciaExamen.fecha_inicio_inscripcion <= ahora,
                InstanciaExamen.fecha_fin_inscripcion >= ahora,
            )
            .order_by(InstanciaExamen.fecha_examen)
        ).all()

        por_materia: dict[int, list] = {}
        for inst in instancias:
            por_materia.setdefault(inst.materia_id, []).append(inst)
        return por_materia

    @staticmethod
    def _inscripciones_vigentes(inscripcion_ids: List[int], session: Session) -> set:
        """Pares (inscripcion_materia_id, instancia_examen_id) ya inscriptos."""
        if not inscripcion_ids:
            return set()

        filas = session.exec(
            select(
                InscripcionExamen.inscripcion_materia_id,
                InscripcionExamen.instancia_examen_id,
            ).where(
                col(InscripcionExamen.inscripcion_materia_id).in_(inscripcion_ids),
                InscripcionExamen.estado == EstadoInscripcionExamen.INSCRIPTO,
            )
        ).all()
        return {(insc_id, inst_id) for insc_id, inst_id in filas}

    # -- Examenes habilitados --------------------------------------------------

    def get_examenes_habilitados(
        self, alumno_id: int, programa_id: int, session: Session
    ) -> list:
        """
        Instancias de examen a las que el alumno puede inscribirse en un programa.

        Aplica las mismas validaciones que inscribir_examen, para que
        puede_inscribirse no contradiga al POST:
          - la materia debe estar en estado A_EXAMEN
          - la instancia habilitada y dentro del plazo de inscripcion
          - no tener ya una inscripcion INSCRIPTO en esa instancia
          - la materia debe tener politica de examen configurada
          - no haber agotado las oportunidades de rendicion

        Las previaturas no se validan aca a proposito: para llegar a A_EXAMEN el
        alumno tuvo que cursar la materia, y esa inscripcion ya las valido.
        """
        ahora = datetime.now(get_uruguay_tz()).replace(tzinfo=None)

        # Materias del programa que el alumno tiene en estado A_EXAMEN
        filas = session.exec(
            select(InscripcionMateria, Materia)
            .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .join(Materia, InstanciaCursado.materia_id == Materia.id)
            .where(
                InscripcionMateria.alumno_id == alumno_id,
                InscripcionMateria.estado == EstadoInscripcionMateria.A_EXAMEN,
                Materia.programa_id == programa_id,
            )
        ).all()

        if not filas:
            return []

        # Precarga en lote: antes cada materia disparaba su politica, su conteo
        # de rendiciones y sus instancias, y cada instancia una consulta mas para
        # saber si ya estaba inscripto.
        inscripcion_ids = [insc.id for insc, _ in filas]
        materia_ids = [materia.id for _, materia in filas]

        politicas = self._politicas_por_id(
            [m.politica_examen_id for _, m in filas], session
        )
        rendiciones_por_inscripcion = self._contar_rendiciones_en_lote(
            inscripcion_ids, session
        )
        instancias_por_materia = self._instancias_abiertas(materia_ids, ahora, session)
        ya_inscripto_en = self._inscripciones_vigentes(inscripcion_ids, session)

        resultado = []
        for insc, materia in filas:
            # Politica de examen: sin ella inscribir_examen falla
            politica = politicas.get(materia.politica_examen_id)
            max_oportunidades = politica.max_oportunidades if politica else 5
            rendiciones = rendiciones_por_inscripcion.get(insc.id, 0)

            for inst in instancias_por_materia.get(materia.id, []):
                ya_inscripto = (insc.id, inst.id) in ya_inscripto_en

                motivos = []
                if materia.politica_examen_id is None:
                    motivos.append("La materia no tiene politica de examen configurada")
                if rendiciones >= max_oportunidades:
                    motivos.append(
                        f"Agotaste las {max_oportunidades} oportunidades de rendicion. "
                        "Debes recursar la materia."
                    )
                if ya_inscripto:
                    motivos.append("Ya estas inscripto a este examen")

                resultado.append({
                    "instancia_examen_id": inst.id,
                    "inscripcion_materia_id": insc.id,
                    "materia_id": materia.id,
                    "materia_nombre": materia.nombre,
                    "materia_codigo": materia.codigo,
                    "nombre_examen": inst.nombre,
                    "fecha_examen": inst.fecha_examen.isoformat() if inst.fecha_examen else None,
                    "fecha_fin_inscripcion": inst.fecha_fin_inscripcion.isoformat(),
                    "hora": inst.hora,
                    "salon": inst.salon,
                    "modalidad": inst.modalidad.value if inst.modalidad else None,
                    "tipo": inst.tipo.value if inst.tipo else None,
                    "ya_inscripto": ya_inscripto,
                    "rendiciones_previas": rendiciones,
                    "max_oportunidades": max_oportunidades,
                    "puede_inscribirse": len(motivos) == 0,
                    "motivos": motivos,
                })

        return resultado

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
            usuario = _usuario_de_alumno(inscripcion.alumno_id, session)
            ic_obj = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
            mat_notif = session.get(Materia, ic_obj.materia_id) if ic_obj else None
            rendiciones = self._contar_rendiciones_previas(inscripcion_materia_id, session)
            if usuario and mat_notif:
                get_v2_services().notificationService.notificar_reprobado_rendiciones(
                    inscripcion, usuario, mat_notif, rendiciones, max_oportunidades, session
                )
        except Exception:
            pass
