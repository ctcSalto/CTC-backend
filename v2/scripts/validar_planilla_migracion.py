"""
Revisa la planilla que devolvio bedelia, antes de tocar la base.

La planilla se va a completar a mano, y a mano siempre salen cedulas con puntos,
codigos de materia que no existen, alumnos con la materia 5 aprobada y la 1 sin
registrar. Este script encuentra todo eso y lo informa con hoja, fila y columna,
para poder devolverselo a administracion y repetir el ciclo las veces que haga
falta sin haber escrito nada en la base.

    python -m v2.scripts.validar_planilla_migracion carga_inicial.xlsx
    python -m v2.scripts.validar_planilla_migracion carga_inicial.xlsx --reporte errores.txt

ERROR   impide importar la fila.
AVISO   se puede importar, pero probablemente este mal y conviene mirarlo.

Sale con codigo 1 si hay errores. Los avisos no lo hacen fallar.

No lee ni escribe la base: trabaja solo sobre el archivo.
"""
import argparse
import difflib
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from openpyxl import load_workbook

from v2.scripts.generar_planilla_migracion import (
    ESTADOS_CARRERA, ESTADOS_HISTORIAL, ROLES_DOCENTE, SI_NO, TIPOS_PREVIATURA,
)
from v2.scripts.malla_inicial import normalizar

HOJAS = {
    "alumnos": "1-Alumnos",
    "docentes": "2-Docentes",
    "plan": "3-Plan de estudios",
    "previaturas": "4-Previaturas",
    "historial": "5-Historial",
    "dictado": "6-Dictado actual",
}

# Todas las hojas de datos tienen la nota en la fila 1 y el encabezado en la 2
PRIMERA_FILA = 3

ESTADOS_QUE_CUENTAN_COMO_TENIDA = {"APROBADA", "EXONERADA", "REVALIDADA"}

# Formas en que bedelia puede haber escrito un estado a mano. Se aceptan y se
# normalizan; lo demas fuera de la lista sigue siendo error.
ALIAS_ESTADOS_HISTORIAL = {
    "REVALIDA": "REVALIDADA",
    "REVÁLIDA": "REVALIDADA",
}

# Como escribe bedelia "no tiene" (un mail) o "no corresponde" (el semestre o
# los creditos de un curso corto). Visto en la planilla devuelta el 25/09/2026.
VACIOS = {"--", "-", "---", "—"}
NO_CORRESPONDE = {"NC", "N/C", "NO CORRESPONDE"}

RE_DOCUMENTO = re.compile(r"^\d{6,10}$")
RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Problema:
    nivel: str      # ERROR | AVISO
    hoja: str
    fila: Optional[int]
    mensaje: str

    def __str__(self) -> str:
        donde = f"{self.hoja}"
        if self.fila:
            donde += f" fila {self.fila}"
        return f"[{self.nivel}] {donde}: {self.mensaje}"


