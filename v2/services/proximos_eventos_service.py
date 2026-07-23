"""
Servicio de "proximos eventos" para la pantalla de inicio del portal.

Agrega, en un unico listado ordenado cronologicamente, las fechas importantes
proximas segun el rol del usuario:

- ESTUDIANTE: solo lo vinculado a sus inscripciones y cursadas activas.
- DOCENTE: solo las asignaturas y examenes que tiene a cargo.
- ADMINISTRATIVO: todo, sin filtrar por asignacion personal.

Un periodo con inicio y fin se parte en dos eventos (apertura y cierre), cada uno
con su propia fecha, de modo que el filtro temporal >= now los muestre o los
oculte de forma independiente: pasada la apertura, deja de aparecer, pero el
cierre sigue vigente hasta que ocurra.
"""
from typing import Optional, List
from datetime import datetime, timedelta
from sqlmodel import Session, select

import os
from zoneinfo import ZoneInfo

from v2.models.evento import EventoProximo
from v2.models.enums import (
    TipoEventoProximo, RolUsuario,
    EstadoInscripcionPrograma, EstadoInscripcionMateria, EstadoInscripcionExamen,
    EstadoInstanciaCursado, EstadoInstanciaExamen,
)
from v2.models.alumno import Alumno
from v2.models.profesor import Profesor
from v2.models.programa import Programa
from v2.models.materia import Materia
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.periodo_inscripcion_materia import PeriodoInscripcionMateria
from v2.models.docente_materia import DocenteMateria
from v2.models.docente_instancia_examen import DocenteInstanciaExamen


def _ahora_naive() -> datetime:
    """
    Ahora en horario de Uruguay, sin tzinfo. Las fechas de la BD se guardan
    naive, asi que hay que comparar contra un naive del mismo huso para no
    mezclar aware con naive (el patron que ya usa el resto de v2).
    """
    tz = ZoneInfo(os.getenv("TIME_ZONE", "America/Montevideo"))
    return datetime.now(tz).replace(tzinfo=None)


