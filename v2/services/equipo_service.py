from typing import Optional, List
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.equipo import Equipo, EquipoMiembro
from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.enums import EstadoInscripcionMateria


class EquipoService(BaseServiceWithFilters[Equipo]):
    def __init__(self):
        super().__init__(Equipo)

    # ── Validaciones de pertenencia ──────────────────────────────────────────

    @staticmethod
    def _validar_alumno_cursa(
        alumno_id: int, instancia: MateriaInstanciaEvaluacion, session: Session
    ) -> None:
        """
        El integrante tiene que estar inscripto a la cursada de esa evaluacion.

        Sin esto se podia armar un equipo con alumnos de otra materia: la nota
        grupal despues no les llegaba (no tienen inscripcion donde escribirla) y
        el equipo quedaba mintiendo sobre quienes lo integran.
        """
        inscripcion = session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.alumno_id == alumno_id,
                InscripcionMateria.instancia_cursado_id == instancia.instancia_cursado_id,
            )
        ).first()
        if not inscripcion:
            raise ValueError(
                f"El alumno {alumno_id} no esta inscripto a la cursada de esta evaluacion"
            )

    @staticmethod
    def _validar_no_esta_en_otro_equipo(
        alumno_id: int,
        instancia_evaluacion_id: int,
        session: Session,
        excluir_equipo_id: Optional[int] = None,
    ) -> None:
        """
        Un alumno no puede integrar dos equipos de la misma evaluacion.

        Si podia, calificar el segundo equipo le pisaba la nota que le habia
        dejado el primero, en silencio: la calificacion es unica por
        inscripcion + evaluacion, asi que gana el ultimo que se corrige.
        """
        stmt = (
            select(EquipoMiembro)
            .join(Equipo, EquipoMiembro.equipo_id == Equipo.id)
            .where(
                EquipoMiembro.alumno_id == alumno_id,
                Equipo.instancia_evaluacion_id == instancia_evaluacion_id,
            )
        )
        if excluir_equipo_id is not None:
            stmt = stmt.where(Equipo.id != excluir_equipo_id)

        otro = session.exec(stmt).first()
        if otro:
            equipo = session.get(Equipo, otro.equipo_id)
            nombre = equipo.nombre if equipo else otro.equipo_id
            raise ValueError(
                f"El alumno {alumno_id} ya integra el equipo '{nombre}' en esta "
                f"misma evaluacion"
            )

    def create_equipo(
        self,
        instancia_evaluacion_id: int,
        nombre: str,
        miembros_ids: list[int],
        session: Session,
    ) -> Equipo:
        """Crea un equipo para una instancia de evaluación grupal"""
        # Validar que la instancia existe y es grupal
        instancia = session.exec(
            select(MateriaInstanciaEvaluacion).where(
                MateriaInstanciaEvaluacion.id == instancia_evaluacion_id
            )
        ).first()
        if not instancia:
            raise ValueError(f"Instancia {instancia_evaluacion_id} no encontrada")
        if not instancia.es_grupal:
            raise ValueError("La instancia no es de tipo grupal")

        # Los integrantes se validan ANTES de crear nada, para no dejar un equipo
        # a medio armar si uno de los ids no sirve.
        if len(set(miembros_ids)) != len(miembros_ids):
            raise ValueError("Hay alumnos repetidos en la lista de integrantes")
        for alumno_id in miembros_ids:
            self._validar_alumno_cursa(alumno_id, instancia, session)
            self._validar_no_esta_en_otro_equipo(
                alumno_id, instancia_evaluacion_id, session
            )

        equipo = Equipo(
            instancia_evaluacion_id=instancia_evaluacion_id,
            nombre=nombre,
        )
        session.add(equipo)
        session.commit()
        session.refresh(equipo)

        for alumno_id in miembros_ids:
            session.add(EquipoMiembro(equipo_id=equipo.id, alumno_id=alumno_id))
        session.commit()
        session.refresh(equipo)

        return equipo

    def get_equipos_instancia(
        self, instancia_id: int, session: Session
    ) -> list:
        """Retorna equipos con miembros para una instancia"""
        from v2.models.usuario import Usuario
        from v2.models.alumno import Alumno

        equipos = session.exec(
            select(Equipo).where(Equipo.instancia_evaluacion_id == instancia_id)
        ).all()

        resultado = []
        for eq in equipos:
            miembros_db = session.exec(
                select(EquipoMiembro).where(EquipoMiembro.equipo_id == eq.id)
            ).all()

            miembros = []
            for m in miembros_db:
                # El nombre vive en Usuario (la persona), no en el perfil de alumno
                usuario = session.exec(
                    select(Usuario)
                    .join(Alumno, Alumno.usuario_id == Usuario.id)
                    .where(Alumno.id == m.alumno_id)
                ).first()
                miembros.append({
                    "id": m.id,
                    "equipo_id": m.equipo_id,
                    "alumno_id": m.alumno_id,
                    "nombre": usuario.nombre if usuario else "",
                    "apellido": usuario.apellido if usuario else "",
                })

            resultado.append({
                "id": eq.id,
                "instancia_evaluacion_id": eq.instancia_evaluacion_id,
                "nombre": eq.nombre,
                "miembros": miembros,
            })

        return resultado

    def add_miembro(
        self, equipo_id: int, alumno_id: int, session: Session
    ) -> EquipoMiembro:
        """Agrega un miembro al equipo"""
        equipo = session.exec(
            select(Equipo).where(Equipo.id == equipo_id)
        ).first()
        if not equipo:
            raise ValueError(f"Equipo {equipo_id} no encontrado")

        # Verificar duplicado
        existente = session.exec(
            select(EquipoMiembro).where(
                EquipoMiembro.equipo_id == equipo_id,
                EquipoMiembro.alumno_id == alumno_id,
            )
        ).first()
        if existente:
            raise ValueError("El alumno ya es miembro de este equipo")

        instancia = session.get(
            MateriaInstanciaEvaluacion, equipo.instancia_evaluacion_id
        )
        if instancia:
            self._validar_alumno_cursa(alumno_id, instancia, session)
        self._validar_no_esta_en_otro_equipo(
            alumno_id, equipo.instancia_evaluacion_id, session,
            excluir_equipo_id=equipo_id,
        )

        miembro = EquipoMiembro(equipo_id=equipo_id, alumno_id=alumno_id)
        session.add(miembro)
        session.commit()
        session.refresh(miembro)
        return miembro

    def remove_miembro(
        self, equipo_id: int, alumno_id: int, session: Session
    ):
        """Remueve un miembro del equipo"""
        miembro = session.exec(
            select(EquipoMiembro).where(
                EquipoMiembro.equipo_id == equipo_id,
                EquipoMiembro.alumno_id == alumno_id,
            )
        ).first()
        if not miembro:
            raise ValueError("El alumno no es miembro de este equipo")

        session.delete(miembro)
        session.commit()

    def delete_equipo(self, equipo_id: int, session: Session):
        """Elimina un equipo y sus miembros"""
        equipo = session.exec(
            select(Equipo).where(Equipo.id == equipo_id)
        ).first()
        if not equipo:
            raise ValueError(f"Equipo {equipo_id} no encontrado")

        # Las calificaciones guardan de que equipo salio la nota. Borrar el equipo
        # las dejaba apuntando a la nada: en Postgres es una violacion de foreign
        # key (500) y en SQLite pasaba en silencio.
        from v2.models.calificacion import Calificacion
        calificacion = session.exec(
            select(Calificacion).where(Calificacion.equipo_id == equipo_id)
        ).first()
        if calificacion:
            raise ValueError(
                "No se puede eliminar: el equipo tiene calificaciones registradas"
            )

        # Eliminar miembros primero
        miembros = session.exec(
            select(EquipoMiembro).where(EquipoMiembro.equipo_id == equipo_id)
        ).all()
        for m in miembros:
            session.delete(m)

        session.delete(equipo)
        session.commit()