class Validador:
    def __init__(self, ruta: str):
        self.wb = load_workbook(ruta, data_only=True)
        self.problemas: List[Problema] = []

        # Catalogos que se van armando a medida que se leen las hojas
        # La clave de una materia es su codigo si lo tiene, y si no
        # "PROGRAMA::nombre". `Materia.codigo` es nullable en el modelo y la
        # malla que ya nos pasaron viene sin codigos, asi que exigirlos seria
        # inventar un requisito que el sistema no tiene.
        self.materias: Dict[str, dict] = {}          # clave -> datos
        self.por_codigo: Dict[str, str] = {}         # codigo -> clave
        self.por_nombre: Dict[Tuple[str, str], str] = {}   # (prog, nombre) -> clave
        self.nombres_ambiguos: Dict[str, List[str]] = defaultdict(list)
        self.programas: Set[str] = set()             # los que aparecen en el plan
        self.programas_de_alumno: Dict[str, Set[str]] = defaultdict(set)
        self.documentos_alumnos: Set[str] = set()
        self.documentos_docentes: Set[str] = set()
        # Estan en 1-Alumnos pero su fila tiene un error: el historial no tiene
        # que decir "no esta", sino "arreglar su fila primero".
        self.documentos_con_error: Set[str] = set()
        self.previas_de: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        # Administracion agrego una columna "Plan" en el plan de estudios: una
        # misma carrera trae materias de varios planes (AP 2007, 2011, 2020,
        # 2022). programa -> planes, y (programa, nombre) -> plan elegido.
        self.planes_de_programa: Dict[str, Set[str]] = defaultdict(set)
        self.plan_por_nombre: Dict[Tuple[str, str], str] = {}

    # ── Utilidades ───────────────────────────────────────────────────────────

    def error(self, hoja: str, fila: Optional[int], mensaje: str):
        self.problemas.append(Problema("ERROR", hoja, fila, mensaje))

    def aviso(self, hoja: str, fila: Optional[int], mensaje: str):
        self.problemas.append(Problema("AVISO", hoja, fila, mensaje))

    @staticmethod
    def _texto(valor) -> str:
        if valor is None:
            return ""
        if isinstance(valor, float) and valor.is_integer():
            return str(int(valor))
        texto = str(valor).strip()
        return "" if texto in VACIOS else texto

    @staticmethod
    def _no_corresponde(valor) -> bool:
        """'--' o 'NC': el campo no aplica (por ejemplo, el semestre de un curso corto)."""
        texto = "" if valor is None else str(valor).strip().upper()
        return texto in VACIOS or texto in NO_CORRESPONDE

    def _encabezados(self, clave: str) -> List[str]:
        """
        Los titulos de columna de una hoja, normalizados. Sirve para reconocer
        las columnas que agrego administracion sin depender de la posicion.
        """
        nombre = HOJAS[clave]
        if nombre not in self.wb.sheetnames:
            return []
        fila = next(self.wb[nombre].iter_rows(min_row=PRIMERA_FILA - 1, max_row=PRIMERA_FILA - 1,
                                               values_only=True), ())
        return [normalizar(str(v)) if v is not None else "" for v in fila]

    @staticmethod
    def _sugerir(texto: str, opciones) -> str:
        """' ¿Es 'X'?' si hay un nombre parecido. Para los tipeos de nombres de carrera y materia."""
        por_normalizado = {normalizar(o): o for o in opciones}
        cercanos = difflib.get_close_matches(normalizar(texto), list(por_normalizado), n=1, cutoff=0.75)
        return f" ¿Es '{por_normalizado[cercanos[0]]}'?" if cercanos else ""

    def _documento(self, valor) -> str:
        """Normaliza la cedula: solo digitos. Es la clave que une las hojas."""
        crudo = self._texto(valor)
        return re.sub(r"[.\-\s]", "", crudo)

    def _filas(self, clave: str):
        """Itera las filas con datos de una hoja, salteando las vacias."""
        nombre = HOJAS[clave]
        if nombre not in self.wb.sheetnames:
            self.error(nombre, None, "Falta la hoja. ¿Se borro o se renombro?")
            return
        ws = self.wb[nombre]
        for numero, fila in enumerate(
            ws.iter_rows(min_row=PRIMERA_FILA, values_only=True), start=PRIMERA_FILA
        ):
            if all(celda is None or str(celda).strip() == "" for celda in fila):
                continue
            yield numero, fila

    def _obligatorio(self, hoja: str, fila: int, valor, campo: str) -> bool:
        if not self._texto(valor):
            self.error(hoja, fila, f"Falta {campo}.")
            return False
        return True

    def _entero(self, hoja: str, fila: int, valor, campo: str,
                minimo: int, maximo: int) -> Optional[int]:
        texto = self._texto(valor)
        if not texto:
            return None
        try:
            numero = int(float(texto))
        except ValueError:
            self.error(hoja, fila, f"{campo} tiene que ser un numero: '{texto}'.")
            return None
        if not (minimo <= numero <= maximo):
            self.error(hoja, fila, f"{campo} fuera de rango ({minimo}-{maximo}): {numero}.")
            return None
        return numero

    def _resolver_materia(
        self, valor, programa: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Encuentra la materia venga escrito el codigo o el nombre.

        La hoja de previaturas viene precargada con nombres, porque la malla que
        ya nos pasaron no trae codigos. Aceptar las dos formas evita pedirle a
        bedelia que traduzca 44 filas a mano.

        Devuelve (clave, motivo_del_fallo). Si el nombre existe en dos carreras
        y no se dice cual, es ambiguo y hay que aclararlo.
        """
        texto = self._texto(valor)
        if not texto:
            return None, "esta vacio"

        if texto.upper() in self.por_codigo:
            return self.por_codigo[texto.upper()], None

        normalizado = normalizar(texto)

        if programa:
            clave = self.por_nombre.get((normalizar(programa), normalizado))
            if clave:
                return clave, None

        candidatos = self.nombres_ambiguos.get(normalizado, [])
        if len(candidatos) == 1:
            return candidatos[0], None
        if len(candidatos) > 1:
            carreras = sorted(
                self.materias[c]["programa"] for c in candidatos
            )
            return None, (
                f"existe en mas de una carrera ({', '.join(carreras)}); "
                f"hay que aclarar cual en la columna Programa"
            )

        nombres = [d["nombre"] for d in self.materias.values()
                   if not programa or normalizar(d["programa"]) == normalizar(programa)]
        return None, (f"no esta en la hoja '{HOJAS['plan']}', ni por codigo ni por nombre."
                      f"{self._sugerir(texto, nombres)}").rstrip(".")

    def _opcion(self, hoja: str, fila: int, valor, campo: str,
                opciones: List[str]) -> Optional[str]:
        texto = self._texto(valor).upper()
        if not texto:
            self.error(hoja, fila, f"Falta {campo}.")
            return None
        if texto not in opciones:
            self.error(
                hoja, fila,
                f"{campo} dice '{texto}' y tiene que ser uno de: {', '.join(opciones)}.",
            )
            return None
        return texto

    # ── Hojas ────────────────────────────────────────────────────────────────

    def validar_plan(self):
        hoja = HOJAS["plan"]
        codigos_vistos: Dict[str, int] = {}
        nombres_vistos: Dict[Tuple[str, str], int] = {}
        incompletas: List[Tuple[int, str, str]] = []

        encabezados = self._encabezados("plan")
        col_plan = encabezados.index("plan") if "plan" in encabezados else None

        for fila, datos in self._filas("plan"):
            programa, codigo, nombre, semestre, creditos, dictando, _ = (
                list(datos) + [None] * 7
            )[:7]
            plan = self._texto(datos[col_plan]) if col_plan is not None and col_plan < len(datos) else ""

            programa = self._texto(programa)
            codigo = self._texto(codigo).upper()
            nombre = self._texto(nombre)

            if not programa:
                self.error(hoja, fila, "Falta el programa.")
                continue
            if not nombre:
                self.error(hoja, fila, "Falta el nombre de la materia.")
                continue

            nombre_normalizado = normalizar(nombre)
            clave_nombre = (normalizar(programa), nombre_normalizado)
            # Con la columna Plan, la misma materia puede estar en varios planes
            # de una carrera. Solo es repetida si se repite dentro del mismo plan.
            clave_repetida = (normalizar(programa), plan, nombre_normalizado)
            if clave_repetida in nombres_vistos:
                self.error(
                    hoja, fila,
                    f"'{nombre}' ya aparece en '{programa}'"
                    f"{f' (plan {plan})' if plan else ''} en la fila "
                    f"{nombres_vistos[clave_repetida]}. Dentro de un plan el "
                    f"nombre no se puede repetir.",
                )
                continue
            nombres_vistos[clave_repetida] = fila

            if codigo:
                # Unico dentro del plan: la misma materia repite codigo en cada plan
                clave_codigo = (codigo, plan)
                if clave_codigo in codigos_vistos:
                    self.error(
                        hoja, fila,
                        f"El codigo '{codigo}' ya aparece en la fila "
                        f"{codigos_vistos[clave_codigo]}"
                        f"{f' (plan {plan})' if plan else ''}. Tiene que ser unico.",
                    )
                    continue
                codigos_vistos[clave_codigo] = fila

            # El semestre y los creditos son obligatorios en el modelo; el
            # codigo no. Las filas precargadas desde la malla llegan sin
            # semestre ni creditos y son decenas: se acumulan y se informan
            # juntas, porque ochenta lineas identicas no le sirven a nadie.
            # "NC" y "--" son "no corresponde" (cursos cortos): no faltan.
            # Los semestres ".5" son talleres entre dos semestres (1.5, 2.5).
            faltan = []
            if self._no_corresponde(semestre):
                semestre = None
            elif not self._texto(semestre):
                faltan.append("semestre")
            else:
                self._entero(hoja, fila, semestre, "el semestre del plan", 1, 20)
            if self._no_corresponde(creditos):
                pass
            elif not self._texto(creditos):
                faltan.append("creditos")
            else:
                self._entero(hoja, fila, creditos, "los creditos", 0, 500)
            if faltan:
                incompletas.append((fila, nombre, " y ".join(faltan)))

            self._opcion(hoja, fila, dictando, "si se sigue dictando", SI_NO)

            if codigo and plan:
                clave = f"{codigo}::{plan}"
            elif codigo:
                clave = codigo
            else:
                clave = (f"{programa}::{plan}::{nombre_normalizado}" if plan
                         else f"{programa}::{nombre_normalizado}")
            self.materias[clave] = {
                "programa": programa,
                "nombre": nombre,
                "codigo": codigo,
                "semestre": semestre,
                "plan": plan,
                "fila": fila,
            }
            self.programas.add(programa)
            if plan:
                self.planes_de_programa[programa].add(plan)
            # Por codigo, igual que por nombre: gana el plan mas reciente
            if codigo and (codigo not in self.por_codigo
                           or plan > self.materias[self.por_codigo[codigo]].get("plan", "")):
                self.por_codigo[codigo] = clave

            # Por nombre, dentro de una carrera, gana el plan mas reciente: las
            # otras hojas no dicen de que plan es cada fila. Ver el aviso de abajo.
            anterior = self.por_nombre.get(clave_nombre)
            if anterior is None:
                self.por_nombre[clave_nombre] = clave
                self.plan_por_nombre[clave_nombre] = plan
                self.nombres_ambiguos[nombre_normalizado].append(clave)
            elif plan > self.plan_por_nombre[clave_nombre]:
                self.nombres_ambiguos[nombre_normalizado] = [
                    clave if c == anterior else c for c in self.nombres_ambiguos[nombre_normalizado]
                ]
                self.por_nombre[clave_nombre] = clave
                self.plan_por_nombre[clave_nombre] = plan

        if incompletas:
            detalle = "; ".join(
                f"fila {fila}: '{nombre}' (falta {que})"
                for fila, nombre, que in incompletas[:15]
            )
            if len(incompletas) > 15:
                detalle += f"; y {len(incompletas) - 15} mas"
            self.error(
                hoja, None,
                f"{len(incompletas)} materias sin completar. Son las filas verdes, "
                f"que vienen de la malla ya definida y solo necesitan el semestre "
                f"del plan y los creditos: {detalle}",
            )

        for programa, planes in sorted(self.planes_de_programa.items()):
            if len(planes) > 1:
                self.aviso(
                    hoja, None,
                    f"'{programa}' trae materias de {len(planes)} planes "
                    f"({', '.join(sorted(planes))}). Las otras hojas no dicen de que plan "
                    f"es cada fila, asi que por ahora cada materia se busca por nombre en "
                    f"el plan mas reciente que la tiene. Como se cargan los planes viejos "
                    f"en el portal esta pendiente de definir: no hace falta cambiar nada "
                    f"en la planilla.",
                )

        if not self.materias:
            self.error(hoja, None, "No hay ninguna materia cargada.")

    def _mostrar(self, clave: str) -> str:
        """Como nombrar una materia en un mensaje: codigo si tiene, si no nombre."""
        datos = self.materias.get(clave, {})
        return datos.get("codigo") or datos.get("nombre") or clave

    def validar_previaturas(self):
        hoja = HOJAS["previaturas"]
        vistas: Set[Tuple[str, str]] = set()

        for fila, datos in self._filas("previaturas"):
            programa, entrada, entrada_previa, tipo, _ = (list(datos) + [None] * 5)[:5]

            if not self._texto(entrada) or not self._texto(entrada_previa):
                self.error(hoja, fila, "Falta la materia o la materia previa.")
                continue

            texto_programa = self._texto(programa)
            codigo, falla = self._resolver_materia(entrada, texto_programa)
            if codigo is None:
                self.error(hoja, fila, f"'{self._texto(entrada)}' {falla}.")
            codigo_previa, falla_previa = self._resolver_materia(
                entrada_previa, texto_programa
            )
            if codigo_previa is None:
                self.error(hoja, fila, f"'{self._texto(entrada_previa)}' {falla_previa}.")
            if codigo is None or codigo_previa is None:
                continue

            if codigo == codigo_previa:
                self.error(
                    hoja, fila,
                    f"'{self._mostrar(codigo)}' no puede ser previatura de si misma.",
                )
                continue

            if (self.materias[codigo]["programa"]
                    != self.materias[codigo_previa]["programa"]):
                self.error(
                    hoja, fila,
                    f"'{self._mostrar(codigo)}' y '{self._mostrar(codigo_previa)}' son "
                    f"de programas distintos. Una previatura tiene que ser dentro de "
                    f"la misma carrera.",
                )
                continue

            if (codigo, codigo_previa) in vistas:
                self.aviso(
                    hoja, fila,
                    f"'{self._mostrar(codigo)} requiere "
                    f"{self._mostrar(codigo_previa)}' esta repetido.",
                )
                continue
            vistas.add((codigo, codigo_previa))

            self._opcion(hoja, fila, tipo, "el tipo de previatura", TIPOS_PREVIATURA)
            self.previas_de[codigo].append((codigo_previa, str(fila)))

        self._buscar_ciclos()

    def _buscar_ciclos(self):
        """
        Un ciclo hace que nadie pueda cursar ninguna de esas materias nunca.
        Mejor encontrarlo en la planilla que despues de importar.
        """
        hoja = HOJAS["previaturas"]
        visitados: Set[str] = set()

        for inicio in list(self.previas_de.keys()):
            if inicio in visitados:
                continue
            pila = [(inicio, [inicio])]
            while pila:
                actual, camino = pila.pop()
                for siguiente, _ in self.previas_de.get(actual, []):
                    if siguiente in camino:
                        ciclo = camino[camino.index(siguiente):] + [siguiente]
                        self.error(
                            hoja, None,
                            "Ciclo de previaturas: "
                            + " requiere ".join(self._mostrar(c) for c in ciclo)
                            + ". Hay que sacar uno de esos requisitos.",
                        )
                        pila = []
                        break
                    pila.append((siguiente, camino + [siguiente]))
                visitados.add(actual)

    def validar_alumnos(self):
        hoja = HOJAS["alumnos"]
        documentos_por_fila: Dict[Tuple[str, str], int] = {}
        nombres_por_documento: Dict[str, str] = {}
        sin_documento: List[Tuple[int, str]] = []
        anio_actual = datetime.now().year
        # Administracion agrego "Otro Programa" y su "Estado en la carrera" al
        # final, para los alumnos que estan en dos cursos. Se toman como una
        # inscripcion mas (equivale a repetir la fila con el otro programa).
        encabezados = self._encabezados("alumnos")
        col_otro = next((i for i, e in enumerate(encabezados) if e.startswith("otro programa")), None)
        col_otro_estado = col_otro + 1 if col_otro is not None else None
        segundos_programas = 0

        for fila, datos in self._filas("alumnos"):
            (documento, apellido, nombre, email, _personal, _tel,
             _nacimiento, programa, anio, estado, _obs) = (list(datos) + [None] * 11)[:11]

            documento = self._documento(documento)
            if not documento:
                # Las filas precargadas desde Google llegan sin cedula y son
                # ciento y pico: se cuentan y se informan juntas al final.
                sin_documento.append((fila, self._texto(email) or self._texto(apellido)))
                continue
            if not RE_DOCUMENTO.match(documento):
                self.error(
                    hoja, fila,
                    f"El documento '{documento}' no parece una cedula. "
                    f"Solo numeros, sin puntos ni guiones.",
                )
                continue

            self._obligatorio(hoja, fila, apellido, "el apellido")
            self._obligatorio(hoja, fila, nombre, "el nombre")

            texto_email = self._texto(email)
            if texto_email and not RE_EMAIL.match(texto_email):
                self.error(hoja, fila, f"El email '{texto_email}' esta mal escrito.")

            # Antes de cualquier `continue`: una misma persona escrita distinto en
            # dos filas es casi siempre un typo, y se pierde si se saltea la fila
            nombre_completo = f"{self._texto(apellido)}, {self._texto(nombre)}"
            anterior = nombres_por_documento.get(documento)
            if anterior and anterior.lower() != nombre_completo.lower():
                self.aviso(
                    hoja, fila,
                    f"El documento {documento} figura como '{anterior}' y tambien "
                    f"como '{nombre_completo}'. ¿Es la misma persona?",
                )
            nombres_por_documento[documento] = nombre_completo

            programa = self._texto(programa)
            if not programa:
                self.error(hoja, fila, "Falta el programa.")
                self.documentos_con_error.add(documento)
                continue

            # Contra el plan y no contra la base: asi bedelia puede correr el
            # validador sin acceso a nada. El importador despues chequea que el
            # programa exista de verdad.
            if programa not in self.programas:
                self.error(
                    hoja, fila,
                    f"El programa '{programa}' no aparece en la hoja "
                    f"'{HOJAS['plan']}'.{self._sugerir(programa, self.programas)} Si es "
                    f"una carrera nueva, hay que cargar sus materias ahi primero.",
                )
                self.documentos_con_error.add(documento)
                continue

            clave = (documento, programa)
            if clave in documentos_por_fila:
                self.error(
                    hoja, fila,
                    f"El documento {documento} ya figura en '{programa}' "
                    f"en la fila {documentos_por_fila[clave]}.",
                )
                continue
            documentos_por_fila[clave] = fila

            self._entero(hoja, fila, anio, "el año de ingreso", 1990, anio_actual + 1)
            self._opcion(hoja, fila, estado, "el estado en la carrera", ESTADOS_CARRERA)

            self.documentos_alumnos.add(documento)
            self.programas_de_alumno[documento].add(programa)

            otro = self._texto(datos[col_otro]) if col_otro is not None and col_otro < len(datos) else ""
            if otro:
                if otro not in self.programas:
                    self.error(
                        hoja, fila,
                        f"El otro programa '{otro}' no aparece en la hoja "
                        f"'{HOJAS['plan']}'.{self._sugerir(otro, self.programas)}",
                    )
                elif otro == programa:
                    self.aviso(hoja, fila, f"'Otro Programa' repite el programa principal ('{otro}').")
                else:
                    estado_otro = datos[col_otro_estado] if col_otro_estado < len(datos) else None
                    self._opcion(hoja, fila, estado_otro, "el estado en el otro programa", ESTADOS_CARRERA)
                    self.programas_de_alumno[documento].add(otro)
                    segundos_programas += 1

        if segundos_programas:
            self.aviso(
                hoja, None,
                f"{segundos_programas} alumnos estan en un segundo programa (columna 'Otro "
                f"Programa'). Se toman como una inscripcion mas. Esa columna no trae año "
                f"de ingreso: el importador va a usar el año de la primera materia de ese "
                f"programa en el historial.",
            )

        if sin_documento:
            def marca(quien):
                return " (parece una cuenta de prueba: borrar la fila)" if re.search(
                    r"test|prueba|ejemplo", quien, re.I) else ""
            muestra = "; ".join(
                f"fila {fila}: {quien}{marca(quien)}" for fila, quien in sin_documento[:10]
            )
            if len(sin_documento) > 10:
                muestra += f"; y {len(sin_documento) - 10} mas"
            self.error(
                hoja, None,
                f"{len(sin_documento)} alumnos sin cedula. Es la columna que une "
                f"todas las hojas, asi que sin eso no se puede importar ninguno. "
                f"Suelen ser las filas que trajo el script de Google, que precarga "
                f"nombre y correo pero no tiene la cedula: {muestra}",
            )

        if not self.documentos_alumnos:
            self.error(hoja, None, "No hay ningun alumno cargado.")

    def validar_docentes(self):
        hoja = HOJAS["docentes"]
        vistos: Dict[str, int] = {}

        for fila, datos in self._filas("docentes"):
            documento, apellido, nombre, email, _personal, _tel, activo, _obs = (
                list(datos) + [None] * 8
            )[:8]

            documento = self._documento(documento)
            if not documento:
                self.error(hoja, fila, "Falta el documento.")
                continue
            if not RE_DOCUMENTO.match(documento):
                self.error(hoja, fila, f"El documento '{documento}' no parece una cedula.")
                continue
            if documento in vistos:
                self.error(
                    hoja, fila,
                    f"El documento {documento} ya aparece en la fila {vistos[documento]}.",
                )
                continue
            vistos[documento] = fila

            self._obligatorio(hoja, fila, apellido, "el apellido")
            self._obligatorio(hoja, fila, nombre, "el nombre")

            texto_email = self._texto(email)
            if texto_email and not RE_EMAIL.match(texto_email):
                self.error(hoja, fila, f"El email '{texto_email}' esta mal escrito.")

            self._opcion(hoja, fila, activo, "si sigue activo", SI_NO)
            self.documentos_docentes.add(documento)

    def validar_historial(self):
        hoja = HOJAS["historial"]
        # Bedelia cargo todas las cursadas de cada materia, no solo el estado de
        # hoy (planilla del 25/09/2026): se aceptan varias filas por alumno y
        # materia, y el estado actual es el de la mas reciente (año, y ante
        # empate, la fila de mas abajo). Una fila identica a otra es un aviso.
        vistas: Dict[Tuple[str, str, str, str, str], int] = {}
        mas_reciente: Dict[Tuple[str, str], Tuple[int, int]] = {}
        errores_por_fila_de_alumno: Dict[str, int] = defaultdict(int)
        anio_actual = datetime.now().year
        # documento -> {codigo: estado}, para el chequeo de cadenas
        estados: Dict[str, Dict[str, str]] = defaultdict(dict)

        for fila, datos in self._filas("historial"):
            documento, programa, codigo, estado, nota, anio, semestre, _obs = (
                list(datos) + [None] * 8
            )[:8]

            documento = self._documento(documento)

            if not documento or not self._texto(codigo):
                self.error(hoja, fila, "Faltan el documento o la materia.")
                continue

            if documento not in self.documentos_alumnos:
                if documento in self.documentos_con_error:
                    errores_por_fila_de_alumno[documento] += 1
                else:
                    self.error(
                        hoja, fila,
                        f"El documento {documento} no esta en la hoja '{HOJAS['alumnos']}'. "
                        f"Todo alumno del historial tiene que estar cargado ahi primero.",
                    )
                continue

            resuelto, falla = self._resolver_materia(codigo, self._texto(programa))
            if resuelto is None:
                self.error(hoja, fila, f"'{self._texto(codigo)}' {falla}.")
                continue
            codigo = resuelto

            clave_fila = (documento, codigo, self._texto(anio), self._texto(semestre),
                          self._texto(estado).upper())
            if clave_fila in vistas:
                self.aviso(
                    hoja, fila,
                    f"Repite la fila {vistas[clave_fila]} ({documento}, "
                    f"'{self._mostrar(codigo)}', mismo año y estado). ¿Esta dos veces?",
                )
                continue
            vistas[clave_fila] = fila

            # La materia tiene que ser de una carrera en la que el alumno este
            programa_materia = self.materias[codigo]["programa"]
            if programa_materia not in self.programas_de_alumno[documento]:
                self.error(
                    hoja, fila,
                    f"'{self._mostrar(codigo)}' es de '{programa_materia}', pero "
                    f"{documento} no figura inscripto en esa carrera.",
                )
                continue

            texto_programa = self._texto(programa)
            if texto_programa and texto_programa != programa_materia:
                self.aviso(
                    hoja, fila,
                    f"Dice '{texto_programa}' pero '{self._mostrar(codigo)}' es de "
                    f"'{programa_materia}'. Se toma el de la materia.",
                )

            texto_estado = self._texto(estado).upper()
            estado = ALIAS_ESTADOS_HISTORIAL.get(texto_estado, estado)
            valor_estado = self._opcion(hoja, fila, estado, "el estado", ESTADOS_HISTORIAL)
            if valor_estado is None:
                continue
            try:
                orden = (int(float(self._texto(anio))) if self._texto(anio) else 0, fila)
            except ValueError:
                orden = (0, fila)
            if orden >= mas_reciente.get((documento, codigo), (-1, -1)):
                mas_reciente[(documento, codigo)] = orden
                estados[documento][codigo] = valor_estado

            if self._texto(nota):
                texto_nota = self._texto(nota).replace(",", ".")
                try:
                    numero = float(texto_nota)
                    if not (0 <= numero <= 100):
                        self.error(hoja, fila, f"La nota {numero} esta fuera de 0 a 100.")
                except ValueError:
                    self.error(hoja, fila, f"La nota '{texto_nota}' no es un numero.")

            if self._texto(anio):
                self._entero(hoja, fila, anio, "el año", 1990, anio_actual + 1)
            elif valor_estado in ESTADOS_QUE_CUENTAN_COMO_TENIDA:
                self.aviso(
                    hoja, fila,
                    "Materia aprobada sin año. Se puede importar, pero la "
                    "escolaridad va a salir sin fecha.",
                )

            # Bedelia puso el semestre del plan (1 a 6, y 1.5, 2.5... para los
            # talleres), no el del año. Es informativo: se acepta cualquiera.
            if self._texto(semestre):
                self._entero(hoja, fila, semestre, "el semestre", 1, 20)

        # Un solo error por alumno cuya fila en 1-Alumnos esta mal, en vez de uno
        # por cada materia suya: se arregla en un lugar y se van todos.
        for documento, cantidad in sorted(errores_por_fila_de_alumno.items()):
            self.error(
                hoja, None,
                f"{documento} tiene {cantidad} filas en el historial que no se pueden "
                f"revisar porque su fila en '{HOJAS['alumnos']}' tiene un error (ver "
                f"arriba). Arreglando esa fila se revisan solas.",
            )

        self._revisar_cadenas(estados)

    def _revisar_cadenas(self, estados: Dict[str, Dict[str, str]]):
        """
        El chequeo que mas dolores de cabeza ahorra.

        Si un alumno tiene una materia aprobada pero su previatura no figura,
        el portal lo va a bloquear el dia uno para inscribirse a lo que sigue, y
        bedelia va a reportar que el sistema esta roto. Casi siempre es que el
        historial viejo quedo incompleto, no un error real del alumno.

        Va como AVISO y no como ERROR porque tambien puede ser legitimo: una
        equivalencia, un cambio de plan, o una excepcion que despues se carga a
        mano. Pero hay que mirarlo caso por caso antes de importar.
        """
        hoja = HOJAS["historial"]
        for documento, materias_alumno in sorted(estados.items()):
            for codigo, estado in sorted(materias_alumno.items()):
                if estado not in ESTADOS_QUE_CUENTAN_COMO_TENIDA:
                    continue
                for previa, _ in self.previas_de.get(codigo, []):
                    estado_previa = materias_alumno.get(previa)
                    if estado_previa in ESTADOS_QUE_CUENTAN_COMO_TENIDA:
                        continue
                    detalle = (
                        f"figura como {estado_previa}" if estado_previa
                        else "no figura en el historial"
                    )
                    self.aviso(
                        hoja, None,
                        f"{documento}: tiene '{self._mostrar(codigo)}' {estado} pero "
                        f"su previatura '{self._mostrar(previa)}' {detalle}. Revisar: "
                        f"si es historial viejo que falta, agregarlo; si el alumno la "
                        f"debe de verdad, va a necesitar una excepcion de previatura.",
                    )

    def validar_dictado(self):
        hoja = HOJAS["dictado"]
        anio_actual = datetime.now().year
        vistos: Set[Tuple[str, int, int, str]] = set()

        # Administracion agrego un segundo docente (documento y rol) despues del
        # primero, para las materias con dos docentes: corre el resto de las
        # columnas dos lugares. Se reconoce por el titulo repetido "Rol".
        encabezados = self._encabezados("dictado")
        dos_docentes = sum(1 for e in encabezados if e.startswith("rol")) >= 2
        fuera_de_rango = 0

        for fila, datos in self._filas("dictado"):
            datos = list(datos) + [None] * 12
            if dos_docentes:
                (programa, codigo, anio, semestre, documento, rol, documento_2, rol_2,
                 _horario, _salon, cupo, _obs) = datos[:12]
            else:
                (programa, codigo, anio, semestre, documento, rol,
                 _horario, _salon, cupo, _obs) = datos[:10]
                documento_2 = rol_2 = None

            documento = self._documento(documento)
            documento_2 = self._documento(documento_2)

            if not self._texto(codigo):
                self.error(hoja, fila, "Falta la materia.")
                continue
            resuelto, falla = self._resolver_materia(codigo, self._texto(programa))
            if resuelto is None:
                self.error(hoja, fila, f"'{self._texto(codigo)}' {falla}.")
                continue
            codigo = resuelto

            for doc, rol_doc, cual in ((documento, rol, "el docente"), (documento_2, rol_2, "el segundo docente")):
                if doc and doc not in self.documentos_docentes:
                    self.error(
                        hoja, fila,
                        f"El documento {doc} ({cual}) no esta en la hoja "
                        f"'{HOJAS['docentes']}'.",
                    )
                if doc:
                    self._opcion(hoja, fila, rol_doc, f"el rol de {cual}", ROLES_DOCENTE)
            if not documento:
                # Una materia que se dicta sin docente asignado todavia no impide
                # importarla: el docente se asigna despues desde el portal.
                self.aviso(hoja, fila, "Sin docente asignado. Se puede asignar despues desde el portal.")

            valor_anio = self._entero(hoja, fila, anio, "el año", 1990, anio_actual + 2)
            valor_semestre = self._entero(hoja, fila, semestre, "el semestre", 1, 20)
            if (valor_semestre and valor_semestre > 2) or (valor_anio and valor_anio < anio_actual):
                fuera_de_rango += 1

            if self._texto(cupo):
                self._entero(hoja, fila, cupo, "el cupo maximo", 1, 500)

            if valor_anio and valor_semestre and documento:
                clave = (codigo, valor_anio, valor_semestre, documento)
                if clave in vistos:
                    self.aviso(
                        hoja, fila,
                        f"{documento} ya figura en '{self._mostrar(codigo)}' "
                        f"{valor_anio}/S{valor_semestre}.",
                    )
                vistos.add(clave)

        if fuera_de_rango:
            self.aviso(
                hoja, None,
                f"{fuera_de_rango} filas tienen un semestre mayor a 2 o un año anterior a "
                f"{anio_actual}. Parece que el año y el semestre son los del plan, no el año "
                f"lectivo y el semestre en que se dicta. Esta hoja es para lo que se dicta "
                f"ahora ({anio_actual}): confirmar con bedelia que quiso poner.",
            )

    # ── Ejecucion ────────────────────────────────────────────────────────────

    def correr(self) -> List[Problema]:
        # El orden importa: cada hoja arma los catalogos que usa la siguiente
        self.validar_plan()
        self.validar_previaturas()
        self.validar_alumnos()
        self.validar_docentes()
        self.validar_historial()
        self.validar_dictado()
        return self.problemas


def _resumen(validador: Validador) -> List[str]:
    return [
        "Resumen de lo leido:",
        f"  Materias en el plan      {len(validador.materias)}",
        f"  Previaturas              {sum(len(v) for v in validador.previas_de.values())}",
        f"  Alumnos                  {len(validador.documentos_alumnos)}",
        f"  Docentes                 {len(validador.documentos_docentes)}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo", help="Planilla .xlsx devuelta por bedelia")
    parser.add_argument("--reporte", help="Guarda el detalle en un .txt para reenviar")
    args = parser.parse_args()

    # En Windows, redirigir la salida a un archivo la deja en cp1252 y los
    # acentos salen como '?'. Visto con la planilla del 25/09/2026.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    validador = Validador(args.archivo)
    problemas = validador.correr()

    errores = [p for p in problemas if p.nivel == "ERROR"]
    avisos = [p for p in problemas if p.nivel == "AVISO"]

    lineas = _resumen(validador) + [""]

    if errores:
        lineas.append(f"ERRORES ({len(errores)}) - hay que corregirlos para importar:")
        lineas += [f"  {p}" for p in errores]
        lineas.append("")
    if avisos:
        lineas.append(f"AVISOS ({len(avisos)}) - revisar, no bloquean:")
        lineas += [f"  {p}" for p in avisos]
        lineas.append("")

    if not errores and not avisos:
        lineas.append("Todo bien. La planilla esta lista para importar.")
    elif not errores:
        lineas.append("Sin errores. Mirá los avisos y despues se puede importar.")

    texto = "\n".join(lineas)
    print(texto)

    if args.reporte:
        with open(args.reporte, "w", encoding="utf-8") as archivo:
            archivo.write(texto + "\n")
        print(f"\nReporte guardado en {args.reporte}")

    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
