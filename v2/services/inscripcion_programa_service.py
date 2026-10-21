from sqlmodel import Session, select
from typing import Optional, List

from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.enums import EstadoInscripcionPrograma
from database.services.filter.filters import BaseServiceWithFilters


class InscripcionProgramaService(BaseServiceWithFilters[InscripcionPrograma]):
    def __init__(self):
        super().__init__(InscripcionPrograma)

    def inscribir_programa(
        self, alumno_id: int, programa_id: int, anio_ingreso: int, session: Session
    ) -> InscripcionPrograma:
        """Inscribe un alumno a un programa. Valida que no exista inscripción activa duplicada."""
        existente = session.exec(
            select(InscripcionPrograma).where(
                InscripcionPrograma.alumno_id == alumno_id,
                InscripcionPrograma.programa_id == programa_id,
                InscripcionPrograma.estado == EstadoInscripcionPrograma.ACTIVA,
            )
        ).first()
        if existente:
            raise ValueError(f"El alumno ya tiene una inscripción activa en este programa (ID: {existente.id})")

        inscripcion = InscripcionPrograma(
            alumno_id=alumno_id,
            programa_id=programa_id,
            anio_ingreso=anio_ingreso,
        )
        session.add(inscripcion)
        session.flush()
        session.refresh(inscripcion)
        return inscripcion

    def get_programas_alumno(self, alumno_id: int, session: Session) -> List[InscripcionPrograma]:
        """Lista todas las inscripciones a programas de un alumno."""
        return list(session.exec(
            select(InscripcionPrograma).where(
                InscripcionPrograma.alumno_id == alumno_id
            )
        ).all())

    def cambiar_estado(
        self, inscripcion_id: int, nuevo_estado: EstadoInscripcionPrograma, session: Session
    ) -> InscripcionPrograma:
        """Cambia el estado de una inscripción a programa."""
        inscripcion = session.get(InscripcionPrograma, inscripcion_id)
        if not inscripcion:
            raise ValueError(f"Inscripción a programa no encontrada: {inscripcion_id}")
        inscripcion.estado = nuevo_estado
        session.flush()
        session.refresh(inscripcion)
        return inscripcion

    def dar_de_baja(
        self,
        inscripcion_id: int,
        motivo: str,
        session: Session,
        cerrar_materias: bool = True,
    ) -> InscripcionPrograma:
        """
        Da de baja a un alumno de un programa.

        Deja registro de cuándo y por qué: `fecha_baja` y `motivo_baja` existían en
        el modelo desde Fase 1 pero ningún servicio los escribía, así que la baja
        no se podía hacer por sistema.

        cerrar_materias: si el alumno deja el programa, sus materias en curso
        quedan como ABANDONO. Se puede desactivar para casos donde la baja del
        programa no implica soltar las cursadas (ej: un pase administrativo).
        """
        from datetime import datetime
        import os
        from zoneinfo import ZoneInfo
        from v2.models.inscripcion_materia import InscripcionMateria
        from v2.models.instancia_cursado import InstanciaCursado
        from v2.models.materia import Materia
        from v2.models.enums import EstadoInscripcionMateria

        inscripcion = session.get(InscripcionPrograma, inscripcion_id)
        if not inscripcion:
            raise ValueError(f"Inscripción a programa no encontrada: {inscripcion_id}")
        if inscripcion.estado == EstadoInscripcionPrograma.BAJA:
            raise ValueError("La inscripción al programa ya está dada de baja")
        if inscripcion.estado == EstadoInscripcionPrograma.COMPLETADA:
            raise ValueError(
                "No se puede dar de baja una inscripción ya completada: el alumno egresó"
            )
        if not motivo or not motivo.strip():
            raise ValueError("El motivo de la baja es obligatorio")

        ahora = datetime.now(ZoneInfo(os.getenv("TIME_ZONE", "America/Montevideo")))

        inscripcion.estado = EstadoInscripcionPrograma.BAJA
        inscripcion.fecha_baja = ahora
        inscripcion.motivo_baja = motivo.strip()
        session.add(inscripcion)

        materias_cerradas = 0
        if cerrar_materias:
            # Solo las materias de ESTE programa: un alumno puede estar en varios
            # y la baja de uno no toca las cursadas de los otros.
            en_curso = session.exec(
                select(InscripcionMateria)
                .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
                .join(Materia, InstanciaCursado.materia_id == Materia.id)
                .where(
                    InscripcionMateria.alumno_id == inscripcion.alumno_id,
                    Materia.programa_id == inscripcion.programa_id,
                    InscripcionMateria.estado == EstadoInscripcionMateria.CURSANDO,
                )
            ).all()

            for insc_materia in en_curso:
                insc_materia.estado = EstadoInscripcionMateria.ABANDONO
                insc_materia.fecha_baja = ahora
                insc_materia.motivo_cierre = f"Baja del programa: {motivo.strip()}"[:255]
                session.add(insc_materia)
                materias_cerradas += 1

        session.commit()
        session.refresh(inscripcion)

        # Notificación best-effort: no puede tumbar una baja ya registrada
        object.__setattr__(inscripcion, "materias_cerradas", materias_cerradas)
        try:
            from v2.services import get_v2_services
            from v2.models.alumno import Alumno
            from v2.models.usuario import Usuario
            from v2.models.programa import Programa

            alumno = session.get(Alumno, inscripcion.alumno_id)
            usuario = session.get(Usuario, alumno.usuario_id) if alumno else None
            programa = session.get(Programa, inscripcion.programa_id)
            if usuario and programa:
                get_v2_services().notificationService.notificar_baja_procesada(
                    inscripcion, usuario, programa, session
                )
        except Exception:
            pass

        return inscripcion
