"""
Importa la planilla de escolaridades de bedelia ("Escolaridades ver 2023.xlsm")
a las tablas historico_plan / historico_alumno / historico_resultado.

Uso:
    python -m v2.scripts.importar_historico <archivo.xlsx|.xlsm> [--dry-run] [--reemplazar]

  --dry-run      lee, normaliza e informa, pero no escribe nada
  --reemplazar   borra lo que haya en las tres tablas antes de cargar. Sin esta
                 opcion, si ya hay datos el script se niega a correr.

El archivo original esta cifrado con contraseña: hay que guardarlo sin
contraseña antes (Archivo > Informacion > Proteger libro > Cifrar > borrar).
Las macros no se usan, solo las hojas ALUMNOS y RESULTADOS.

Lo que hace con la planilla, hoja por hoja:

RESULTADOS (la que importa)
  - Cada fila es una evaluacion. Se toman las 17 columnas con datos; las
    otras 80 estan vacias.
  - ~470 filas tienen solo la columna OP (restos de carga): se saltean.
  - ~30% de las filas son duplicados exactos (mismos 17 valores). Se cargan
    una sola vez y se informa cuantas se descartaron.
  - Cinco fechas vienen como texto mal tipeado ('31/07//2024'). Las que se
    pueden interpretar se interpretan; la que no ('31/11/2024') queda con
    fecha null y el texto original en fecha_texto.
  - Los codigos de plan tienen variantes ('AP2011' y 'AP 2011'): se unifican
    con ALIAS_PLAN. Las materias se normalizan a mayusculas sin espacios
    dobles, pero NO se corrigen tipeos ('INDESING CTC' queda asi).
  - Valores basura en RESULT. ('#REF!', 0) quedan como null.

ALUMNOS (datos de contacto)
  - Es la tabla de clientes del sistema administrativo viejo: hay empresas,
    proveedores y cuentas contables mezclados con los alumnos. Se importan
    solo las filas cuya clave parece una cedula (6 a 8 digitos).
  - Hay cedulas repetidas: se queda la fila con mas datos.
  - ~100 filas (2351 a 2449) estan desplazadas: el nombre y la cedula son
    correctos pero el resto de las columnas pertenece a otra persona. De esas
    se toma solo cedula y nombre.
  - NO se importan cl_observ (notas de cobranza en RTF), cl_ruc ni cl_cpostal.
  - Quien aparece en RESULTADOS y no en ALUMNOS se crea con el nombre que
    figura en el acta.

El catalogo de planes (carrera y creditos) sale de la hoja ESCOLARIDAD, y para
los cursos cortos que no estaban ahi se dedujo de las materias que contienen.
Esta fijo en CATALOGO_PLANES, no se lee de la planilla.
"""
import argparse
import re
import sys
import warnings
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Tuple

from sqlmodel import Session, select, func

from v2.models.historico import HistoricoAlumno, HistoricoPlan, HistoricoResultado
from v2.services.historico_service import solo_digitos, texto_busqueda


# ── Catalogo de planes ───────────────────────────────────────────────────────

