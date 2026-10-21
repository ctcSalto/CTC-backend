from typing import Optional, List
from decimal import Decimal
from sqlmodel import Session, select, col

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.calificacion import Calificacion
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
from v2.models.docente_materia import DocenteMateria
from v2.models.enums import EstadoInscripcionMateria
from v2.services.grading_engine import calcular_estado

import os
from datetime import datetime
from zoneinfo import ZoneInfo


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class CalificacionService(BaseServiceWithFilters[Calificacion]):
    def __init__(self):
        super().__init__(Calificacion)

    # ── Guardar calificación individual ─────────────────────────────────────

    def guardar_calificacion(
        self,
        cargado_por_id: int,
        inscripcion_id: int,
        instancia_evaluacion_id: int,
        nota: Decimal,
        session: Session,
        equipo_id: Optional[int] = None,
        observaciones: Optional[str] = None,
        instancia_cursado_id: Optional[int] = None,
    ) -> Calificacion:
        """
        Carga o actualiza una calificación (upsert por inscripcion+instancia).
        Recalcula automáticamente el estado de la inscripción.

        instancia_cursado_id: la cursada sobre la que el llamador tiene permiso.
        Las rutas la toman del path y ahi validan que el docente este asignado,
        pero ese permiso no dice nada sobre la inscripcion ni la evaluacion que
        vienen en el body. Sin este parametro, un docente asignado a una sola
        cursada podia escribir notas en la inscripcion de cualquier alumno del
        sistema.
        """
        # 1. Validar inscripción
        inscripcion = session.exec(
            select(InscripcionMateria).where(InscripcionMateria.id == inscripcion_id)
        ).first()
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")
        self._validar_editable(inscripcion, session)

        # 2. Validar instancia de evaluación
        instancia = session.exec(
            select(MateriaInstanciaEvaluacion).where(
                MateriaInstanciaEvaluacion.id == instancia_evaluacion_id
            )
        ).first()
        if not instancia:
            raise ValueError(f"Instancia de evaluacion {instancia_evaluacion_id} no encontrada")

        # 2b. La evaluacion y la inscripcion tienen que ser de la misma cursada,
        # y esa cursada tiene que ser sobre la que el llamador tiene permiso.
        if instancia.instancia_cursado_id != inscripcion.instancia_cursado_id:
            raise ValueError(
                f"La instancia de evaluacion {instancia_evaluacion_id} no pertenece "
                f"a la cursada de la inscripcion {inscripcion_id}"
            )
        if (
            instancia_cursado_id is not None
            and inscripcion.instancia_cursado_id != instancia_cursado_id
        ):
            raise ValueError(
                f"La inscripcion {inscripcion_id} no pertenece a la instancia de "
                f"cursado {instancia_cursado_id}"
            )

        # 2c. La evaluacion tiene que estar en el snapshot de la inscripcion.
        # El snapshot congela las reglas al momento de inscribirse: una evaluacion
        # agregada despues no puede alterar la nota de quien ya estaba inscripto.
        ids_snapshot = {
            inst["id"] for inst in (inscripcion.snapshot_instancias or [])
            if inst.get("id") is not None
        }
        if ids_snapshot and instancia_evaluacion_id not in ids_snapshot:
            raise ValueError(
                f"La instancia de evaluacion {instancia_evaluacion_id} no estaba "
                f"vigente cuando el alumno se inscribio, asi que no computa para su "
                f"nota. Para incorporarla hay que actualizar la inscripcion."
            )

        # 3. Validar rango de nota
        nota_decimal = Decimal(str(nota))
        if nota_decimal < 0 or nota_decimal > instancia.peso_maximo:
            raise ValueError(
                f"La nota debe estar entre 0 y {instancia.peso_maximo} (peso maximo de la instancia)"
            )

        # 4. Instancia grupal: la nota es del equipo, no de una persona
        if instancia.es_grupal:
            if not equipo_id:
                raise ValueError("La instancia es grupal, se requiere equipo_id")
            return self._calificar_equipo(
                cargado_por_id=cargado_por_id,
                inscripcion=inscripcion,
                instancia=instancia,
                equipo_id=equipo_id,
                nota=nota_decimal,
                session=session,
                observaciones=observaciones,
            )

        return self._upsert_calificacion(
            cargado_por_id=cargado_por_id,
            inscripcion_id=inscripcion_id,
            instancia_evaluacion_id=instancia_evaluacion_id,
            nota=nota_decimal,
            session=session,
            equipo_id=equipo_id,
            observaciones=observaciones,
        )

    # ── Editabilidad ────────────────────────────────────────────────────────

    # Cerrar la materia no congela las notas: el docente tiene que poder corregir
    # un error de carga. Un 60 tipeado en lugar de un 90 dejaba al alumno
    # reprobado sin ninguna via de vuelta.
    ESTADOS_EDITABLES = (
        EstadoInscripcionMateria.CURSANDO,
        EstadoInscripcionMateria.A_EXAMEN,
        EstadoInscripcionMateria.EXONERADO,
        EstadoInscripcionMateria.APROBADO,
        EstadoInscripcionMateria.REPROBADO,
    )

    # Estos no se editan calificando: no los decidio el curso.
    MOTIVO_NO_EDITABLE = {
        EstadoInscripcionMateria.REVALIDADA:
            "la materia fue revalidada por administracion, no cursada. Para "
            "cambiarla hay que revertir la revalida.",
        EstadoInscripcionMateria.PERDIDO_INASISTENCIA:
            "la materia se perdio por inasistencia. Para reabrirla hay que "
            "corregir las faltas.",
        EstadoInscripcionMateria.ABANDONO:
            "la inscripcion esta dada de baja.",
    }

    def _validar_editable(self, inscripcion: InscripcionMateria, session: Session) -> None:
        """
        Decide si se pueden tocar las notas de curso de esta inscripcion.

        Una inscripcion cerrada por el curso (exonerado / aprobado / reprobado) se
        puede corregir: recalcular vuelve a derivar el estado de las notas. Pero
        si la materia se aprobo rindiendo examen, recalcular desde las notas de
        curso pisaria ese resultado y dejaria la inscripcion a examen colgada, asi
        que ese caso se bloquea y se deriva a la correccion del examen.
        """
        estado = inscripcion.estado

        motivo = self.MOTIVO_NO_EDITABLE.get(estado)
        if motivo:
            raise ValueError(f"No se puede calificar: {motivo}")

        if estado not in self.ESTADOS_EDITABLES:
            raise ValueError(
                f"No se puede calificar una inscripcion en estado {estado.value}"
            )

        if estado == EstadoInscripcionMateria.APROBADO and self._aprobo_por_examen(
            inscripcion.id, session
        ):
            raise ValueError(
                "No se puede calificar: la materia se aprobo rindiendo examen. "
                "Corregir la nota del examen, no la del curso."
            )

    @staticmethod
    def _aprobo_por_examen(inscripcion_id: int, session: Session) -> bool:
        from v2.models.inscripcion_examen import InscripcionExamen
        from v2.models.enums import EstadoInscripcionExamen

        return session.exec(
            select(InscripcionExamen).where(
                InscripcionExamen.inscripcion_materia_id == inscripcion_id,
                InscripcionExamen.estado == EstadoInscripcionExamen.APROBADO,
            )
        ).first() is not None

    # ── Escritura de una calificación ───────────────────────────────────────

    def _upsert_calificacion(
        self,
        cargado_por_id: int,
        inscripcion_id: int,
        instancia_evaluacion_id: int,
        nota: Decimal,
        session: Session,
        equipo_id: Optional[int] = None,
        observaciones: Optional[str] = None,
    ) -> Calificacion:
        """Alta o actualización de la nota de UNA inscripción, y su recálculo."""
        existente = session.exec(
            select(Calificacion).where(
                Calificacion.inscripcion_id == inscripcion_id,
                Calificacion.instancia_evaluacion_id == instancia_evaluacion_id,
            )
        ).first()

        if existente:
            existente.nota = nota
            existente.cargado_por_id = cargado_por_id
            existente.equipo_id = equipo_id
            existente.observaciones = observaciones
            existente.fecha = datetime.now(get_uruguay_tz())
            calificacion = existente
        else:
            calificacion = Calificacion(
                inscripcion_id=inscripcion_id,
                instancia_evaluacion_id=instancia_evaluacion_id,
                nota=nota,
                equipo_id=equipo_id,
                cargado_por_id=cargado_por_id,
                observaciones=observaciones,
            )

        session.add(calificacion)
        session.commit()
        session.refresh(calificacion)

        self._recalcular_estado(inscripcion_id, session)
        return calificacion

    # ── Calificación grupal ─────────────────────────────────────────────────

    def _calificar_equipo(
        self,
        cargado_por_id: int,
        inscripcion,
        instancia,
        equipo_id: int,
        nota: Decimal,
        session: Session,
        observaciones: Optional[str] = None,
    ) -> Calificacion:
        """
        Aplica la nota a todos los integrantes del equipo.

        Una evaluacion grupal se corrige una vez y vale para el equipo entero: el
        obligatorio suele ser grupal, aunque un equipo puede tener un solo
        integrante. Antes la nota se guardaba en una sola inscripcion y el
        equipo_id quedaba de adorno, asi que el docente terminaba cargando la
        misma nota una por una.

        Devuelve la calificacion de la inscripcion que pidio el llamador, para no
        cambiarle la forma a la respuesta.
        """
        from v2.models.equipo import Equipo, EquipoMiembro

        equipo = session.get(Equipo, equipo_id)
        if not equipo:
            raise ValueError(f"Equipo {equipo_id} no encontrado")
        if equipo.instancia_evaluacion_id != instancia.id:
            raise ValueError(
                f"El equipo {equipo_id} no pertenece a la instancia de evaluacion "
                f"{instancia.id}"
            )

        miembros = session.exec(
            select(EquipoMiembro).where(EquipoMiembro.equipo_id == equipo_id)
        ).all()
        alumnos_ids = {m.alumno_id for m in miembros}

        if inscripcion.alumno_id not in alumnos_ids:
            raise ValueError(
                f"El alumno de la inscripcion {inscripcion.id} no integra el "
                f"equipo {equipo_id}"
            )

        # Inscripciones de los integrantes en la MISMA cursada. Se usa el mismo
        # criterio de editabilidad que para una nota individual: si no, corregir
        # un obligatorio ya cerrado no encontraba a ningun integrante y fallaba.
        inscripciones_equipo = session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.instancia_cursado_id == inscripcion.instancia_cursado_id,
                col(InscripcionMateria.alumno_id).in_(alumnos_ids),
                col(InscripcionMateria.estado).in_(self.ESTADOS_EDITABLES),
            )
        ).all()

        resultado = None
        for insc_miembro in inscripciones_equipo:
            # Un integrante puede no ser editable por su propia situacion (por
            # ejemplo, ya aprobo rindiendo examen). Se lo saltea en vez de abortar:
            # el resto del equipo tiene que recibir su nota igual.
            try:
                self._validar_editable(insc_miembro, session)
            except ValueError:
                continue

            ids_snapshot = {
                inst["id"] for inst in (insc_miembro.snapshot_instancias or [])
                if inst.get("id") is not None
            }
            if ids_snapshot and instancia.id not in ids_snapshot:
                continue  # la evaluacion no estaba vigente para este integrante

            calificacion = self._upsert_calificacion(
                cargado_por_id=cargado_por_id,
                inscripcion_id=insc_miembro.id,
                instancia_evaluacion_id=instancia.id,
                nota=nota,
                session=session,
                equipo_id=equipo_id,
                observaciones=observaciones,
            )
            if insc_miembro.id == inscripcion.id:
                resultado = calificacion

        if resultado is None:
            raise ValueError(
                f"No se pudo registrar la nota en la inscripcion {inscripcion.id}"
            )
        return resultado

    # ── Carga masiva ────────────────────────────────────────────────────────

    def guardar_batch(
        self,
        cargado_por_id: int,
        instancia_evaluacion_id: int,
        calificaciones: list,
        session: Session,
        instancia_cursado_id: Optional[int] = None,
    ) -> dict:
        """
        Carga masiva de notas para una instancia.
        Retorna {exitosos: int, errores: [{inscripcion_id, error}]}

        Los errores se acumulan por item: una fila invalida no aborta el resto.
        """
        exitosos = 0
        errores = []

        for item in calificaciones:
            try:
                self.guardar_calificacion(
                    cargado_por_id=cargado_por_id,
                    inscripcion_id=item.inscripcion_id,
                    instancia_evaluacion_id=instancia_evaluacion_id,
                    nota=item.nota,
                    session=session,
                    equipo_id=item.equipo_id,
                    observaciones=item.observaciones,
                    instancia_cursado_id=instancia_cursado_id,
                )
                exitosos += 1
            except ValueError as e:
                errores.append({
                    "inscripcion_id": item.inscripcion_id,
                    "error": str(e),
                })

        return {"exitosos": exitosos, "errores": errores}

    # ── Consultas ───────────────────────────────────────────────────────────

    def get_calificaciones_inscripcion(
        self, inscripcion_id: int, session: Session
    ) -> List[Calificacion]:
        """Todas las calificaciones de una inscripción"""
        return list(session.exec(
            select(Calificacion)
            .where(Calificacion.inscripcion_id == inscripcion_id)
            .order_by(Calificacion.instancia_evaluacion_id)
        ).all())

    def get_calificaciones_instancia_cursado(
        self,
        instancia_cursado_id: int,
        instancia_evaluacion_id: int,
        session: Session,
    ) -> list:
        """
        Retorna las notas de todos los alumnos en una instancia de evaluación específica.
        Para vista docente: "lista de alumnos de Primer Parcial"
        """
        from v2.models.usuario import Usuario
        from v2.models.alumno import Alumno

        # Obtener inscripciones de la instancia de cursado
        inscripciones = session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.instancia_cursado_id == instancia_cursado_id,
            )
        ).all()

        resultado = []
        for insc in inscripciones:
            usuario = session.exec(
                select(Usuario)
                .join(Alumno, Alumno.usuario_id == Usuario.id)
                .where(Alumno.id == insc.alumno_id)
            ).first()

            calificacion = session.exec(
                select(Calificacion).where(
                    Calificacion.inscripcion_id == insc.id,
                    Calificacion.instancia_evaluacion_id == instancia_evaluacion_id,
                )
            ).first()

            resultado.append({
                "inscripcion_id": insc.id,
                "alumno_id": insc.alumno_id,
                "nombre": usuario.nombre if usuario else "",
                "apellido": usuario.apellido if usuario else "",
                "nota": float(calificacion.nota) if calificacion else None,
                "calificacion_id": calificacion.id if calificacion else None,
                "observaciones": calificacion.observaciones if calificacion else None,
            })

        return resultado

    # ── Nota final directa ──────────────────────────────────────────────────

    def cargar_nota_final_directa(
        self,
        cargado_por_id: int,
        inscripcion_id: int,
        nota: Decimal,
        session: Session,
        instancia_cursado_id: Optional[int] = None,
    ) -> InscripcionMateria:
        """
        Profesor carga nota final ya promediada, sin pasar por instancias de evaluación.
        Ejecuta el grading engine con todas_instancias_calificadas=True.

        instancia_cursado_id: la cursada sobre la que el llamador tiene permiso.
        Mismo motivo que en guardar_calificacion: el permiso de la ruta es sobre
        la cursada del path, no sobre la inscripcion que viene en el body.
        """
        inscripcion = session.exec(
            select(InscripcionMateria).where(InscripcionMateria.id == inscripcion_id)
        ).first()
        if not inscripcion:
            raise ValueError(f"Inscripcion {inscripcion_id} no encontrada")
        if (
            instancia_cursado_id is not None
            and inscripcion.instancia_cursado_id != instancia_cursado_id
        ):
            raise ValueError(
                f"La inscripcion {inscripcion_id} no pertenece a la instancia de "
                f"cursado {instancia_cursado_id}"
            )
        # Misma regla que al calificar por instancias: una nota final cargada mal
        # se tiene que poder corregir despues de cerrada.
        self._validar_editable(inscripcion, session)

        snapshot_pol = inscripcion.snapshot_politica or {}
        nota_maxima = Decimal(str(snapshot_pol.get("nota_maxima", 100)))
        nota_decimal = Decimal(str(nota))

        if nota_decimal < 0 or nota_decimal > nota_maxima:
            raise ValueError(f"La nota debe estar entre 0 y {nota_maxima}")

        # Obtener créditos de la materia via instancia_cursado
        from v2.models.instancia_cursado import InstanciaCursado
        from v2.models.materia import Materia
        instancia_cursado = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
        materia = session.get(Materia, instancia_cursado.materia_id) if instancia_cursado else None
        creditos = materia.creditos if materia else 0

        # Calcular estado con el grading engine
        resultado = calcular_estado(
            nota_curso=nota_decimal,
            snapshot_politica=snapshot_pol,
            creditos_materia=creditos,
            todas_instancias_calificadas=True,
        )

        # Actualizar inscripción
        inscripcion.nota_final_directa = nota_decimal
        inscripcion.nota_curso = resultado["nota_curso"]
        inscripcion.nota_final = resultado["nota_final"]
        inscripcion.estado = resultado["estado"]
        inscripcion.creditos_obtenidos = resultado["creditos_obtenidos"]

        inscripcion.fecha_cierre = self._fecha_cierre_para(
            resultado["estado"], inscripcion.fecha_cierre
        )

        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)
        return inscripcion

    # ── Recálculo automático de estado ──────────────────────────────────────

    # Estados en los que la materia queda cerrada por el curso
    _ESTADOS_CIERRAN = (
        EstadoInscripcionMateria.EXONERADO,
        EstadoInscripcionMateria.APROBADO,
        EstadoInscripcionMateria.REPROBADO,
    )

    @classmethod
    def _fecha_cierre_para(cls, estado, fecha_cierre_actual):
        """
        Al corregir una nota la inscripcion puede volver a abrirse (por ejemplo de
        REPROBADO a A_EXAMEN). En ese caso hay que limpiar la fecha de cierre: si
        quedaba la vieja, la materia figuraba cerrada y abierta a la vez.
        """
        if estado in cls._ESTADOS_CIERRAN:
            return fecha_cierre_actual or datetime.now(get_uruguay_tz())
        return None

    def _recalcular_estado(self, inscripcion_id: int, session: Session):
        """
        Recalcula el estado de la inscripción basándose en las calificaciones
        actuales y los snapshots de la política/instancias.
        """
        inscripcion = session.exec(
            select(InscripcionMateria).where(InscripcionMateria.id == inscripcion_id)
        ).first()
        if not inscripcion:
            return

        # Estados que no los decidio el curso: recalcular los pisaria.
        # REVALIDADA es una decision administrativa; las otras dos son cierres
        # manuales por faltas o baja.
        if inscripcion.estado in (
            EstadoInscripcionMateria.PERDIDO_INASISTENCIA,
            EstadoInscripcionMateria.ABANDONO,
            EstadoInscripcionMateria.REVALIDADA,
        ):
            return

        snapshot_pol = inscripcion.snapshot_politica or {}
        snapshot_inst = inscripcion.snapshot_instancias or []

        if not snapshot_pol or not snapshot_inst:
            return

        # Cargar todas las calificaciones
        calificaciones = session.exec(
            select(Calificacion).where(Calificacion.inscripcion_id == inscripcion_id)
        ).all()

        # Sumar solo las notas de las instancias que estaban en el snapshot.
        # Sin este filtro, una evaluacion creada despues de la inscripcion sumaba
        # igual y podia mover el estado (ej: de A_EXAMEN a EXONERADO) por una
        # regla que no existia cuando el alumno se inscribio, que es justamente
        # lo que el snapshot tiene que impedir. El filtro tambien protege de los
        # datos que hayan quedado mal cargados antes de esta validacion.
        ids_snapshot = {
            inst["id"] for inst in snapshot_inst if inst.get("id") is not None
        }
        nota_total = Decimal("0")
        instancias_calificadas = set()
        for cal in calificaciones:
            if cal.instancia_evaluacion_id not in ids_snapshot:
                continue
            nota_total += cal.nota
            instancias_calificadas.add(cal.instancia_evaluacion_id)

        todas_calificadas = ids_snapshot.issubset(instancias_calificadas)

        # Obtener créditos de la materia via instancia_cursado
        from v2.models.instancia_cursado import InstanciaCursado
        from v2.models.materia import Materia
        instancia_cursado = session.get(InstanciaCursado, inscripcion.instancia_cursado_id)
        materia = session.get(Materia, instancia_cursado.materia_id) if instancia_cursado else None
        creditos = materia.creditos if materia else 0

        # Calcular con el motor
        resultado = calcular_estado(
            nota_curso=nota_total,
            snapshot_politica=snapshot_pol,
            creditos_materia=creditos,
            todas_instancias_calificadas=todas_calificadas,
        )

        # Actualizar inscripción
        inscripcion.estado = resultado["estado"]
        inscripcion.nota_curso = resultado["nota_curso"]
        inscripcion.nota_final = resultado["nota_final"]
        inscripcion.creditos_obtenidos = resultado["creditos_obtenidos"]

        inscripcion.fecha_cierre = self._fecha_cierre_para(
            resultado["estado"], inscripcion.fecha_cierre
        )

        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)

    # ── Validar asignación docente ──────────────────────────────────────────

    def validar_docente_instancia_cursado(
        self, profesor_id: int, instancia_cursado_id: int, session: Session
    ) -> bool:
        """Verifica que el profesor esté asignado a la instancia de cursado."""
        asignacion = session.exec(
            select(DocenteMateria).where(
                DocenteMateria.profesor_id == profesor_id,
                DocenteMateria.instancia_cursado_id == instancia_cursado_id,
            )
        ).first()
        return asignacion is not None
