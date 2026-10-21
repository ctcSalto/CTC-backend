from typing import Optional, List
from sqlmodel import Session, select, col

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

        # Validar que no cree un ciclo, directo (A requiere B y B requiere A) ni
        # indirecto (A requiere B, B requiere C, C requiere A)
        camino = self._camino_de_ciclo(
            data.materia_id, data.materia_previa_id, materia.programa_id, session
        )
        if camino:
            raise ValueError(
                "No se puede crear: generaria un ciclo de previaturas "
                f"({self._describir_ciclo(materia, camino, session)})"
            )

        previatura = Previatura(**data.model_dump())
        session.add(previatura)
        session.commit()
        session.refresh(previatura)
        return previatura

    @staticmethod
    def _camino_de_ciclo(
        materia_id: int, materia_previa_id: int, programa_id: int, session: Session
    ) -> Optional[List[int]]:
        """
        Si agregar "materia_id requiere materia_previa_id" cerrara un ciclo,
        devuelve el camino que lo cierra; si no, None.

        Un ciclo se cierra cuando la materia previa ya depende, directa o
        indirectamente, de la materia que la va a requerir. Asi que se arranca
        en la materia previa y se sigue lo que ella misma requiere: si por ahi
        se llega a materia_id, el arco nuevo cierra el circulo.

        El grafo del programa se carga entero de una sola vez y se recorre en
        memoria. Antes solo se miraba el arco inverso, asi que A->B->C->A
        entraba sin problema y despues colgaba a quien recorriera la cadena.

        `vistos` no es solo una optimizacion: si la base ya tiene un ciclo
        cargado de antes, sin eso este recorrido no terminaria.
        """
        arcos = session.exec(
            select(Previatura.materia_id, Previatura.materia_previa_id)
            .join(Materia, Previatura.materia_id == Materia.id)
            .where(Materia.programa_id == programa_id)
        ).all()

        requiere: dict = {}
        for origen, destino in arcos:
            requiere.setdefault(origen, []).append(destino)

        pila = [(materia_previa_id, [materia_previa_id])]
        vistos = set()
        while pila:
            actual, camino = pila.pop()
            if actual == materia_id:
                return camino
            if actual in vistos:
                continue
            vistos.add(actual)
            for siguiente in requiere.get(actual, []):
                pila.append((siguiente, camino + [siguiente]))

        return None

    @staticmethod
    def _describir_ciclo(materia: Materia, camino: List[int], session: Session) -> str:
        """
        El ciclo en palabras, para que bedelia sepa que arco sacar.

        Sin esto el error dice que hay un ciclo pero no cual, y en una malla de
        treinta materias encontrarlo a mano es un problema.
        """
        nombres = {
            mid: nombre for mid, nombre in session.exec(
                select(Materia.id, Materia.nombre).where(col(Materia.id).in_(camino))
            ).all()
        }
        secuencia = [materia.nombre] + [
            nombres.get(mid, f"Materia {mid}") for mid in camino
        ]
        return " requiere ".join(secuencia)

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
