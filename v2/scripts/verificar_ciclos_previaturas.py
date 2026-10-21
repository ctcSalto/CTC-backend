"""
Busca ciclos de previaturas ya cargados en la base.

`previatura_service.create` los bloquea al crear, pero esa validacion no existia
siempre y las previaturas tambien se pueden cargar por SQL directo. Un ciclo en
la base cuelga cualquier recorrido de la cadena, asi que conviene correr esto
antes de un despliegue y despues de una carga masiva de datos.

Solo lectura: no modifica nada.

    python -m v2.scripts.verificar_ciclos_previaturas

Sale con codigo 1 si encuentra algun ciclo, para poder encadenarlo en un deploy.
"""
import sys
from typing import Dict, List, Optional

from sqlmodel import Session, select

from database.database import get_db_session
from v2.models.previatura import Previatura
from v2.models.materia import Materia
from v2.models.programa import Programa


def _grafo(session: Session) -> tuple:
    """materia_id -> materias que requiere, mas los nombres y el programa."""
    materias = session.exec(select(Materia)).all()
    previaturas = session.exec(select(Previatura)).all()

    requiere: Dict[int, List[int]] = {}
    for prev in previaturas:
        requiere.setdefault(prev.materia_id, []).append(prev.materia_previa_id)

    nombres = {m.id: m.nombre for m in materias}
    programa_de = {m.id: m.programa_id for m in materias}
    return requiere, nombres, programa_de


def _buscar_ciclo_desde(
    inicio: int, requiere: Dict[int, List[int]], visitados: set
) -> Optional[List[int]]:
    """
    DFS iterativo. Devuelve el ciclo si lo encuentra saliendo de `inicio`.

    `en_camino` son los nodos de la rama actual: volver a pisar uno de esos es
    un ciclo. `visitados` es global entre llamadas, para no recorrer dos veces
    la misma parte del grafo.
    """
    pila = [(inicio, [inicio])]
    while pila:
        actual, camino = pila.pop()
        for siguiente in requiere.get(actual, []):
            if siguiente in camino:
                # Recorta el prefijo: el ciclo empieza donde se repite
                return camino[camino.index(siguiente):] + [siguiente]
            if siguiente not in visitados:
                pila.append((siguiente, camino + [siguiente]))
        visitados.add(actual)
    return None


def buscar_ciclos(session: Session) -> List[List[int]]:
    requiere, _, _ = _grafo(session)
    visitados: set = set()
    ciclos = []
    for materia_id in list(requiere.keys()):
        if materia_id in visitados:
            continue
        ciclo = _buscar_ciclo_desde(materia_id, requiere, visitados)
        if ciclo:
            ciclos.append(ciclo)
    return ciclos


def main() -> int:
    with get_db_session() as session:
        requiere, nombres, programa_de = _grafo(session)
        programas = {p.id: p.nombre for p in session.exec(select(Programa)).all()}

        total_arcos = sum(len(v) for v in requiere.values())
        print(f"Previaturas cargadas: {total_arcos}")
        print(f"Materias con previaturas: {len(requiere)}")

        ciclos = buscar_ciclos(session)

        if not ciclos:
            print("\nOK: no hay ciclos de previaturas.")
            return 0

        print(f"\nATENCION: {len(ciclos)} ciclo(s) encontrado(s).")
        print("Cada flecha se lee 'requiere'. Hay que borrar un arco de cada uno.\n")
        for ciclo in ciclos:
            programa_id = programa_de.get(ciclo[0])
            programa = programas.get(programa_id, f"programa {programa_id}")
            camino = " -> ".join(
                f"{nombres.get(mid, '?')} ({mid})" for mid in ciclo
            )
            print(f"  [{programa}] {camino}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
