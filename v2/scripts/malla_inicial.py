"""
La malla de previaturas ya definida, en un solo lugar.

Estos datos venian de `moodle_materias_previaturas.xlsx` y se escribieron en la
migracion `f3g4h5i6j7k8_seed_previaturas`. Esa migracion corrio y **no inserto
nada**: resuelve las materias por nombre exacto y en ese momento la tabla
`materia` estaba vacia, asi que cada busqueda dio None y siguio de largo en
silencio. Alembic no vuelve a correr una revision ya aplicada, con lo cual esos
datos quedaron en el repo sin llegar nunca a la base.

Se sacan aca para que sirvan de fuente unica: los usa la planilla que completa
bedelia (para no pedirle que tipee de nuevo 44 previaturas ya decididas) y el
script que las carga cuando las materias existan.

La comparacion de nombres va sin tildes ni mayusculas a proposito: el seed
buscaba "Programación 1" y en la base figura "Programacion 1". Con igualdad
exacta, de 40 materias mencionadas encontraba 1.
"""
import unicodedata
from typing import Dict, List, Set

# ── Analista Programador ─────────────────────────────────────────────────────

ANALISTA_PROGRAMADOR: Dict[str, List[str]] = {
    "Programación 2": ["Programación 1"],
    "Programación 3": ["Programación 1", "Programación 2"],
    "Algoritmos y Estructura de Datos": ["Programación 2"],
    "Base de Datos 2": ["Base de Datos 1"],
    "Desarrollo para Dispositivos Móviles": ["Programación 1", "Programación 2"],
    "Diseño y Desarrollo de Aplicaciones": [
        "Programación 2", "Programación 3", "Base de Datos 1",
    ],
    "Ingenieria de Software": ["Programación 2", "Base de Datos 1"],
    "Taller Seguridad Informatica": [
        "Taller de Usabilidad y Accesibilidad", "Programación 2",
        "Base de Datos 1", "Pensamiento Computacional",
    ],
    "Taller de Genexus": ["Base de Datos 2", "Programación 3"],
}

# El Integrador requiere TODAS las materias del programa. No se lista una por
# una porque depende de que materias termine teniendo el plan.
INTEGRADOR_MATERIA = "Integrador - Analista programador"

# ── Técnico en Gestión y Dirección de Empresas ───────────────────────────────

TECNICO_GESTION: Dict[str, List[str]] = {
    "Contabilidad y Costos": ["Contabilidad Básica"],
    "Estructuras y Procesos Administrativos": ["Principios de Administración"],
    "Gestión de Recursos Humanos": ["Principios de Administración"],
    "Gestión de Ventas": ["Principios de Marketing"],
    "Liquidación de Sueldos": ["Técnica Tributaria"],
    "Presupuesto Financiero": ["Contabilidad y Costos"],
    "Prácticas de Gestión": [
        "Presupuesto Financiero", "Técnica Tributaria",
        "Gestión de Recursos Humanos",
    ],
    "Taller Cómo crear una Empresa": ["Principios de Marketing"],
    "Taller de Comercio Exterior": ["Prácticas de Gestión"],
    "Taller de Comunicación y Negociación": ["Principios de Marketing"],
    "Taller de Derecho": ["Gestión de Recursos Humanos", "Técnica Tributaria"],
    "Técnica Tributaria": ["Contabilidad y Costos"],
    # Materias nuevas (sin moodle_id todavia)
    "Taller de Informática": ["Fundamentos del Marketing"],
    "Marketing online y de servicios": ["Fundamentos del Marketing"],
    "Taller de contabilidad informatizada": ["Contabilidad y Costos"],
    "Gestión de capital humano": ["Gestión y Administración de Empresas"],
    "Taller de liquidación de sueldos": [
        "Gestión de Recursos Humanos", "Técnica Tributaria",
    ],
    "Gestión de Logística Operacional": ["Operaciones de Servicios"],
    "Práctica de Gestión Integral": [
        "Contabilidad y Costos", "Técnica Tributaria",
        "Gestión de Recursos Humanos",
    ],
    "Derecho Laboral y Comercial": ["Técnica Tributaria"],
}

# Como identificar cada programa en la base. El seed usaba LIKE porque los
# nombres exactos no estaban decididos.
PATRONES_PROGRAMA = {
    "Analista Programador": "%Analista Programador%",
    "Técnico en Gestión y Dirección de Empresas": "%Gesti_n%Direcci_n%Empresas%",
}

MALLAS = {
    "Analista Programador": ANALISTA_PROGRAMADOR,
    "Técnico en Gestión y Dirección de Empresas": TECNICO_GESTION,
}


def normalizar(nombre: str) -> str:
    """Sin tildes, sin mayusculas, sin espacios de mas."""
    sin_acentos = "".join(
        caracter for caracter in unicodedata.normalize("NFD", nombre)
        if unicodedata.category(caracter) != "Mn"
    )
    return " ".join(sin_acentos.lower().split())


def materias_de(malla: Dict[str, List[str]]) -> Set[str]:
    """Todos los nombres que aparecen en una malla, como materia o como previa."""
    nombres = set(malla.keys())
    for previas in malla.values():
        nombres.update(previas)
    return nombres


def materias_por_programa() -> Dict[str, List[str]]:
    """Nombre de programa -> materias que la malla menciona, ordenadas."""
    resultado = {}
    for programa, malla in MALLAS.items():
        nombres = materias_de(malla)
        if programa == "Analista Programador":
            nombres.add(INTEGRADOR_MATERIA)
        resultado[programa] = sorted(nombres)
    return resultado


def previaturas_por_programa() -> Dict[str, List[tuple]]:
    """Nombre de programa -> lista de (materia, materia_previa)."""
    resultado = {}
    for programa, malla in MALLAS.items():
        pares = []
        for materia, previas in malla.items():
            for previa in previas:
                pares.append((materia, previa))
        resultado[programa] = sorted(pares)
    return resultado