# codigo -> (carrera, creditos requeridos). Los creditos son los de la hoja
# ESCOLARIDAD (la que usaba la formula del certificado); donde diferia de la
# hoja Validaciones se tomo ESCOLARIDAD.
#
# La carrera tiene que ser EXACTAMENTE igual entre planes de la misma carrera:
# el legajo promedia por carrera (criterio de bedelia, 22/09/2026). Los planes
# nocturnos (TA ... N) son la misma carrera en otro turno, no otra carrera.
CATALOGO_PLANES: Dict[str, Tuple[Optional[str], Optional[int]]] = {
    "AP 95": ("Analista Programador", 23),
    "AP 2000": ("Analista Programador", 20),
    "AP 2002": ("Analista Programador", 20),
    "AP 2004": ("Analista Programador", 17),
    "AP 2007": ("Analista Programador", 17),
    "AP 2011": ("Analista Programador", 15),
    "AP 2020": ("Analista Programador", 15),
    "AP 2022": ("Analista Programador", 15),
    "TA 1996": ("Tecnico en Gerencia", 17),
    "TA 2001": ("Tecnico en Gerencia", 19),
    "TA 2001 N": ("Tecnico en Gerencia", 18),
    "TA 2011": ("Tecnico en Gerencia", None),
    "TA 2016": ("Tecnico en Gerencia", 18),
    "TA 2016 N": ("Tecnico en Gerencia", 15),
    "TA 2017": ("Tecnico en Gerencia", None),
    "TEI": ("Tecnico en Electronica Informatica", None),
    "TEI 2000": ("Tecnico en Electronica Informatica", 18),
    "TEI 2002": ("Tecnico en Electronica Informatica", 16),
    "TEI 2004": ("Tecnico en Electronica Informatica", 16),
    "TEI 2006": ("Tecnico en Electronica Informatica", 17),
    "SJ 2001": ("Secretariado Ejecutivo", 16),
    "XP": ("Analista en Publicidad", None),
    "XP 2001": ("Analista en Publicidad", 14),
    "TSI 2011": ("Tecnico en Soporte Informatico", 17),
    "TGDE 2022": ("Tecnico en Gestion y Direccion de Empresas", 19),
    "TGDE 2025": ("Tecnico en Gestion y Direccion de Empresas", 16),
    "AC": ("Asistente Contable", 1),
    "AC 2016": ("Asistente Contable", None),
    "OPC": ("Operador Contable", None),
    "OP CONT": ("Operador Contable", None),
    "OP DG": ("Operador en Diseño Grafico", 5),
    "OPG": ("Operador en Diseño Grafico", None),
    "OP OFF": ("Operador Office", None),
    # Cursos cortos: la carrera se dedujo de las materias que contiene
    "EXCEL AV": ("Excel Avanzado", None),
    "EX+PBI": ("Excel Avanzado y Power BI", None),
    "MANT": ("Mantenimiento de PC", None),
    "MANT PC": ("Mantenimiento de PC", None),
    "D WEB": ("Diseño Web", None),
    "DG": ("Diseño Grafico, Ploteo Digital y Sublimacion", None),
    "CDAV": ("Corel Draw Avanzado", None),
    "LS": ("Liquidacion de Sueldos", None),
    "LS+GNS": ("Liquidacion de Sueldos + GNS", None),
    "RRHH": ("Gestion de Recursos Humanos", None),
    "MD": ("Marketing Digital", None),
    "ST IT": ("Soporte Tecnico IT", None),
    "CYN": ("Comunicacion y Negociacion", None),
    "AT.C": ("Atencion al Cliente", None),
    "LOG 2016": ("Gestion en Logistica Operacional", None),
    "IA 2024": ("Diploma en Inteligencia Artificial", None),
    "GX": ("Genexus", None),
}

# Variantes que aparecen en la planilla -> codigo canonico
ALIAS_PLAN = {
    "OPDG": "OP DG",
}


def codigo_plan(valor) -> Optional[str]:
    """'ap2011 ' -> 'AP 2011'. Mayusculas, un espacio entre letras y año, alias."""
    texto = normalizar_texto(valor)
    if not texto:
        return None
    texto = re.sub(r"^([A-Z]+)(\d{2,4})$", r"\1 \2", texto)
    return ALIAS_PLAN.get(texto, texto)


# ── Normalizacion de celdas ──────────────────────────────────────────────────

def normalizar_texto(valor, largo: Optional[int] = None) -> Optional[str]:
    """Texto en mayusculas, sin espacios dobles, o None si esta vacio."""
    if valor is None or isinstance(valor, bool):
        return None
    texto = re.sub(r"\s+", " ", str(valor)).strip().upper()
    if not texto:
        return None
    # Ð es la Ñ mal decodificada del sistema viejo (PESTAÐA)
    texto = texto.replace("Ð", "Ñ")
    return texto[:largo] if largo else texto


