from typing import Optional, List
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.previatura import Previatura, PreviaturaCreate, PreviaturaConNombres
from v2.models.materia import Materia


class PreviaturaService(BaseServiceWithFilters[Previatura]):
    def __init__(self):
        super().__init__(Previatura)

    def get_by_id(self, previatura_id: int, session: Session) -> Optional[Previatura]:
        return session.exec(
            select(Previatura).where(Previatura.id == previatura_id)
        ).first()

    def create(self, data: PreviaturaCreate, session: Session) -> Previatura:
        # Validar que no sea la misma materia
        if data.materia_id == data.materia_previa_id:
            raise ValueError("Una materia no puede ser previatura de si misma")

        # Validar que ambas materias existan
        materia = session.exec(
            select(Materia).where(Materia.id == data.materia_id)
        ).first()
        if not materia:
            raise ValueError(f"Materia {data.materia_id} no encontrada")

        materia_previa = session.exec(
            select(Materia).where(Materia.id == data.materia_previa_id)
        ).first()
        if not materia_previa:
            raise ValueError(f"Materia previa {data.materia_previa_id} no encontrada")

        # Validar que ambas pertenezcan al mismo programa
        if materia.programa_id != materia_previa.programa_id:
            raise ValueError(
                "Ambas materias deben pertenecer al mismo programa"
            )

        # Validar que no exista la misma previatura
        existente = session.exec(
            select(Previatura).where(
                Previatura.materia_id == data.materia_id,
                Previatura.materia_previa_id == data.materia_previa_id,
            )
        ).first()
        if existente:
            raise ValueError("Esta relacion de previatura ya existe")

        # Validar que no cree un ciclo directo (A requiere B y B requiere A)
        ciclo = session.exec(
            select(Previatura).where(
                Previatura.materia_id == data.materia_previa_id,
                Previatura.materia_previa_id == data.materia_id,
            )
        ).first()
        if ciclo:
            raise ValueError(
                "No se puede crear: generaria un ciclo de previaturas"
            )

        previatura = Previatura(**data.model_dump())
        session.add(previatura)
        session.commit()
        session.refresh(previatura)
        return previatura

    def get_by_materia(
        self, materia_id: int, session: Session
    ) -> List[PreviaturaConNombres]:
        """Obtener previaturas de una materia con los nombres de las materias"""
        previaturas = session.exec(
            select(Previatura).where(Previatura.materia_id == materia_id)
        ).all()

        resultado = []
        for prev in previaturas:
            materia = session.exec(
                select(Materia).where(Materia.id == prev.materia_id)
            ).first()
            materia_previa = session.exec(
                select(Materia).where(Materia.id == prev.materia_previa_id)
            ).first()

            resultado.append(
                PreviaturaConNombres(
                    id=prev.id,
                    materia_id=prev.materia_id,
                    materia_nombre=materia.nombre if materia else "",
                    materia_previa_id=prev.materia_previa_id,
                    materia_previa_nombre=materia_previa.nombre if materia_previa else "",
                    tipo_requerido=prev.tipo_requerido,
                )
            )

        return resultado

    def get_malla_programa(self, programa_id: int, session: Session) -> dict:
        """Malla curricular completa de un programa: materias agrupadas por semestre con sus previaturas"""
        materias = session.exec(
            select(Materia)
            .where(Materia.programa_id == programa_id)
            .order_by(Materia.semestre, Materia.nombre)
        ).all()

        materia_ids = [m.id for m in materias]

        # Obtener todas las previaturas del programa
        previaturas = session.exec(
            select(Previatura).where(Previatura.materia_id.in_(materia_ids))
        ).all()

        # Crear mapa de previaturas por materia
        previaturas_map = {}
        for prev in previaturas:
            if prev.materia_id not in previaturas_map:
                previaturas_map[prev.materia_id] = []
            # Buscar nombre de la materia previa
            materia_previa = next(
                (m for m in materias if m.id == prev.materia_previa_id), None
            )
            previaturas_map[prev.materia_id].append({
                "materia_previa_id": prev.materia_previa_id,
                "materia_previa_nombre": materia_previa.nombre if materia_previa else "",
                "tipo_requerido": prev.tipo_requerido.value,
            })

        # Agrupar por semestre
        semestres = {}
        for materia in materias:
            sem = materia.semestre
            if sem not in semestres:
                semestres[sem] = []
            semestres[sem].append({
                "id": materia.id,
                "nombre": materia.nombre,
                "codigo": materia.codigo,
                "creditos": materia.creditos,
                "activo": materia.activo,
                "previaturas": previaturas_map.get(materia.id, []),
            })

        return {
            "programa_id": programa_id,
            "semestres": semestres,
        }

    def delete(self, previatura_id: int, session: Session) -> None:
        previatura = self.get_by_id(previatura_id, session)
        if not previatura:
            raise ValueError(f"Previatura {previatura_id} no encontrada")

        session.delete(previatura)
        session.commit()
