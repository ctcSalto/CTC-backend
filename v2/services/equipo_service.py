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

        # Crear equipo
        equipo = Equipo(
            instancia_evaluacion_id=instancia_evaluacion_id,
            nombre=nombre,
        )
        session.add(equipo)
        session.commit()
        session.refresh(equipo)

        # Agregar miembros
        for uid in miembros_ids:
            miembro = EquipoMiembro(equipo_id=equipo.id, usuario_id=uid)
            session.add(miembro)
        session.commit()
        session.refresh(equipo)

        return equipo

    def get_equipos_instancia(
        self, instancia_id: int, session: Session
    ) -> list:
        """Retorna equipos con miembros para una instancia"""
        from v2.models.usuario import Usuario

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
                usuario = session.exec(
                    select(Usuario).where(Usuario.id == m.usuario_id)
                ).first()
                miembros.append({
                    "id": m.id,
                    "equipo_id": m.equipo_id,
                    "usuario_id": m.usuario_id,
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
        self, equipo_id: int, usuario_id: int, session: Session
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
                EquipoMiembro.usuario_id == usuario_id,
            )
        ).first()
        if existente:
            raise ValueError("El usuario ya es miembro de este equipo")

        miembro = EquipoMiembro(equipo_id=equipo_id, usuario_id=usuario_id)
        session.add(miembro)
        session.commit()
        session.refresh(miembro)
        return miembro

    def remove_miembro(
        self, equipo_id: int, usuario_id: int, session: Session
    ):
        """Remueve un miembro del equipo"""
        miembro = session.exec(
            select(EquipoMiembro).where(
                EquipoMiembro.equipo_id == equipo_id,
                EquipoMiembro.usuario_id == usuario_id,
            )
        ).first()
        if not miembro:
            raise ValueError("El usuario no es miembro de este equipo")

        session.delete(miembro)
        session.commit()

    def delete_equipo(self, equipo_id: int, session: Session):
        """Elimina un equipo y sus miembros"""
        equipo = session.exec(
            select(Equipo).where(Equipo.id == equipo_id)
        ).first()
        if not equipo:
            raise ValueError(f"Equipo {equipo_id} no encontrado")

        # Eliminar miembros primero
        miembros = session.exec(
            select(EquipoMiembro).where(EquipoMiembro.equipo_id == equipo_id)
        ).all()
        for m in miembros:
            session.delete(m)

        session.delete(equipo)
        session.commit()