def texto_tal_cual(valor, largo: Optional[int] = None) -> Optional[str]:
    """Texto recortado, sin cambiar mayusculas (direcciones, emails)."""
    if valor is None or isinstance(valor, bool):
        return None
    texto = re.sub(r"\s+", " ", str(valor)).strip()
    if not texto:
        return None
    return texto[:largo] if largo else texto


def parsear_cedula(valor) -> Optional[str]:
    """Solo digitos; entre 6 y 8. Lo demas (empresas, '#REF!', claves chicas) es None."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, float):
        valor = int(valor)
    digitos = solo_digitos(valor)
    return digitos if 6 <= len(digitos) <= 8 else None


def parsear_entero(valor) -> Optional[int]:
    """Nota o numero. 'REV', 'NSP' y demas textos son None."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return int(valor)
    texto = str(valor).strip()
    return int(texto) if texto.lstrip("-").isdigit() else None


def parsear_fecha(valor) -> Tuple[Optional[date], Optional[str]]:
    """
    (fecha, texto_original_si_no_se_pudo). Los datetime vienen bien; los
    textos son tipeos ('31/07//2024', '14/032025') que se intentan rescatar.
    """
    if valor is None or valor == "":
        return None, None
    if isinstance(valor, datetime):
        return valor.date(), None
    if isinstance(valor, date):
        return valor, None

    texto = str(valor).strip()
    limpio = re.sub(r"/+", "/", texto)
    for formato in ("%d/%m/%Y", "%d/%m%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(limpio, formato).date(), None
        except ValueError:
            continue
    return None, texto[:20]


def codigo_corto(valor, validos: Iterable[str]) -> Optional[str]:
    """Un codigo de la planilla si esta entre los conocidos; si no, None."""
    texto = normalizar_texto(valor)
    return texto if texto in set(validos) else None


TIPOS_VALIDOS = ("CUR", "EXA", "TALLER", "REV", "DIP")
RESULTADOS_VALIDOS = ("APR", "EXO", "ELI", "NSP", "REV", "EXA", "PEND")
CREDITOS_VALIDOS = ("T", "P")


# ── Lectura de las hojas ─────────────────────────────────────────────────────

COLUMNAS_RESULTADOS = {
    "OP": 0, "CARRERA": 1, "MATERIA": 2, "DOCENTE": 3, "FECHA": 4, "CEDULA": 5,
    "ESTUDIANTE": 7, "EVAL": 9, "PUNT": 10, "PPRO": 11, "RESULT.": 12,
    "CRED": 13, "OBS": 14, "Proy": 15, "Zona": 16,
}

COLUMNAS_ALUMNOS = {
    "clave": 0, "cl_nombre": 2, "cl_direc": 4, "cl_local": 5, "cl_telef": 8,
    "cl_fax": 9, "cl_email": 10, "cl_zona": 12, "cl_obs": 13, "cl_depto": 14,
    "Plan": 15, "Plan2": 16,
}


def _verificar_encabezado(fila, esperado: Dict[str, int], hoja: str):
    for nombre, idx in esperado.items():
        real = str(fila[idx]).strip() if idx < len(fila) and fila[idx] is not None else ""
        if real != nombre:
            raise ValueError(
                f"Hoja {hoja}: se esperaba la columna {nombre!r} en la posicion {idx} "
                f"y hay {real!r}. La planilla cambio de formato."
            )


def leer_resultados(ws) -> Tuple[List[dict], Counter]:
    """
    Filas normalizadas de RESULTADOS, sin duplicados exactos, con el numero de
    fila de origen. Devuelve tambien un contador de lo que se descarto.
    """
    filas = ws.iter_rows(values_only=True)
    _verificar_encabezado(next(filas), COLUMNAS_RESULTADOS, "RESULTADOS")
    c = COLUMNAS_RESULTADOS

    salida: List[dict] = []
    vistos = set()
    stats = Counter()

    for numero, fila in enumerate(filas, start=2):
        fila = tuple(fila) + (None,) * (17 - len(fila))
        if not any(v not in (None, "") for v in fila):
            continue
        plan = codigo_plan(fila[c["CARRERA"]])
        materia = normalizar_texto(fila[c["MATERIA"]], 120)
        cedula = parsear_cedula(fila[c["CEDULA"]])
        tipo = codigo_corto(fila[c["EVAL"]], TIPOS_VALIDOS)

        if not plan and not materia and not cedula:
            stats["vacias"] += 1          # solo tienen OP: restos de carga
            continue
        if not plan or not materia or not cedula or not tipo:
            stats["incompletas"] += 1
            continue

        clave = tuple(normalizar_texto(v) if isinstance(v, str) else v for v in fila[:17])
        if clave in vistos:
            stats["duplicadas"] += 1
            continue
        vistos.add(clave)

        fecha, fecha_texto = parsear_fecha(fila[c["FECHA"]])
        if fecha_texto:
            stats["fecha_ilegible"] += 1

        acta = fila[c["OBS"]]
        acta = str(int(acta)) if isinstance(acta, (int, float)) else texto_tal_cual(acta, 20)

        salida.append({
            "fila_origen": numero,
            "plan": plan,
            "cedula": cedula,
            "nombre": normalizar_texto(fila[c["ESTUDIANTE"]], 150),
            "materia": materia,
            "docente": normalizar_texto(fila[c["DOCENTE"]], 120),
            "fecha": fecha,
            "fecha_texto": fecha_texto,
            "tipo_evaluacion": tipo,
            "resultado": codigo_corto(fila[c["RESULT."]], RESULTADOS_VALIDOS),
            "puntaje": parsear_entero(fila[c["PUNT"]]),
            "puntaje_promedio": parsear_entero(fila[c["PPRO"]]),
            "credito": codigo_corto(fila[c["CRED"]], CREDITOS_VALIDOS),
            "acta": acta,
            "proyecto": parsear_entero(fila[c["Proy"]]),
            "observaciones": texto_tal_cual(fila[c["Zona"]], 200),
            "operador": normalizar_texto(fila[c["OP"]], 10),
        })

    stats["cargadas"] = len(salida)
    return salida, stats


def _fila_desplazada(fila) -> bool:
    """Las ~100 filas corridas tienen True donde deberia haber texto."""
    return isinstance(fila[COLUMNAS_ALUMNOS["cl_obs"]], bool)


def _plan_declarado(plan, anio) -> Optional[str]:
    plan = normalizar_texto(plan)
    if not plan or plan == "OTRO PLAN":
        return None
    anio = parsear_entero(anio)
    return f"{plan} {anio}"[:30] if anio and anio > 1900 else plan[:30]


def _zona(valor) -> Optional[str]:
    """Los codigos tipo '05TA'. Los '1' y '2' sueltos no dicen nada."""
    texto = normalizar_texto(valor, 20)
    return texto if texto and re.match(r"^\d\d[A-Z]", texto) else None


def leer_alumnos(ws) -> Tuple[Dict[str, dict], Counter]:
    """Personas de ALUMNOS por cedula. Ante repetidas, la fila con mas datos."""
    filas = ws.iter_rows(values_only=True)
    _verificar_encabezado(next(filas), COLUMNAS_ALUMNOS, "ALUMNOS")
    c = COLUMNAS_ALUMNOS

    por_cedula: Dict[str, dict] = {}
    stats = Counter()

    for numero, fila in enumerate(filas, start=2):
        fila = tuple(fila) + (None,) * (17 - len(fila))
        if not any(v not in (None, "") for v in fila):
            continue
        cedula = parsear_cedula(fila[c["clave"]])
        nombre = normalizar_texto(fila[c["cl_nombre"]], 150)
        if not cedula or not nombre:
            stats["sin_cedula_valida"] += 1
            continue

        if _fila_desplazada(fila):
            stats["desplazadas"] += 1
            datos = {
                "cedula": cedula, "nombre": nombre, "fila_origen": numero,
                "observaciones": "Fila desplazada en la planilla original: solo se tomo cedula y nombre",
            }
        else:
            datos = {
                "cedula": cedula,
                "nombre": nombre,
                "fila_origen": numero,
                "plan_declarado": _plan_declarado(fila[c["Plan"]], fila[c["Plan2"]]),
                "zona": _zona(fila[c["cl_zona"]]),
                "direccion": texto_tal_cual(fila[c["cl_direc"]], 200),
                "localidad": normalizar_texto(fila[c["cl_local"]], 100),
                "departamento": texto_tal_cual(fila[c["cl_depto"]], 10),
                "telefono": texto_tal_cual(fila[c["cl_telef"]], 100),
                "celular": texto_tal_cual(fila[c["cl_fax"]], 100),
                "email": texto_tal_cual(fila[c["cl_email"]], 255),
                "observaciones": texto_tal_cual(fila[c["cl_obs"]], 500),
            }
            if datos["email"] and "@" not in datos["email"]:
                datos["email"] = None   # hay telefonos cargados en la columna de email

        if cedula in por_cedula:
            stats["cedulas_repetidas"] += 1
            if _llenos(datos) <= _llenos(por_cedula[cedula]):
                continue
        por_cedula[cedula] = datos

    stats["personas"] = len(por_cedula)
    return por_cedula, stats


def _llenos(datos: dict) -> int:
    return sum(1 for v in datos.values() if v not in (None, ""))


# ── Carga ────────────────────────────────────────────────────────────────────

def hay_datos(session: Session) -> bool:
    return session.exec(select(func.count(HistoricoResultado.id))).one() > 0 \
        or session.exec(select(func.count(HistoricoAlumno.id))).one() > 0


def vaciar(session: Session):
    for modelo in (HistoricoResultado, HistoricoAlumno, HistoricoPlan):
        for fila in session.exec(select(modelo)).all():
            session.delete(fila)
    session.flush()


def cargar(resultados: List[dict], alumnos: Dict[str, dict], session: Session) -> Counter:
    """Inserta planes, alumnos y resultados. No hace commit: lo decide quien llama."""
    stats = Counter()

    # Planes: los del catalogo que aparecen, mas los que aparezcan sin catalogo
    codigos = sorted({r["plan"] for r in resultados})
    planes: Dict[str, HistoricoPlan] = {}
    for codigo in codigos:
        carrera, creditos = CATALOGO_PLANES.get(codigo, (None, None))
        if codigo not in CATALOGO_PLANES:
            stats["planes_sin_catalogo"] += 1
        planes[codigo] = HistoricoPlan(codigo=codigo, carrera=carrera, creditos_requeridos=creditos)
    session.add_all(planes.values())
    session.flush()
    stats["planes"] = len(planes)

    # Alumnos: los de la hoja ALUMNOS mas los que solo estan en actas
    nombres_en_actas: Dict[str, Counter] = defaultdict(Counter)
    for r in resultados:
        if r["nombre"]:
            nombres_en_actas[r["cedula"]][r["nombre"]] += 1

    personas: Dict[str, HistoricoAlumno] = {}
    for cedula, datos in alumnos.items():
        personas[cedula] = HistoricoAlumno(nombre_busqueda=texto_busqueda(datos["nombre"]), **datos)
    for cedula, nombres in nombres_en_actas.items():
        if cedula not in personas:
            nombre = nombres.most_common(1)[0][0]
            personas[cedula] = HistoricoAlumno(
                cedula=cedula, nombre=nombre, nombre_busqueda=texto_busqueda(nombre),
                observaciones="No figura en la hoja ALUMNOS; nombre tomado del acta",
            )
            stats["alumnos_solo_en_actas"] += 1
    session.add_all(personas.values())
    session.flush()
    stats["alumnos"] = len(personas)
    stats["alumnos_con_resultados"] = len(nombres_en_actas)

    # Resultados
    filas = []
    for r in resultados:
        datos = {k: v for k, v in r.items() if k not in ("plan", "cedula", "nombre")}
        filas.append(HistoricoResultado(
            alumno_id=personas[r["cedula"]].id, plan_id=planes[r["plan"]].id, **datos,
        ))
    session.add_all(filas)
    session.flush()
    stats["resultados"] = len(filas)
    return stats


def importar(ruta: str, session: Session, reemplazar: bool = False, dry_run: bool = False) -> dict:
    """Todo el proceso. Con dry_run no queda nada escrito."""
    from openpyxl import load_workbook

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")   # openpyxl avisa por las validaciones de la planilla
        wb = load_workbook(ruta, read_only=True, data_only=True)
    for hoja in ("RESULTADOS", "ALUMNOS"):
        if hoja not in wb.sheetnames:
            raise ValueError(f"La planilla no tiene la hoja {hoja}. Hojas: {wb.sheetnames}")

    resultados, stats_res = leer_resultados(wb["RESULTADOS"])
    alumnos, stats_alu = leer_alumnos(wb["ALUMNOS"])

    if hay_datos(session):
        if not reemplazar:
            raise ValueError("Ya hay datos en las tablas de historico. Usa --reemplazar para cargar de nuevo.")
        vaciar(session)

    stats_carga = cargar(resultados, alumnos, session)

    if dry_run:
        session.rollback()
    else:
        session.commit()

    return {"resultados": stats_res, "alumnos": stats_alu, "carga": stats_carga}


def _imprimir(informe: dict, dry_run: bool):
    print("\nRESULTADOS")
    r = informe["resultados"]
    print(f"  filas cargadas          {r['cargadas']:>6}")
    print(f"  duplicadas exactas      {r['duplicadas']:>6}  (se cargan una vez)")
    print(f"  vacias (solo OP)        {r['vacias']:>6}")
    print(f"  incompletas             {r['incompletas']:>6}  (sin plan, materia, cedula o tipo)")
    print(f"  fecha ilegible          {r['fecha_ilegible']:>6}  (quedan con fecha_texto)")
    print("\nALUMNOS")
    a = informe["alumnos"]
    print(f"  personas                {a['personas']:>6}")
    print(f"  cedulas repetidas       {a['cedulas_repetidas']:>6}  (se queda la fila con mas datos)")
    print(f"  filas desplazadas       {a['desplazadas']:>6}  (solo cedula y nombre)")
    print(f"  sin cedula valida       {a['sin_cedula_valida']:>6}  (empresas, cuentas, claves chicas)")
    print("\nCARGA")
    c = informe["carga"]
    print(f"  planes                  {c['planes']:>6}  ({c['planes_sin_catalogo']} sin catalogo)")
    print(f"  alumnos                 {c['alumnos']:>6}  ({c['alumnos_con_resultados']} con resultados, "
          f"{c['alumnos_solo_en_actas']} solo en actas)")
    print(f"  resultados              {c['resultados']:>6}")
    print("\n" + ("DRY RUN: no se escribio nada." if dry_run else "Listo."))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("archivo", help="Planilla .xlsx o .xlsm sin contraseña")
    parser.add_argument("--dry-run", action="store_true", help="No escribe nada")
    parser.add_argument("--reemplazar", action="store_true", help="Borra lo que haya antes de cargar")
    args = parser.parse_args()

    from database.database import get_db_session

    with get_db_session() as session:
        try:
            informe = importar(args.archivo, session, reemplazar=args.reemplazar, dry_run=args.dry_run)
        except ValueError as e:
            print(f"\nERROR: {e}")
            sys.exit(1)
    _imprimir(informe, args.dry_run)


if __name__ == "__main__":
    main()
