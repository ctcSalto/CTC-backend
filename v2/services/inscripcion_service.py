from typing import Optional, List, Tuple
from datetime import datetime
from decimal import Decimal
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.inscripcion_materia import InscripcionMateria, InscripcionMateriaResumen
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.materia import Materia
from v2.models.previatura import Previatura
from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
from v2.models.politica_calificacion import PoliticaCalificacion
from v2.models.usuario import Usuario
from v2.models.enums import EstadoInscripcionMateria, TipoPreviatura

import os
from zoneinfo import ZoneInfo


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class InscripcionMateriaService(BaseServiceWithFilters[InscripcionMateria]):
    def __init__(self):
        super().__init__(InscripcionMateria)

    def get_by_id(self, inscripcion_id: int, session: Session) -> Optional[InscripcionMateria]:
        return session.exec(
            select(InscripcionMateria).where(InscripcionMateria.id == inscripcion_id)
        ).first()

    def get_by_usuario_instancia(
        self, usuario_id: int, instancia_cursado_id: int, session: Session
    ) -> Optional[InscripcionMateria]:
        """Busca inscripción de un usuario en una instancia de cursado."""
        return session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.usuario_id == usuario_id,
                InscripcionMateria.instancia_cursado_id == instancia_cursado_id,
            )
        ).first()

    # ── Flujo principal de inscripción ────────────────────────────────────────

    def inscribir_materia(
        self,
        usuario_id: int,
        instancia_cursado_id: int,
        session: Session,
        skip_periodo: bool = False,
    ) -> InscripcionMateria:
        """
        Flujo completo de inscripción a materia via instancia de cursado:
        1. Obtener instancia de cursado y materia
        2. Verificar período activo
        3. Verificar duplicado
        4. Validar previaturas
        5. Crear snapshots
        6. Crear inscripción
        7. Sync Moodle (best-effort)

        skip_periodo: True para inscripción manual por admin
        """
        # 1. Obtener instancia de cursado y materia
        instancia_cursado = session.get(InstanciaCursado, instancia_cursado_id)
        if not instancia_cursado:
            raise ValueError(f"Instancia de cursado {instancia_cursado_id} no encontrada")

        materia = session.exec(
            select(Materia).where(Materia.id == instancia_cursado.materia_id)
        ).first()
        if not materia:
            raise ValueError(f"Materia {instancia_cursado.materia_id} no encontrada")
        if not materia.activo:
            raise ValueError("La materia no esta activa")

        # 2. Verificar período activo (salvo inscripción manual por admin)
        if not skip_periodo:
            from v2.services.periodo_inscripcion_service import PeriodoInscripcionService
            periodo_service = PeriodoInscripcionService()
            periodo = periodo_service.get_periodo_activo(
                materia.programa_id, instancia_cursado.anio_lectivo, session
            )
            if not periodo:
                raise ValueError(
                    "No hay un periodo de inscripcion activo para este programa y anio lectivo"
                )

        # 3. Verificar que no esté ya inscripto en esta instancia con estado activo
        existente = session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.usuario_id == usuario_id,
                InscripcionMateria.instancia_cursado_id == instancia_cursado_id,
                InscripcionMateria.estado == EstadoInscripcionMateria.CURSANDO,
            )
        ).first()
        if existente:
            raise ValueError("Ya estas inscripto en esta instancia de cursado")

        # 4. Validar previaturas
        cumple, faltantes = self.validar_previaturas(usuario_id, materia.id, session)
        if not cumple:
            raise ValueError(
                "No cumple las previaturas requeridas: " + "; ".join(faltantes)
            )

        # 5. Crear snapshots
        snapshot_politica = self._crear_snapshot_politica(materia, session)
        snapshot_instancias = self._crear_snapshot_instancias(instancia_cursado_id, session)

        # 6. Crear inscripción
        inscripcion = InscripcionMateria(
            usuario_id=usuario_id,
            instancia_cursado_id=instancia_cursado_id,
            estado=EstadoInscripcionMateria.CURSANDO,
            snapshot_politica=snapshot_politica,
            snapshot_instancias=snapshot_instancias,
        )
        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)

        # 7. Sync Moodle (best-effort)
        self._sync_moodle_enrol(usuario_id, materia, session)

        return inscripcion

    # ── Validación de previaturas ─────────────────────────────────────────────

    def validar_previaturas(
        self, usuario_id: int, materia_id: int, session: Session
    ) -> Tuple[bool, List[str]]:
        """
        Verifica que el estudiante cumpla todas las previaturas de la materia.
        Retorna (cumple, lista_mensajes_faltantes)
        """
        previaturas = session.exec(
            select(Previatura).where(Previatura.materia_id == materia_id)
        ).all()

        if not previaturas:
            return True, []

        faltantes = []
        for prev in previaturas:
            # Buscar la mejor inscripción del estudiante en la materia previa
            # Necesitamos buscar via instancia_cursado -> materia
            inscripcion_previa = session.exec(
                select(InscripcionMateria)
                .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
                .where(
                    InscripcionMateria.usuario_id == usuario_id,
                    InstanciaCursado.materia_id == prev.materia_previa_id,
                    InscripcionMateria.estado.in_([
                        EstadoInscripcionMateria.APROBADO,
                        EstadoInscripcionMateria.EXONERADO,
                    ]),
                )
            ).first()

            materia_previa = session.exec(
                select(Materia).where(Materia.id == prev.materia_previa_id)
            ).first()
            nombre_previa = materia_previa.nombre if materia_previa else f"Materia {prev.materia_previa_id}"

            if not inscripcion_previa:
                faltantes.append(f"Debe aprobar {nombre_previa}")
                continue

            # Si requiere EXONERADA, verificar que sea exactamente EXONERADO
            if prev.tipo_requerido == TipoPreviatura.EXONERADA:
                if inscripcion_previa.estado != EstadoInscripcionMateria.EXONERADO:
                    faltantes.append(f"Debe exonerar {nombre_previa} (no alcanza con aprobar por examen)")

        return len(faltantes) == 0, faltantes

    # ── Snapshots ─────────────────────────────────────────────────────────────

    def _crear_snapshot_politica(self, materia: Materia, session: Session) -> dict:
        """Crea un snapshot de la política de calificación vigente"""
        politica = session.exec(
            select(PoliticaCalificacion).where(PoliticaCalificacion.id == materia.politica_id)
        ).first()

        if not politica:
            return {}

        return {
            "politica_id": politica.id,
            "nombre": politica.nombre,
            "nota_maxima": float(politica.nota_maxima) if politica.nota_maxima else None,
            "tipo_nota": politica.tipo_nota.value if politica.tipo_nota else None,
            "umbral_aprobacion": float(politica.umbral_aprobacion) if politica.umbral_aprobacion else None,
            "umbral_examen": float(politica.umbral_examen) if politica.umbral_examen else None,
            "umbral_exoneracion": float(politica.umbral_exoneracion) if politica.umbral_exoneracion else None,
        }

    def _crear_snapshot_instancias(
        self, instancia_cursado_id: int, session: Session
    ) -> list:
        """Crea un snapshot de las instancias de evaluación vigentes para la instancia de cursado"""
        instancias = session.exec(
            select(MateriaInstanciaEvaluacion)
            .where(
                MateriaInstanciaEvaluacion.instancia_cursado_id == instancia_cursado_id,
                MateriaInstanciaEvaluacion.activo == True,
            )
            .order_by(MateriaInstanciaEvaluacion.orden)
        ).all()

        return [
            {
                "id": inst.id,
                "nombre": inst.nombre,
                "peso_maximo": float(inst.peso_maximo) if inst.peso_maximo else None,
                "orden": inst.orden,
                "es_grupal": inst.es_grupal,
            }
            for inst in instancias
        ]

    # ── Sync Moodle ──────────────────────────────────────────────────────────

    def _sync_moodle_enrol(self, usuario_id: int, materia: Materia, session: Session):
        """Sincroniza la inscripción con Moodle (best-effort, no falla si Moodle no responde)"""
        if not materia.moodle_course_id:
            return

        usuario = session.exec(
            select(Usuario).where(Usuario.id == usuario_id)
        ).first()
        if not usuario or not usuario.moodle_id:
            return

        try:
            from external_services.moodle_api.controllers.moodle_enrolment_controller import EnrolmentController
            from external_services.moodle_api.models.enrolment import MoodleEnrolmentCreate

            controller = EnrolmentController()
            result = controller.enrol_user(MoodleEnrolmentCreate(
                courseid=materia.moodle_course_id,
                userid=usuario.moodle_id,
                roleid=5,  # Student
            ))
            if result.success:
                print(f"[OK] Moodle: inscripto usuario {usuario.moodle_id} en curso {materia.moodle_course_id}")
            else:
                print(f"[WARN] Moodle: {result.message}")
        except Exception as e:
            print(f"[WARN] Moodle sync fallo (no critico): {e}")

    # ── Escolaridad ──────────────────────────────────────────────────────────

    def get_escolaridad(
        self, usuario_id: int, programa_id: int, session: Session
    ) -> dict:
        """Escolaridad completa del estudiante en un programa"""
        # Obtener todas las materias del programa
        materias = session.exec(
            select(Materia)
            .where(Materia.programa_id == programa_id)
            .order_by(Materia.semestre, Materia.nombre)
        ).all()

        materia_ids = [m.id for m in materias]
        materia_map = {m.id: m for m in materias}

        # Obtener inscripciones del usuario en estas materias (via instancia_cursado)
        inscripciones = session.exec(
            select(InscripcionMateria)
            .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .where(
                InscripcionMateria.usuario_id == usuario_id,
                InstanciaCursado.materia_id.in_(materia_ids),
            )
        ).all()

        # Mapear inscripciones a materia_id via instancia_cursado
        insc_por_materia = {}
        for insc in inscripciones:
            ic = session.get(InstanciaCursado, insc.instancia_cursado_id)
            if ic:
                mid = ic.materia_id
                if mid not in insc_por_materia:
                    insc_por_materia[mid] = []
                insc_por_materia[mid].append((insc, ic.anio_lectivo))

        # Agrupar por semestre
        semestres = {}
        total_creditos = 0
        total_creditos_posibles = 0

        for materia in materias:
            sem = materia.semestre
            if sem not in semestres:
                semestres[sem] = []

            total_creditos_posibles += materia.creditos

            insc_materia = insc_por_materia.get(materia.id, [])

            if insc_materia:
                # Tomar la más reciente
                insc, anio = sorted(insc_materia, key=lambda x: x[1], reverse=True)[0]
                total_creditos += insc.creditos_obtenidos
                semestres[sem].append(
                    InscripcionMateriaResumen(
                        id=insc.id,
                        materia_nombre=materia.nombre,
                        materia_codigo=materia.codigo,
                        semestre=materia.semestre,
                        anio_lectivo=anio,
                        estado=insc.estado,
                        nota_curso=insc.nota_curso,
                        nota_final=insc.nota_final,
                        creditos_obtenidos=insc.creditos_obtenidos,
                    ).model_dump()
                )
            else:
                # Materia sin inscripción
                semestres[sem].append({
                    "materia_nombre": materia.nombre,
                    "materia_codigo": materia.codigo,
                    "semestre": materia.semestre,
                    "estado": "sin_inscripcion",
                    "creditos_obtenidos": 0,
                })

        return {
            "usuario_id": usuario_id,
            "programa_id": programa_id,
            "semestres": semestres,
            "total_creditos": total_creditos,
            "total_creditos_posibles": total_creditos_posibles,
        }

    # ── Materias disponibles ─────────────────────────────────────────────────

    def get_materias_disponibles(
        self, usuario_id: int, programa_id: int, anio_lectivo: int, session: Session
    ) -> list:
        """Materias a las que el estudiante puede inscribirse (con instancias activas)"""
        materias = session.exec(
            select(Materia).where(
                Materia.programa_id == programa_id,
                Materia.activo == True,
            ).order_by(Materia.semestre, Materia.nombre)
        ).all()

        resultado = []
        for materia in materias:
            # Verificar si ya tiene inscripción aprobada/exonerada/cursando en alguna instancia
            inscripcion_activa = session.exec(
                select(InscripcionMateria)
                .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
                .where(
                    InscripcionMateria.usuario_id == usuario_id,
                    InstanciaCursado.materia_id == materia.id,
                    InscripcionMateria.estado.in_([
                        EstadoInscripcionMateria.CURSANDO,
                        EstadoInscripcionMateria.EXONERADO,
                        EstadoInscripcionMateria.APROBADO,
                    ]),
                )
            ).first()

            if inscripcion_activa:
                continue  # Ya la tiene aprobada o la está cursando

            # Verificar previaturas
            cumple, faltantes = self.validar_previaturas(usuario_id, materia.id, session)

            # Buscar instancia de cursado activa para este año
            instancia = session.exec(
                select(InstanciaCursado).where(
                    InstanciaCursado.materia_id == materia.id,
                    InstanciaCursado.anio_lectivo == anio_lectivo,
                )
            ).first()

            resultado.append({
                "materia_id": materia.id,
                "nombre": materia.nombre,
                "codigo": materia.codigo,
                "semestre": materia.semestre,
                "creditos": materia.creditos,
                "puede_inscribirse": cumple and instancia is not None,
                "previaturas_faltantes": faltantes,
                "instancia_cursado_id": instancia.id if instancia else None,
            })

        return resultado

    # ── Faltas ────────────────────────────────────────────────────────────────

    def registrar_falta(self, inscripcion_id: int, session: Session) -> InscripcionMateria:
        """Incrementa faltas. Si alcanza faltas_maximas, cambia estado a PERDIDO_INASISTENCIA."""
        inscripcion = self.get_by_id(inscripcion_id, session)
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")
        if inscripcion.estado != EstadoInscripcionMateria.CURSANDO:
            raise ValueError(
                f"Solo se pueden registrar faltas en estado CURSANDO (actual: {inscripcion.estado.value})"
            )

        inscripcion.faltas += 1

        # Verificar si supera el máximo permitido
        ic = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
        if ic and ic.faltas_maximas is not None and inscripcion.faltas >= ic.faltas_maximas:
            inscripcion.estado = EstadoInscripcionMateria.PERDIDO_INASISTENCIA
            inscripcion.creditos_obtenidos = 0
            inscripcion.fecha_cierre = datetime.now(get_uruguay_tz())
            inscripcion.motivo_cierre = f"Perdido por inasistencia ({inscripcion.faltas}/{ic.faltas_maximas} faltas)"

        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)
        return inscripcion

    def quitar_falta(self, inscripcion_id: int, session: Session) -> InscripcionMateria:
        """Decrementa faltas (mínimo 0)."""
        inscripcion = self.get_by_id(inscripcion_id, session)
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")
        if inscripcion.estado != EstadoInscripcionMateria.CURSANDO:
            raise ValueError(
                f"Solo se pueden quitar faltas en estado CURSANDO (actual: {inscripcion.estado.value})"
            )

        inscripcion.faltas = max(0, inscripcion.faltas - 1)
        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)
        return inscripcion

    # ── Marcar inasistencia / abandono ────────────────────────────────────────

    def marcar_inasistencia(
        self, inscripcion_id: int, motivo: Optional[str], session: Session
    ) -> InscripcionMateria:
        inscripcion = self.get_by_id(inscripcion_id, session)
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")
        if inscripcion.estado != EstadoInscripcionMateria.CURSANDO:
            raise ValueError(
                f"Solo se puede marcar inasistencia en estado CURSANDO (actual: {inscripcion.estado.value})"
            )

        inscripcion.estado = EstadoInscripcionMateria.PERDIDO_INASISTENCIA
        inscripcion.creditos_obtenidos = 0
        inscripcion.fecha_cierre = datetime.now(get_uruguay_tz())
        inscripcion.motivo_cierre = motivo or "Perdido por inasistencia"

        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)
        return inscripcion

    def marcar_abandono(
        self, inscripcion_id: int, motivo: Optional[str], session: Session
    ) -> InscripcionMateria:
        inscripcion = self.get_by_id(inscripcion_id, session)
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")
        if inscripcion.estado != EstadoInscripcionMateria.CURSANDO:
            raise ValueError(
                f"Solo se puede marcar abandono en estado CURSANDO (actual: {inscripcion.estado.value})"
            )

        inscripcion.estado = EstadoInscripcionMateria.ABANDONO
        inscripcion.creditos_obtenidos = 0
        inscripcion.fecha_cierre = datetime.now(get_uruguay_tz())
        inscripcion.motivo_cierre = motivo or "Abandono"

        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)
        return inscripcion

    # ── Mis materias (alumno) ─────────────────────────────────────────────────

    def get_mis_materias(
        self, usuario_id: int, anio_lectivo: int, session: Session
    ) -> list:
        """Materias donde el alumno tiene inscripción activa en un año lectivo."""
        inscripciones = session.exec(
            select(InscripcionMateria, InstanciaCursado)
            .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .where(
                InscripcionMateria.usuario_id == usuario_id,
                InstanciaCursado.anio_lectivo == anio_lectivo,
            )
            .order_by(InscripcionMateria.fecha_inscripcion.desc())
        ).all()

        resultado = []
        for insc, ic in inscripciones:
            materia = session.get(Materia, ic.materia_id)
            resultado.append({
                "inscripcion_id": insc.id,
                "instancia_cursado_id": ic.id,
                "materia_id": ic.materia_id,
                "materia_nombre": materia.nombre if materia else "",
                "materia_codigo": materia.codigo if materia else "",
                "semestre": materia.semestre if materia else None,
                "estado": insc.estado.value,
                "nota_curso": float(insc.nota_curso) if insc.nota_curso else None,
                "nota_final": float(insc.nota_final) if insc.nota_final else None,
                "faltas": insc.faltas,
                "faltas_maximas": ic.faltas_maximas,
            })
        return resultado

    # ── Detalle materia (alumno) ──────────────────────────────────────────────

    def get_detalle_materia(
        self, inscripcion_id: int, usuario_id: int, session: Session
    ) -> dict:
        """Vista completa de una inscripción para el alumno."""
        inscripcion = self.get_by_id(inscripcion_id, session)
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")
        if inscripcion.usuario_id != usuario_id:
            raise ValueError("No es tu inscripcion")

        ic = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
        materia = session.get(Materia, ic.materia_id) if ic else None

        # Obtener calificaciones
        from v2.models.calificacion import Calificacion
        calificaciones = session.exec(
            select(Calificacion).where(Calificacion.inscripcion_id == inscripcion_id)
        ).all()

        calificaciones_detalle = []
        for cal in calificaciones:
            eval_inst = session.get(MateriaInstanciaEvaluacion, cal.instancia_evaluacion_id)
            calificaciones_detalle.append({
                "calificacion_id": cal.id,
                "instancia_evaluacion_id": cal.instancia_evaluacion_id,
                "instancia_evaluacion_nombre": eval_inst.nombre if eval_inst else "",
                "nota": float(cal.nota) if cal.nota is not None else None,
                "fecha": cal.fecha.isoformat() if cal.fecha else None,
                "observaciones": cal.observaciones,
            })

        return {
            "inscripcion_id": inscripcion.id,
            "estado": inscripcion.estado.value,
            "materia_id": materia.id if materia else None,
            "materia_nombre": materia.nombre if materia else "",
            "materia_codigo": materia.codigo if materia else "",
            "semestre": materia.semestre if materia else None,
            "creditos": materia.creditos if materia else 0,
            "nota_curso": float(inscripcion.nota_curso) if inscripcion.nota_curso else None,
            "nota_final": float(inscripcion.nota_final) if inscripcion.nota_final else None,
            "nota_final_directa": float(inscripcion.nota_final_directa) if inscripcion.nota_final_directa else None,
            "faltas": inscripcion.faltas,
            "faltas_maximas": ic.faltas_maximas if ic else None,
            "creditos_obtenidos": inscripcion.creditos_obtenidos,
            "fecha_inscripcion": inscripcion.fecha_inscripcion.isoformat(),
            "fecha_cierre": inscripcion.fecha_cierre.isoformat() if inscripcion.fecha_cierre else None,
            "calificaciones": calificaciones_detalle,
            "snapshot_politica": inscripcion.snapshot_politica,
        }

    # ── Desinscripción de materia ─────────────────────────────────────────────

    def desinscribir_materia(
        self, inscripcion_id: int, usuario_id: int, session: Session
    ) -> None:
        """Permite al alumno desinscribirse de una materia (solo si está CURSANDO)."""
        inscripcion = self.get_by_id(inscripcion_id, session)
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")
        if inscripcion.usuario_id != usuario_id:
            raise ValueError("No es tu inscripcion")
        if inscripcion.estado != EstadoInscripcionMateria.CURSANDO:
            raise ValueError(
                f"Solo se puede desinscribir en estado CURSANDO (actual: {inscripcion.estado.value})"
            )

        # Verificar período activo
        ic = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
        if ic:
            materia = session.get(Materia, ic.materia_id)
            if materia:
                from v2.services.periodo_inscripcion_service import PeriodoInscripcionService
                periodo_service = PeriodoInscripcionService()
                periodo = periodo_service.get_periodo_activo(
                    materia.programa_id, ic.anio_lectivo, session
                )
                if not periodo:
                    raise ValueError("No hay un periodo de inscripcion activo para desinscribirse")

        session.delete(inscripcion)
        session.commit()

    # ── Mapa de previaturas (alumno) ──────────────────────────────────────────

    def get_mapa_previaturas(
        self, usuario_id: int, programa_id: int, session: Session
    ) -> list:
        """Grafo de previaturas con el estado del alumno en cada materia."""
        materias = session.exec(
            select(Materia).where(
                Materia.programa_id == programa_id,
                Materia.activo == True,
            ).order_by(Materia.semestre, Materia.nombre)
        ).all()

        # Obtener todas las previaturas del programa
        materia_ids = [m.id for m in materias]
        previaturas = session.exec(
            select(Previatura).where(Previatura.materia_id.in_(materia_ids))
        ).all()

        # Mapear previaturas por materia
        previaturas_por_materia = {}
        for prev in previaturas:
            if prev.materia_id not in previaturas_por_materia:
                previaturas_por_materia[prev.materia_id] = []
            # Buscar nombre de materia previa
            materia_previa = session.get(Materia, prev.materia_previa_id)
            previaturas_por_materia[prev.materia_id].append({
                "materia_previa_id": prev.materia_previa_id,
                "nombre": materia_previa.nombre if materia_previa else "",
                "codigo": materia_previa.codigo if materia_previa else "",
                "tipo_requerido": prev.tipo_requerido.value,
            })

        # Estado del alumno en cada materia
        inscripciones = session.exec(
            select(InscripcionMateria, InstanciaCursado)
            .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .where(
                InscripcionMateria.usuario_id == usuario_id,
                InstanciaCursado.materia_id.in_(materia_ids),
            )
        ).all()

        # Mejor estado por materia (prioridad: APROBADO > EXONERADO > CURSANDO > A_EXAMEN > otros)
        estado_por_materia = {}
        prioridad = {
            EstadoInscripcionMateria.APROBADO: 6,
            EstadoInscripcionMateria.EXONERADO: 5,
            EstadoInscripcionMateria.CURSANDO: 4,
            EstadoInscripcionMateria.A_EXAMEN: 3,
            EstadoInscripcionMateria.REPROBADO: 2,
            EstadoInscripcionMateria.PERDIDO_INASISTENCIA: 1,
            EstadoInscripcionMateria.ABANDONO: 0,
        }
        for insc, ic in inscripciones:
            mid = ic.materia_id
            if mid not in estado_por_materia or prioridad.get(insc.estado, -1) > prioridad.get(estado_por_materia[mid], -1):
                estado_por_materia[mid] = insc.estado

        resultado = []
        for materia in materias:
            estado = estado_por_materia.get(materia.id)
            resultado.append({
                "materia_id": materia.id,
                "nombre": materia.nombre,
                "codigo": materia.codigo,
                "semestre": materia.semestre,
                "creditos": materia.creditos,
                "previaturas": previaturas_por_materia.get(materia.id, []),
                "estado_alumno": estado.value if estado else "pendiente",
            })

        return resultado
