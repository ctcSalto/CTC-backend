"""
Planes de estudio: cada plan de una carrera es un programa aparte.

Decidido el 25/09/2026. Una carrera como Analista Programador tiene alumnos en
cuatro planes a la vez (2007, 2011, 2020, 2022), cada uno con su malla, sus
creditos y sus previaturas. En vez de agregar el concepto de plan a la base
(un cambio de esquema), cada plan es un Programa con el año en el nombre:

    "Analista Programador (Plan 2020)"
    "Analista Programador (Plan 2022)"

Las carreras con un solo plan (la mayoria de los cursos cortos) no llevan el
sufijo. Lo que es "de la carrera" y no del plan —el promedio de la escolaridad,
que bedelia calcula con todos los planes juntos— se agrupa por el nombre sin el
sufijo: carrera_de().
"""
import math
import re
from typing import Iterable, Optional, Tuple

# "X (Plan 2020)", "X - Plan 2020", "X – plan 2020", "X Plan 2020"
_RE_PLAN = re.compile(r"\s*(?:\(\s*plan\s+(\d{4})\s*\)|[-–]?\s*plan\s+(\d{4}))\s*$", re.IGNORECASE)


def separar_plan(nombre: Optional[str]) -> Tuple[str, Optional[str]]:
    """'Analista Programador (Plan 2020)' -> ('Analista Programador', '2020')."""
    texto = (nombre or "").strip()
    m = _RE_PLAN.search(texto)
    if not m:
        return texto, None
    return texto[:m.start()].strip(), m.group(1) or m.group(2)


def carrera_de(nombre_programa: Optional[str]) -> str:
    """El nombre de la carrera, sin el plan. Es lo que agrupa el promedio."""
    return separar_plan(nombre_programa)[0]


def nombre_programa(carrera: str, plan: Optional[str]) -> str:
    """El nombre del programa de un plan. Sin plan, el de la carrera tal cual."""
    carrera = carrera.strip()
    return f"{carrera} (Plan {plan})" if plan else carrera


def plan_por_defecto(planes: Iterable[str]) -> Optional[str]:
    """
    El plan de un alumno que no lo dice: el mas reciente de la carrera.

    Bedelia (25/09/2026): todos los alumnos de Analista Programador estan en el
    plan 2022, incluso los que empezaron en planes viejos, porque cortaron y
    retomaron con el actual. Los de TGDE, en el mismo plan, el de este año. Si
    alguna vez un alumno esta en un plan viejo, se pone explicito.
    """
    planes = [p for p in planes if p]
    return max(planes) if planes else None


def semestre_del_plan(valor) -> Optional[int]:
    """
    El semestre de una materia en el plan, como entero (materia.semestre).

    Los talleres vienen como 1.5, 2.5...: van entre dos semestres. Se redondea
    para abajo, decidido con bedelia el 25/09/2026: el alumno paga el taller
    junto con el semestre anterior (el 1.5 se paga con el semestre 1). Genexus
    4.5 queda en 4. "NC" (cursos cortos, no corresponde) es None.
    """
    if valor is None:
        return None
    texto = str(valor).strip().replace(",", ".")
    try:
        return math.floor(float(texto))
    except ValueError:
        return None