class ProximosEventosService:

    def get_eventos(
        self,
        usuario,
        session: Session,
        limit: int = 10,
        days: Optional[int] = None,
    ) -> List[EventoProximo]:
        """
        Devuelve los proximos eventos del usuario, ordenados ascendentemente,
        recortados a `limit`. Si `days` viene, solo eventos dentro de los proximos
        N dias. Lista vacia si no hay eventos (nunca error).
        """
        ahora = _ahora_naive()
        hasta = ahora + timedelta(days=days) if days else None

        if usuario.rol == RolUsuario.ESTUDIANTE:
            eventos = self._eventos_alumno(usuario.id, session, ahora)
        elif usuario.rol == RolUsuario.DOCENTE:
            eventos = self._eventos_profesor(usuario.id, session, ahora)
        elif usuario.rol == RolUsuario.ADMINISTRATIVO:
            eventos = self._eventos_admin(session, ahora)
        else:
            eventos = []

        # Filtro temporal central: cada sub-evento se muestra solo si su fecha es
        # futura (o presente) y, si se pidio, cae dentro de la ventana de N dias.
        vigentes = [
            e for e in eventos
            if e.fecha >= ahora and (hasta is None or e.fecha <= hasta)
        ]
        vigentes.sort(key=lambda e: e.fecha)
        return vigentes[:limit]

    # ── Constructores de eventos por rol ─────────────────────────────────────

    def _eventos_alumno(self, usuario_id: int, session: Session, ahora: datetime) -> List[EventoProximo]:
        alumno = session.exec(
            select(Alumno).where(Alumno.usuario_id == usuario_id)
        ).first()
        if not alumno:
            return []

        eventos: List[EventoProximo] = []

        # 1. Apertura/cierre de inscripcion a materias de los programas del alumno
        periodos = session.exec(
            select(PeriodoInscripcionMateria, Programa)
            .join(InscripcionPrograma, InscripcionPrograma.programa_id == PeriodoInscripcionMateria.programa_id)
            .join(Programa, Programa.id == PeriodoInscripcionMateria.programa_id)
            .where(
                InscripcionPrograma.alumno_id == alumno.id,
                InscripcionPrograma.estado == EstadoInscripcionPrograma.ACTIVA,
                PeriodoInscripcionMateria.habilitado == True,
                PeriodoInscripcionMateria.fecha_fin >= ahora,
            )
        ).all()
        for periodo, programa in periodos:
            eventos.extend(self._eventos_periodo(periodo, programa))

        # 2. Ventana de inscripcion a examen para materias en estado A_EXAMEN
        examenes_disponibles = session.exec(
            select(InstanciaExamen, Materia)
            .join(InstanciaCursado, InstanciaCursado.materia_id == InstanciaExamen.materia_id)
            .join(InscripcionMateria, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .join(Materia, Materia.id == InstanciaExamen.materia_id)
            .where(
                InscripcionMateria.alumno_id == alumno.id,
                InscripcionMateria.estado == EstadoInscripcionMateria.A_EXAMEN,
                InstanciaExamen.habilitado == True,
                InstanciaExamen.estado != EstadoInstanciaExamen.CANCELADO,
                InstanciaExamen.fecha_fin_inscripcion >= ahora,
            )
        ).all()
        for instancia, materia in examenes_disponibles:
            eventos.extend(self._eventos_inscripcion_examen(instancia, materia))

        # 3. Examenes en los que el alumno figura inscripto
        inscripto = session.exec(
            select(InstanciaExamen, Materia)
            .join(InscripcionExamen, InscripcionExamen.instancia_examen_id == InstanciaExamen.id)
            .join(InscripcionMateria, InscripcionMateria.id == InscripcionExamen.inscripcion_materia_id)
            .join(Materia, Materia.id == InstanciaExamen.materia_id)
            .where(
                InscripcionMateria.alumno_id == alumno.id,
                InscripcionExamen.estado == EstadoInscripcionExamen.INSCRIPTO,
                InstanciaExamen.estado != EstadoInstanciaExamen.CANCELADO,
                InstanciaExamen.fecha_examen >= ahora,
            )
        ).all()
        for instancia, materia in inscripto:
            eventos.append(self._evento_fecha_examen(instancia, materia))

        # 4. Inicio/fin de dictado de materias que esta cursando
        cursando = session.exec(
            select(InstanciaCursado, Materia)
            .join(InscripcionMateria, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .join(Materia, Materia.id == InstanciaCursado.materia_id)
            .where(
                InscripcionMateria.alumno_id == alumno.id,
                InscripcionMateria.estado == EstadoInscripcionMateria.CURSANDO,
                InstanciaCursado.estado != EstadoInstanciaCursado.CANCELADA,
            )
        ).all()
        for instancia, materia in cursando:
            eventos.extend(self._eventos_dictado(instancia, materia))

        return eventos

    def _eventos_profesor(self, usuario_id: int, session: Session, ahora: datetime) -> List[EventoProximo]:
        profesor = session.exec(
            select(Profesor).where(Profesor.usuario_id == usuario_id)
        ).first()
        if not profesor:
            return []

        eventos: List[EventoProximo] = []

        # 1/2. Inicio/fin de dictado de las asignaturas a cargo
        a_cargo = session.exec(
            select(InstanciaCursado, Materia)
            .join(DocenteMateria, DocenteMateria.instancia_cursado_id == InstanciaCursado.id)
            .join(Materia, Materia.id == InstanciaCursado.materia_id)
            .where(
                DocenteMateria.profesor_id == profesor.id,
                InstanciaCursado.estado != EstadoInstanciaCursado.CANCELADA,
            )
        ).all()
        for instancia, materia in a_cargo:
            eventos.extend(self._eventos_dictado(instancia, materia))

        # 3. Mesas de examen que debe tomar
        mesas = session.exec(
            select(InstanciaExamen, Materia)
            .join(DocenteInstanciaExamen, DocenteInstanciaExamen.instancia_examen_id == InstanciaExamen.id)
            .join(Materia, Materia.id == InstanciaExamen.materia_id)
            .where(
                DocenteInstanciaExamen.profesor_id == profesor.id,
                InstanciaExamen.estado != EstadoInstanciaExamen.CANCELADO,
                InstanciaExamen.fecha_examen >= ahora,
            )
        ).all()
        for instancia, materia in mesas:
            eventos.append(self._evento_fecha_examen(instancia, materia))

        return eventos

    def _eventos_admin(self, session: Session, ahora: datetime) -> List[EventoProximo]:
        eventos: List[EventoProximo] = []

        # 1. Todos los periodos de inscripcion a materia habilitados
        periodos = session.exec(
            select(PeriodoInscripcionMateria, Programa)
            .join(Programa, Programa.id == PeriodoInscripcionMateria.programa_id)
            .where(
                PeriodoInscripcionMateria.habilitado == True,
                PeriodoInscripcionMateria.fecha_fin >= ahora,
            )
        ).all()
        for periodo, programa in periodos:
            eventos.extend(self._eventos_periodo(periodo, programa))

        # 2. Todas las instancias de examen: ventana de inscripcion + fecha de examen
        instancias_examen = session.exec(
            select(InstanciaExamen, Materia)
            .join(Materia, Materia.id == InstanciaExamen.materia_id)
            .where(InstanciaExamen.estado != EstadoInstanciaExamen.CANCELADO)
        ).all()
        for instancia, materia in instancias_examen:
            eventos.extend(self._eventos_inscripcion_examen(instancia, materia))
            eventos.append(self._evento_fecha_examen(instancia, materia))

        # 3. Inicio/fin de dictado de todas las instancias de cursado
        cursados = session.exec(
            select(InstanciaCursado, Materia)
            .join(Materia, Materia.id == InstanciaCursado.materia_id)
            .where(InstanciaCursado.estado != EstadoInstanciaCursado.CANCELADA)
        ).all()
        for instancia, materia in cursados:
            eventos.extend(self._eventos_dictado(instancia, materia))

        return eventos

    # ── Fabricas de eventos por tipo de fuente ───────────────────────────────

    def _eventos_periodo(self, periodo: PeriodoInscripcionMateria, programa: Programa) -> List[EventoProximo]:
        base = dict(
            referencia_tipo="periodo_inscripcion_materia",
            referencia_id=periodo.id,
            programa_nombre=programa.nombre,
            anio_lectivo=periodo.anio_lectivo,
        )
        return [
            EventoProximo(
                tipo=TipoEventoProximo.APERTURA_INSCRIPCION_MATERIA,
                titulo=f"Apertura de inscripciones — {programa.nombre}",
                descripcion="Comienza el periodo de inscripcion a materias.",
                fecha=periodo.fecha_inicio,
                **base,
            ),
            EventoProximo(
                tipo=TipoEventoProximo.CIERRE_INSCRIPCION_MATERIA,
                titulo=f"Cierre de inscripciones — {programa.nombre}",
                descripcion="Ultimo dia para inscribirse a materias.",
                fecha=periodo.fecha_fin,
                **base,
            ),
        ]

    def _eventos_inscripcion_examen(self, instancia: InstanciaExamen, materia: Materia) -> List[EventoProximo]:
        base = dict(
            referencia_tipo="instancia_examen",
            referencia_id=instancia.id,
            materia_nombre=materia.nombre,
            materia_codigo=materia.codigo,
        )
        return [
            EventoProximo(
                tipo=TipoEventoProximo.APERTURA_INSCRIPCION_EXAMEN,
                titulo=f"Apertura de inscripcion a examen — {materia.nombre}",
                descripcion=f"Comienza la inscripcion a {instancia.nombre}.",
                fecha=instancia.fecha_inicio_inscripcion,
                **base,
            ),
            EventoProximo(
                tipo=TipoEventoProximo.CIERRE_INSCRIPCION_EXAMEN,
                titulo=f"Cierre de inscripcion a examen — {materia.nombre}",
                descripcion=f"Ultimo dia para inscribirse a {instancia.nombre}.",
                fecha=instancia.fecha_fin_inscripcion,
                **base,
            ),
        ]

    def _evento_fecha_examen(self, instancia: InstanciaExamen, materia: Materia) -> EventoProximo:
        return EventoProximo(
            tipo=TipoEventoProximo.FECHA_EXAMEN,
            titulo=f"Examen — {materia.nombre}",
            descripcion=instancia.nombre,
            fecha=instancia.fecha_examen,
            referencia_tipo="instancia_examen",
            referencia_id=instancia.id,
            materia_nombre=materia.nombre,
            materia_codigo=materia.codigo,
        )

    def _eventos_dictado(self, instancia: InstanciaCursado, materia: Materia) -> List[EventoProximo]:
        base = dict(
            referencia_tipo="instancia_cursado",
            referencia_id=instancia.id,
            materia_nombre=materia.nombre,
            materia_codigo=materia.codigo,
            anio_lectivo=instancia.anio_lectivo,
        )
        eventos: List[EventoProximo] = []
        # fecha_inicio / fecha_fin son nullable: solo generamos el evento si existe.
        if instancia.fecha_inicio is not None:
            eventos.append(EventoProximo(
                tipo=TipoEventoProximo.INICIO_DICTADO,
                titulo=f"Inicio de dictado — {materia.nombre}",
                descripcion="Comienza el cursado de la asignatura.",
                fecha=instancia.fecha_inicio,
                **base,
            ))
        if instancia.fecha_fin is not None:
            eventos.append(EventoProximo(
                tipo=TipoEventoProximo.FIN_DICTADO,
                titulo=f"Fin de dictado — {materia.nombre}",
                descripcion="Finaliza el cursado de la asignatura.",
                fecha=instancia.fecha_fin,
                **base,
            ))
        return eventos
