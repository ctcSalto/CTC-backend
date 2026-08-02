from typing import Optional, List, Tuple
from datetime import datetime
from decimal import Decimal
from sqlmodel import Session, select, col
from sqlalchemy import func, or_

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.inscripcion_materia import (
    InscripcionMateria,
    EscolaridadMateriaItem,
    EscolaridadSemestre,
    EscolaridadRead,
    SIN_INSCRIPCION,
)
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.materia import Materia
from v2.models.previatura import Previatura
from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
from v2.models.politica_calificacion import PoliticaCalificacion
from v2.models.usuario import Usuario
from v2.models.alumno import Alumno
from v2.models.enums import (
    EstadoInscripcionMateria,
    EstadoInstanciaCursado,
    TipoPreviatura,
)

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

    def get_by_alumno_instancia(
        self, alumno_id: int, instancia_cursado_id: int, session: Session
    ) -> Optional[InscripcionMateria]:
        """Busca inscripción de un alumno en una instancia de cursado."""
        return session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.alumno_id == alumno_id,
                InscripcionMateria.instancia_cursado_id == instancia_cursado_id,
            )
        ).first()

    # ── Flujo principal de inscripción ────────────────────────────────────────

    def inscribir_materia(
        self,
        alumno_id: int,
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
                InscripcionMateria.alumno_id == alumno_id,
                InscripcionMateria.instancia_cursado_id == instancia_cursado_id,
                InscripcionMateria.estado == EstadoInscripcionMateria.CURSANDO,
            )
        ).first()
        if existente:
            raise ValueError("Ya estas inscripto en esta instancia de cursado")

        # 4. Validar previaturas
        cumple, faltantes = self.validar_previaturas(alumno_id, materia.id, session)
        if not cumple:
            raise ValueError(
                "No cumple las previaturas requeridas: " + "; ".join(faltantes)
            )

        # 5. Crear snapshots
        snapshot_politica = self._crear_snapshot_politica(materia, session)
        snapshot_instancias = self._crear_snapshot_instancias(instancia_cursado_id, session)

        # 6. Crear inscripción
        inscripcion = InscripcionMateria(
            alumno_id=alumno_id,
            instancia_cursado_id=instancia_cursado_id,
            estado=EstadoInscripcionMateria.CURSANDO,
            snapshot_politica=snapshot_politica,
            snapshot_instancias=snapshot_instancias,
        )
        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)

        # 7. Sync Moodle (best-effort)
        self._sync_moodle_enrol(alumno_id, materia, session)

        # 8. Notificación (best-effort, no crítica)
        # El id_rastreo de la notificación se adjunta a la respuesta para que
        # quien inscribió pueda verificar después si el email se entregó
        # (ver GET /v2/admin/notificaciones/rastreo/{id_rastreo}).
        object.__setattr__(inscripcion, "id_rastreo_notificacion", None)
        try:
            from v2.services import get_v2_services
            from v2.models.programa import Programa
            # La notificación necesita el Usuario (email/contacto), que cuelga del
            # perfil de alumno. Un oyente sin cuenta simplemente no recibe nada.
            usuario = self._usuario_de_alumno(alumno_id, session)
            programa = session.get(Programa, materia.programa_id)
            if usuario and programa:
                resultado = get_v2_services().notificationService.notificar_inscripcion_materia(
                    inscripcion, usuario, materia,
                    programa.nombre, instancia_cursado.anio_lectivo, session
                )
                object.__setattr__(inscripcion, "id_rastreo_notificacion", resultado.get("id_rastreo"))
        except Exception:
            pass  # notificación nunca bloquea la inscripción

        return inscripcion

    # ── Validación de previaturas ─────────────────────────────────────────────

    # Estados de la materia previa que satisfacen cada tipo de previatura.
    #
    # REVALIDADA cuenta como materia cumplida, igual que APROBADO y EXONERADO:
    # una materia convalidada de otra institucion otorga creditos y cuenta para
    # el egreso, asi que tambien tiene que habilitar la siguiente. Y satisface
    # una previatura de tipo EXONERADA porque el alumno no puede volver a cursar
    # lo que ya revalido: exigirle la exoneracion lo dejaria sin salida. El
    # control academico de la revalida ya lo hizo administracion al otorgarla.
    CUMPLE_APROBADA = (
        EstadoInscripcionMateria.APROBADO,
        EstadoInscripcionMateria.EXONERADO,
        EstadoInscripcionMateria.REVALIDADA,
    )
    CUMPLE_EXONERADA = (
        EstadoInscripcionMateria.EXONERADO,
        EstadoInscripcionMateria.REVALIDADA,
    )

    @classmethod
    def _evaluar_previaturas(
        cls,
        previaturas: List[Previatura],
        estados_por_materia: dict,
        nombres_por_materia: dict,
    ) -> Tuple[bool, List[str]]:
        """
        Regla de previaturas, sin tocar la base.

        Se separo de la consulta para poder evaluarla en lote: las pantallas de
        disponibilidad la necesitan para todas las materias del plan a la vez, y
        resolviendola materia por materia cada una disparaba dos consultas por
        previatura.

        estados_por_materia: materia_id -> set de estados del alumno en esa materia
        nombres_por_materia: materia_id -> nombre, para los mensajes
        """
        faltantes = []
        for prev in previaturas:
            # Se miran TODOS los estados del alumno en la materia previa, no uno:
            # si recurso puede tener varias filas y basta con que alguna alcance
            # el tipo requerido.
            estados = estados_por_materia.get(prev.materia_previa_id, set())
            cumplen = estados & set(cls.CUMPLE_APROBADA)

            nombre = nombres_por_materia.get(
                prev.materia_previa_id, f"Materia {prev.materia_previa_id}"
            )

            if not cumplen:
                faltantes.append(f"Debe aprobar {nombre}")
                continue

            if prev.tipo_requerido == TipoPreviatura.EXONERADA:
                if not cumplen & set(cls.CUMPLE_EXONERADA):
                    faltantes.append(f"Debe exonerar {nombre} (no alcanza con aprobar por examen)")

        return len(faltantes) == 0, faltantes

    def _estados_del_alumno(
        self, alumno_id: int, materia_ids: List[int], session: Session
    ) -> dict:
        """Estados del alumno en cada materia, en una sola consulta."""
        if not materia_ids:
            return {}

        filas = session.exec(
            select(InstanciaCursado.materia_id, InscripcionMateria.estado)
            .join(InscripcionMateria, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .where(
                InscripcionMateria.alumno_id == alumno_id,
                col(InstanciaCursado.materia_id).in_(materia_ids),
            )
        ).all()

        estados: dict[int, set] = {}
        for materia_id, estado in filas:
            estados.setdefault(materia_id, set()).add(estado)
        return estados

    def validar_previaturas(
        self, alumno_id: int, materia_id: int, session: Session
    ) -> Tuple[bool, List[str]]:
        """
        Verifica que el estudiante cumpla todas las previaturas de la materia.
        Retorna (cumple, lista_mensajes_faltantes)
        """
        previaturas = list(session.exec(
            select(Previatura).where(Previatura.materia_id == materia_id)
        ).all())

        if not previaturas:
            return True, []

        previas_ids = [p.materia_previa_id for p in previaturas]
        estados = self._estados_del_alumno(alumno_id, previas_ids, session)
        nombres = {
            m.id: m.nombre for m in session.exec(
                select(Materia).where(col(Materia.id).in_(previas_ids))
            ).all()
        }

        return self._evaluar_previaturas(previaturas, estados, nombres)

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

    def _usuario_de_alumno(self, alumno_id: int, session: Session) -> Optional[Usuario]:
        """
        Resuelve el Usuario (la persona) detrás de un perfil de alumno.
        Necesario para todo lo que sale del dominio académico: Moodle, emails.
        """
        alumno = session.get(Alumno, alumno_id)
        return session.get(Usuario, alumno.usuario_id) if alumno else None

    def _sync_moodle_enrol(self, alumno_id: int, materia: Materia, session: Session):
        """Sincroniza la inscripción con Moodle (best-effort, no falla si Moodle no responde)"""
        if not materia.moodle_course_id:
            return

        usuario = self._usuario_de_alumno(alumno_id, session)
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
        self, alumno_id: int, programa_id: int, session: Session
    ) -> dict:
        """Escolaridad completa del estudiante en un programa"""
        # Obtener todas las materias del programa
        materias = session.exec(
            select(Materia)
            .where(Materia.programa_id == programa_id)
            .order_by(Materia.semestre, Materia.nombre)
        ).all()

        materia_ids = [m.id for m in materias]

        # Inscripciones del alumno en estas materias. Traemos materia_id y
        # anio_lectivo de la instancia en la misma consulta para no hacer un
        # get(InstanciaCursado) por inscripcion.
        filas = session.exec(
            select(
                InscripcionMateria,
                InstanciaCursado.materia_id,
                InstanciaCursado.anio_lectivo,
            )
            .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .where(
                InscripcionMateria.alumno_id == alumno_id,
                InstanciaCursado.materia_id.in_(materia_ids),
            )
        ).all()

        # De cada materia queda la inscripcion del anio lectivo mas reciente
        insc_por_materia: dict[int, tuple[InscripcionMateria, int]] = {}
        for insc, materia_id, anio_lectivo in filas:
            elegida = insc_por_materia.get(materia_id)
            if elegida is None or anio_lectivo > elegida[1]:
                insc_por_materia[materia_id] = (insc, anio_lectivo)

        # Agrupar por semestre
        por_semestre: dict[int, list[EscolaridadMateriaItem]] = {}
        total_creditos = 0
        total_creditos_posibles = 0

        for materia in materias:
            total_creditos_posibles += materia.creditos

            elegida = insc_por_materia.get(materia.id)
            if elegida:
                insc, anio_lectivo = elegida
                total_creditos += insc.creditos_obtenidos
                item = EscolaridadMateriaItem(
                    inscripcion_id=insc.id,
                    materia_nombre=materia.nombre,
                    materia_codigo=materia.codigo,
                    semestre=materia.semestre,
                    anio_lectivo=anio_lectivo,
                    estado=insc.estado.value,
                    nota_curso=insc.nota_curso,
                    nota_final=insc.nota_final,
                    creditos_obtenidos=insc.creditos_obtenidos,
                    faltas=insc.faltas,
                )
            else:
                # Materia del plan sin inscripcion: mismos campos, en None
                item = EscolaridadMateriaItem(
                    materia_nombre=materia.nombre,
                    materia_codigo=materia.codigo,
                    semestre=materia.semestre,
                    estado=SIN_INSCRIPCION,
                )

            por_semestre.setdefault(materia.semestre, []).append(item)

        return EscolaridadRead(
            alumno_id=alumno_id,
            programa_id=programa_id,
            semestres=[
                EscolaridadSemestre(semestre=sem, materias=por_semestre[sem])
                for sem in sorted(por_semestre)
            ],
            total_creditos=total_creditos,
            total_creditos_posibles=total_creditos_posibles,
        ).model_dump()

    # ── Materias disponibles ─────────────────────────────────────────────────

    def get_materias_disponibles(
        self, alumno_id: int, programa_id: int, anio_lectivo: int, session: Session
    ) -> list:
        """Materias a las que el estudiante puede inscribirse (con instancias activas)"""
        materias = session.exec(
            select(Materia).where(
                Materia.programa_id == programa_id,
                Materia.activo == True,
            ).order_by(Materia.semestre, Materia.nombre)
        ).all()

        # Precarga en lote, igual que get_materias_habilitadas: consultar por
        # materia hacia ~150 consultas con un plan de 30.
        materia_ids = [m.id for m in materias]
        estados_alumno = self._estados_del_alumno(alumno_id, materia_ids, session)
        previaturas_por_materia, nombres_previas = self._previaturas_de(
            materia_ids, session
        )
        nombres = {m.id: m.nombre for m in materias}
        nombres.update(nombres_previas)

        # Esta consulta no filtra por estado ni semestre, a diferencia de
        # get_materias_habilitadas: se conserva el comportamiento original.
        instancias_por_materia: dict[int, InstanciaCursado] = {}
        if materia_ids:
            for instancia in session.exec(
                select(InstanciaCursado).where(
                    col(InstanciaCursado.materia_id).in_(materia_ids),
                    InstanciaCursado.anio_lectivo == anio_lectivo,
                )
            ).all():
                instancias_por_materia.setdefault(instancia.materia_id, instancia)

        bloquean = (
            EstadoInscripcionMateria.CURSANDO,
            EstadoInscripcionMateria.EXONERADO,
            EstadoInscripcionMateria.APROBADO,
        )

        resultado = []
        for materia in materias:
            # Ya la tiene aprobada o la esta cursando
            if estados_alumno.get(materia.id, set()) & set(bloquean):
                continue

            cumple, faltantes = self._evaluar_previaturas(
                previaturas_por_materia.get(materia.id, []), estados_alumno, nombres
            )
            instancia = instancias_por_materia.get(materia.id)

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

    # ── Precarga en lote ──────────────────────────────────────────────────────
    # Estos helpers existen para que las pantallas de disponibilidad no consulten
    # por materia. Cada uno resuelve en UNA consulta lo que antes se pedia N veces.

    def _previaturas_de(
        self, materia_ids: List[int], session: Session
    ) -> Tuple[dict, dict]:
        """
        Previaturas de varias materias y los nombres de sus materias previas.

        Devuelve (previaturas_por_materia, nombres_por_materia_previa). Los
        nombres se resuelven aparte porque una materia previa puede no estar en
        la lista consultada.
        """
        if not materia_ids:
            return {}, {}

        previaturas = list(session.exec(
            select(Previatura).where(col(Previatura.materia_id).in_(materia_ids))
        ).all())

        por_materia: dict[int, list] = {}
        for prev in previaturas:
            por_materia.setdefault(prev.materia_id, []).append(prev)

        previas_ids = {p.materia_previa_id for p in previaturas}
        nombres = {}
        if previas_ids:
            nombres = {
                m.id: m.nombre for m in session.exec(
                    select(Materia).where(col(Materia.id).in_(previas_ids))
                ).all()
            }

        return por_materia, nombres

    def _instancias_del_periodo(
        self, materia_ids: List[int], periodo, session: Session
    ) -> dict:
        """
        Instancia de cursado ofrecida en el periodo, por materia.

        Con varias candidatas gana la del semestre mas alto, igual criterio que
        la consulta por materia que reemplaza.
        """
        if not materia_ids:
            return {}

        stmt = select(InstanciaCursado).where(
            col(InstanciaCursado.materia_id).in_(materia_ids),
            InstanciaCursado.anio_lectivo == periodo.anio_lectivo,
            col(InstanciaCursado.estado).in_([
                EstadoInstanciaCursado.PLANIFICADA,
                EstadoInstanciaCursado.EN_CURSO,
            ]),
        )
        if periodo.semestre is not None:
            # Una instancia con semestre NULL se considera dictada en cualquier
            # semestre, para no ocultar oferta cargada antes de que el campo
            # existiera. Si el periodo no declara semestre, no se filtra: vale
            # para todo el anio lectivo.
            stmt = stmt.where(
                or_(
                    InstanciaCursado.semestre == periodo.semestre,
                    col(InstanciaCursado.semestre).is_(None),
                )
            )

        por_materia: dict[int, InstanciaCursado] = {}
        for instancia in session.exec(stmt).all():
            actual = por_materia.get(instancia.materia_id)
            if actual is None or (instancia.semestre or 0) > (actual.semestre or 0):
                por_materia[instancia.materia_id] = instancia
        return por_materia

    @staticmethod
    def _contar_cursando(instancia_ids: List[int], session: Session) -> dict:
        """Inscripciones vivas por instancia de cursado, para el control de cupo."""
        if not instancia_ids:
            return {}

        filas = session.exec(
            select(
                InscripcionMateria.instancia_cursado_id,
                func.count(InscripcionMateria.id),
            )
            .where(
                col(InscripcionMateria.instancia_cursado_id).in_(instancia_ids),
                InscripcionMateria.estado == EstadoInscripcionMateria.CURSANDO,
            )
            .group_by(InscripcionMateria.instancia_cursado_id)
        ).all()
        return {instancia_id: total for instancia_id, total in filas}

    # ── Materias habilitadas en el semestre activo ────────────────────────────

    # Estados que significan "ya la tiene, no la puede volver a cursar"
    _ESTADOS_BLOQUEAN_RECURSADA = (
        EstadoInscripcionMateria.CURSANDO,
        EstadoInscripcionMateria.EXONERADO,
        EstadoInscripcionMateria.APROBADO,
        EstadoInscripcionMateria.REVALIDADA,
    )

    def get_materias_habilitadas(
        self, alumno_id: int, programa_id: int, session: Session
    ) -> dict:
        """
        Materias a las que el alumno puede inscribirse en el semestre activo.

        El semestre activo lo define el periodo de inscripcion abierto del
        programa: de ahi salen anio_lectivo y semestre. Sin periodo abierto no
        hay nada habilitado, y se devuelve el detalle para que el cliente pueda
        explicarlo en vez de mostrar una lista vacia sin motivo.

        A diferencia de get_materias_disponibles, esta consulta aplica las
        mismas validaciones que inscribir_materia, asi que puede_inscribirse no
        deberia contradecir al POST.
        """
        from v2.services.periodo_inscripcion_service import PeriodoInscripcionService

        periodo = PeriodoInscripcionService().get_periodo_vigente(programa_id, session)

        if periodo is None:
            return {
                "programa_id": programa_id,
                "periodo_inscripcion": {"abierto": False},
                "materias": [],
            }

        info_periodo = {
            "abierto": True,
            "periodo_id": periodo.id,
            "anio_lectivo": periodo.anio_lectivo,
            "semestre": periodo.semestre,
            "fecha_inicio": periodo.fecha_inicio.isoformat(),
            "fecha_fin": periodo.fecha_fin.isoformat(),
        }

        materias = session.exec(
            select(Materia).where(
                Materia.programa_id == programa_id,
                Materia.activo == True,
            ).order_by(Materia.semestre, Materia.nombre)
        ).all()

        # Todo lo que necesita el bucle se trae de una, en cinco consultas fijas.
        # Antes cada materia disparaba las suyas (estado del alumno, instancia,
        # previaturas con dos consultas por cada una, y cupo): con un plan de 30
        # materias eran ~180 consultas, y la base esta en otro servidor.
        materia_ids = [m.id for m in materias]
        estados_alumno = self._estados_del_alumno(alumno_id, materia_ids, session)
        instancias_por_materia = self._instancias_del_periodo(
            materia_ids, periodo, session
        )
        previaturas_por_materia, nombres_previas = self._previaturas_de(
            materia_ids, session
        )
        inscriptos_por_instancia = self._contar_cursando(
            [i.id for i in instancias_por_materia.values()], session
        )
        # Los nombres de las materias del plan ya estan cargados; las previas de
        # otro programa (si las hubiera) vienen de la consulta anterior.
        nombres = {m.id: m.nombre for m in materias}
        nombres.update(nombres_previas)

        resultado = []
        for materia in materias:
            # Ya aprobada, exonerada, revalidada o en curso: no se vuelve a cursar
            if estados_alumno.get(materia.id, set()) & set(self._ESTADOS_BLOQUEAN_RECURSADA):
                continue

            instancia = instancias_por_materia.get(materia.id)
            if instancia is None:
                continue  # No se dicta en el semestre activo

            cumple_previaturas, faltantes = self._evaluar_previaturas(
                previaturas_por_materia.get(materia.id, []), estados_alumno, nombres
            )

            inscriptos = inscriptos_por_instancia.get(instancia.id, 0)
            hay_cupo = instancia.cupo_maximo is None or inscriptos < instancia.cupo_maximo

            motivos = list(faltantes)
            if not hay_cupo:
                motivos.append(
                    f"La instancia esta completa ({inscriptos}/{instancia.cupo_maximo})"
                )

            resultado.append({
                "materia_id": materia.id,
                "nombre": materia.nombre,
                "codigo": materia.codigo,
                "semestre_plan": materia.semestre,
                "creditos": materia.creditos,
                "instancia_cursado_id": instancia.id,
                "anio_lectivo": instancia.anio_lectivo,
                "semestre": instancia.semestre,
                "horario": instancia.horario,
                "salon": instancia.salon,
                "cupo_maximo": instancia.cupo_maximo,
                "inscriptos": inscriptos,
                "puede_inscribirse": cumple_previaturas and hay_cupo,
                "motivos": motivos,
                "previaturas_faltantes": faltantes,
            })

        return {
            "programa_id": programa_id,
            "periodo_inscripcion": info_periodo,
            "materias": resultado,
        }

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
        self, alumno_id: int, anio_lectivo: int, session: Session
    ) -> list:
        """Materias donde el alumno tiene inscripción activa en un año lectivo."""
        inscripciones = session.exec(
            select(InscripcionMateria, InstanciaCursado)
            .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .where(
                InscripcionMateria.alumno_id == alumno_id,
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
        self, inscripcion_id: int, alumno_id: int, session: Session
    ) -> dict:
        """Vista completa de una inscripción para el alumno."""
        inscripcion = self.get_by_id(inscripcion_id, session)
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")
        if inscripcion.alumno_id != alumno_id:
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
        self, inscripcion_id: int, alumno_id: int, session: Session
    ) -> None:
        """Permite al alumno desinscribirse de una materia (solo si está CURSANDO)."""
        inscripcion = self.get_by_id(inscripcion_id, session)
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")
        if inscripcion.alumno_id != alumno_id:
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

        inscripcion.estado = EstadoInscripcionMateria.ABANDONO
        inscripcion.fecha_baja = datetime.now(get_uruguay_tz())
        inscripcion.motivo_cierre = "Desinscripcion voluntaria"
        session.add(inscripcion)
        session.commit()

    # ── Revalida ──────────────────────────────────────────────────────────────

    def revalidar_materia(
        self,
        inscripcion_id: int,
        motivo: str,
        session: Session,
    ) -> InscripcionMateria:
        """
        Revalida (convalida) una materia. Solo admin.
        Cambia estado a REVALIDADA, asigna creditos y registra motivo.
        """
        inscripcion = self.get_by_id(inscripcion_id, session)
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")

        if inscripcion.estado == EstadoInscripcionMateria.APROBADO:
            raise ValueError("La materia ya esta aprobada")
        if inscripcion.estado == EstadoInscripcionMateria.REVALIDADA:
            raise ValueError("La materia ya fue revalidada")

        ic = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
        materia = session.get(Materia, ic.materia_id) if ic else None
        creditos = materia.creditos if materia else 0

        inscripcion.estado = EstadoInscripcionMateria.REVALIDADA
        inscripcion.motivo_revalida = motivo
        inscripcion.creditos_obtenidos = creditos
        inscripcion.fecha_cierre = datetime.now(get_uruguay_tz())

        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)
        return inscripcion

    # ── Mapa de previaturas (alumno) ──────────────────────────────────────────

    def get_mapa_previaturas(
        self, alumno_id: int, programa_id: int, session: Session
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
                InscripcionMateria.alumno_id == alumno_id,
                InstanciaCursado.materia_id.in_(materia_ids),
            )
        ).all()

        # Mejor estado por materia. REVALIDADA va arriba de CURSANDO porque es
        # una materia ya cumplida; sin entrada en este dict caia en -1 y perdia
        # contra todo, incluso contra ABANDONO.
        estado_por_materia = {}
        prioridad = {
            EstadoInscripcionMateria.APROBADO: 7,
            EstadoInscripcionMateria.EXONERADO: 6,
            EstadoInscripcionMateria.REVALIDADA: 5,
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
