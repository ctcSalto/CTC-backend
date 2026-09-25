"""
Importa al portal la planilla de carga inicial que completo bedelia.

    python -m v2.scripts.importar_planilla_migracion planilla.xlsx              # simula
    python -m v2.scripts.importar_planilla_migracion planilla.xlsx --confirmar  # escribe

Sin --confirmar hace todo dentro de una transaccion y al final la deshace: sirve
para ver que va a crear sin tocar nada.

Primero corre el validador (validar_planilla_migracion): con un solo ERROR no
importa nada, y lo que importa son las filas que el validador ya resolvio. Todo
va en una sola transaccion: o entra la planilla entera o no entra nada.

Se puede correr mas de una vez: antes de crear busca lo que ya existe (programa
por nombre, materia por codigo, persona por cedula o email, inscripciones por
alumno y programa o por alumno y cursada), asi que una segunda corrida no
duplica. No borra nada ni toca Moodle, Google ni los mails.

Lee de una vez lo que ya hay en la base y resuelve todo en memoria: contra la
base de develop cada consulta tarda ~230 ms, y una consulta por fila eran mas de
diez minutos.

Decisiones (docs/MIGRACION_DATOS.md):
- Cada plan de una carrera es un programa aparte: "Analista Programador (Plan
  2022)". El programa que ya existia sin plan pasa a ser el del plan vigente.
- materia.codigo es unico en toda la base: el plan vigente conserva el codigo
  de la planilla y los viejos llevan el año ("PROG1-2020").
- Semestres .5 para abajo (planes.semestre_del_plan). Los cursos ("NC") van en
  el semestre 1 y sin creditos (0): la columna es obligatoria en el modelo.
- Cada fila del historial es una inscripcion en la cursada de esa materia y ese
  año. Sin fecha_cierre: el promedio de la escolaridad cuenta una cursada del
  portal solo si el portal la cerro, y lo anterior ya esta en el legajo.
- Las que estan CURSANDO quedan con la politica copiada, para que el docente
  les ponga la nota desde el portal (nota final directa).
- La hoja 6 es la asignacion docente por materia del plan vigente: el docente
  se asigna a las cursadas de este año que salen del historial.
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlmodel import Session, select, text

from v2.models.alumno import Alumno
from v2.models.docente_materia import DocenteMateria
from v2.models.enums import (
    AreaPrograma, EstadoInscripcionMateria, EstadoInscripcionPrograma,
    EstadoInstanciaCursado, RolDocente, RolUsuario, TipoPreviatura, TipoPrograma,
)
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.materia import Materia
from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
from v2.models.politica_calificacion import PoliticaCalificacion
from v2.models.politica_examen import PoliticaExamen
from v2.models.previatura import Previatura
from v2.models.profesor import Profesor
from v2.models.programa import Programa
from v2.models.usuario import Usuario
from v2.scripts.malla_inicial import normalizar
from v2.scripts.validar_planilla_migracion import Validador
from v2.services.planes import nombre_programa, semestre_del_plan

TZ = ZoneInfo("America/Montevideo")

ESTADO_MATERIA = {
    "APROBADA": EstadoInscripcionMateria.APROBADO,
    "EXONERADA": EstadoInscripcionMateria.EXONERADO,
    "A_EXAMEN": EstadoInscripcionMateria.A_EXAMEN,
    "CURSANDO": EstadoInscripcionMateria.CURSANDO,
    "RECURSA": EstadoInscripcionMateria.REPROBADO,
    "REVALIDADA": EstadoInscripcionMateria.REVALIDADA,
}
QUE_DAN_CREDITOS = {
    EstadoInscripcionMateria.APROBADO, EstadoInscripcionMateria.EXONERADO,
    EstadoInscripcionMateria.REVALIDADA,
}
CON_NOTA_DE_CURSO = {
    EstadoInscripcionMateria.EXONERADO, EstadoInscripcionMateria.A_EXAMEN,
    EstadoInscripcionMateria.REPROBADO,
}
CON_NOTA_FINAL = {
    EstadoInscripcionMateria.EXONERADO, EstadoInscripcionMateria.APROBADO,
    EstadoInscripcionMateria.REVALIDADA,
}
AREAS = {
    "informatica": AreaPrograma.INFORMATICA,
    "administracion": AreaPrograma.ADMINISTRACION,
    "comunicacion": AreaPrograma.COMUNICACION,
    "cultura": AreaPrograma.CULTURA,
}

# Politicas que ya existen en la base. Las carreras usan la de 5 oportunidades de
# examen; los cursos independientes, una de 2 sin caducidad (bedelia,
# 23/09/2026), que se crea si no esta.
POLITICA_CARRERA = "Base 100 - Carrera AP"
POLITICA_CURSO = "Base 100 - Curso Corto"
EXAMEN_CARRERA_OPORTUNIDADES = 5
EXAMEN_CURSO = "Examen curso independiente - 2 oportunidades"

# El Integrador de Analista Programador requiere todas las materias de su plan
# (LEEME de la planilla). Bedelia lo llama Proyecto Integrador Final.
CODIGO_INTEGRADOR = "INT"
CARRERA_INTEGRADOR = "Analista Programador"


def _ahora() -> datetime:
    return datetime.now(TZ)


def _inicio_de(anio: int) -> datetime:
    """Una fecha para lo que solo tiene año: el comienzo de los cursos."""
    return datetime(anio, 3, 1, tzinfo=TZ)


def _fecha(valor) -> Optional[date]:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$", str(valor or ""))
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _email(valor: str) -> Optional[str]:
    valor = (valor or "").strip().lower()
    return valor if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", valor) else None


def _numero(valor) -> Optional[float]:
    return float(valor) if valor is not None else None


class Importador:
    def __init__(self, validador: Validador, session: Session):
        self.v = validador
        self.s = session
        self.anio_actual = _ahora().year
        self.cuenta: Counter = Counter()
        self.notas: List[str] = []
        self.programa_de_clave: Dict[str, Programa] = {}   # clave de materia -> programa
        self.materia_de_clave: Dict[str, Materia] = {}
        self.alumno_de_doc: Dict[str, Alumno] = {}
        self.profesor_de_doc: Dict[str, Profesor] = {}

    # ── Utilidades ───────────────────────────────────────────────────────────

    def _contar(self, que: str, creado: bool):
        self.cuenta[f"{que}: {'nuevos' if creado else 'ya estaban'}"] += 1

    def _plan_efectivo(self, carrera: str, plan: Optional[str]) -> Optional[str]:
        """El plan va en el nombre solo si la carrera tiene varios."""
        return plan if self.v._varios_planes(carrera) else None

    def _plan_vigente(self, carrera: str) -> Optional[str]:
        planes = self.v.planes_de_programa.get(carrera)
        return max(planes) if planes else None

    def _todos(self, modelo):
        return self.s.exec(select(modelo)).all()

    def _cargar_base(self):
        """Lo que ya hay, en memoria. Se va actualizando a medida que se crea."""
        self.programas = {p.nombre: p for p in self._todos(Programa)}
        materias = self._todos(Materia)
        self.materia_por_codigo = {m.codigo: m for m in materias if m.codigo}
        self.materia_por_nombre = {(m.programa_id, normalizar(m.nombre)): m for m in materias}
        self.previaturas_base = {(p.materia_id, p.materia_previa_id): p for p in self._todos(Previatura)}
        usuarios = self._todos(Usuario)
        self.usuario_por_doc = {u.documento: u for u in usuarios if u.documento}
        self.usuario_por_email = {u.email.lower(): u for u in usuarios if u.email}
        self.alumno_por_usuario = {a.usuario_id: a for a in self._todos(Alumno)}
        self.profesor_por_usuario = {p.usuario_id: p for p in self._todos(Profesor)}
        self.insc_programa = {(i.alumno_id, i.programa_id): i for i in self._todos(InscripcionPrograma)}
        self.cursadas = {(c.materia_id, c.anio_lectivo): c for c in self._todos(InstanciaCursado)
                         if c.semestre is None}
        self.insc_materia = {(i.alumno_id, i.instancia_cursado_id): i for i in self._todos(InscripcionMateria)}
        self.asignaciones = {(d.profesor_id, d.instancia_cursado_id) for d in self._todos(DocenteMateria)}
        self.evaluaciones: Dict[int, list] = defaultdict(list)
        for e in sorted(self._todos(MateriaInstanciaEvaluacion), key=lambda e: e.orden or 0):
            if e.activo:
                self.evaluaciones[e.instancia_cursado_id].append(e)

    def _estados_en_la_base(self) -> Optional[set]:
        """
        Los valores del enum de estados de InscripcionMateria que acepta
        Postgres. En develop falta REVALIDADA (el codigo lo tiene, ninguna
        migracion lo agrego): esas filas se saltean con un aviso y entran al
        volver a correr despues de la migracion. None si no es Postgres.
        """
        if self.s.get_bind().dialect.name != "postgresql":
            return None
        return {r[0] for r in self.s.exec(text(
            "select e.enumlabel from pg_enum e join pg_type t on t.oid = e.enumtypid "
            "where t.typname = 'estadoinscripcionmateria'")).all()}

    # ── Politicas ────────────────────────────────────────────────────────────

    def _politicas(self):
        calificacion = {p.nombre: p for p in self._todos(PoliticaCalificacion)}
        for nombre in (POLITICA_CARRERA, POLITICA_CURSO):
            if nombre not in calificacion:
                raise RuntimeError(f"No esta la politica de calificacion '{nombre}' en la base.")
        self.pol_carrera, self.pol_curso = calificacion[POLITICA_CARRERA], calificacion[POLITICA_CURSO]
        self.politicas = {p.id: p for p in calificacion.values()}

        examenes = self._todos(PoliticaExamen)
        self.examen_carrera = next((p for p in examenes if p.activo
                                    and p.max_oportunidades == EXAMEN_CARRERA_OPORTUNIDADES), None)
        if self.examen_carrera is None:
            raise RuntimeError("No esta la politica de examen de 5 oportunidades en la base.")
        self.examen_curso = next((p for p in examenes if p.nombre == EXAMEN_CURSO), None)
        creado = self.examen_curso is None
        if creado:
            self.examen_curso = PoliticaExamen(
                nombre=EXAMEN_CURSO, nota_maxima=self.examen_carrera.nota_maxima,
                umbral_aprobacion=self.examen_carrera.umbral_aprobacion, max_oportunidades=2,
            )
            self.s.add(self.examen_curso)
            self.s.flush()
        self._contar("politicas de examen", creado)

    # ── Programas y materias ─────────────────────────────────────────────────

    def programas_y_materias(self):
        por_programa: Dict[Tuple[str, Optional[str]], List[str]] = defaultdict(list)
        for clave, m in self.v.materias.items():
            por_programa[(m["programa"], self._plan_efectivo(m["programa"], m["plan"]))].append(clave)
        orden = sorted(por_programa, key=lambda x: (x[0], x[1] or ""))

        for carrera, plan in orden:
            programa = self._programa(carrera, plan, [self.v.materias[c] for c in por_programa[(carrera, plan)]])
            for clave in por_programa[(carrera, plan)]:
                self.programa_de_clave[clave] = programa
        self.s.flush()   # ids de los programas nuevos

        codigos = self._codigos_finales()
        for clave, m in self.v.materias.items():
            self.materia_de_clave[clave] = self._materia(self.programa_de_clave[clave], codigos[clave], m)
        self.s.flush()   # ids de las materias nuevas

    def _codigos_finales(self) -> Dict[str, Optional[str]]:
        """Codigo en la base para cada materia: los planes viejos llevan el año."""
        finales: Dict[str, Optional[str]] = {}
        for clave, m in self.v.materias.items():
            codigo = m["codigo"] or None
            if (codigo and self._plan_efectivo(m["programa"], m["plan"])
                    and m["plan"] != self._plan_vigente(m["programa"])):
                codigo = f"{codigo}-{m['plan']}"
            finales[clave] = codigo
        repetidos = [c for c, n in Counter(c for c in finales.values() if c).items() if n > 1]
        if repetidos:
            raise RuntimeError(f"Codigos de materia repetidos entre programas: {', '.join(sorted(repetidos))}. "
                               f"materia.codigo es unico en la base.")
        largos = [c for c in finales.values() if c and len(c) > 20]
        if largos:
            raise RuntimeError(f"Codigos de mas de 20 caracteres: {', '.join(largos)}.")
        return finales

    def _programa(self, carrera: str, plan: Optional[str], datos: List[dict]) -> Programa:
        nombre = nombre_programa(carrera, plan)
        programa = self.programas.get(nombre)
        if programa is None and plan and plan == self._plan_vigente(carrera) and carrera in self.programas:
            # El programa que existia antes de separar los planes es el del vigente
            programa = self.programas.pop(carrera)
            self.notas.append(f"El programa '{carrera}' (id {programa.id}) pasa a llamarse '{nombre}'.")
            programa.nombre = nombre

        semestres = [semestre_del_plan(m["semestre"]) for m in datos if m["semestre"] is not None]
        area = next((AREAS[a] for m in datos for a in AREAS if a in normalizar(m["observaciones"])), None)
        creado = programa is None
        if creado:
            programa = Programa(
                nombre=nombre, area=area,
                tipo=TipoPrograma.CARRERA if semestres else TipoPrograma.CURSO_CORTO,
                duracion_semestres=max(semestres) if semestres else None,
                # Los planes viejos no se ofrecen: quedan para el historial de quien los curso
                activo=plan is None or plan == self._plan_vigente(carrera),
            )
        else:
            programa.area = programa.area or area
            programa.duracion_semestres = programa.duracion_semestres or (max(semestres) if semestres else None)
        self.s.add(programa)
        self.programas[nombre] = programa
        self._contar("programas", creado)
        return programa

    def _materia(self, programa: Programa, codigo: Optional[str], m: dict) -> Materia:
        materia = self.materia_por_codigo.get(codigo) if codigo else None
        if materia is not None and materia.programa_id != programa.id:
            raise RuntimeError(f"El codigo {codigo} ya es de otra materia (id {materia.id}, programa "
                               f"{materia.programa_id}), no de '{programa.nombre}'.")
        if materia is None:
            materia = self.materia_por_nombre.get((programa.id, normalizar(m["nombre"])))

        es_carrera = programa.tipo == TipoPrograma.CARRERA
        creado = materia is None
        if creado:
            materia = Materia(programa_id=programa.id, nombre=m["nombre"], semestre=1, creditos=0,
                              politica_id=(self.pol_carrera if es_carrera else self.pol_curso).id)
        # La planilla manda sobre lo que hubiera (la malla de prueba de develop)
        materia.nombre = m["nombre"]
        materia.codigo = codigo
        materia.semestre = semestre_del_plan(m["semestre"]) or 1
        materia.creditos = int(float(m["creditos"])) if m["creditos"] else 0
        materia.activo = m["dictando"] != "NO"
        if materia.politica_examen_id is None:
            materia.politica_examen_id = (self.examen_carrera if es_carrera else self.examen_curso).id
        self.s.add(materia)
        if codigo:
            self.materia_por_codigo[codigo] = materia
        self._contar("materias", creado)
        return materia

    # ── Previaturas ──────────────────────────────────────────────────────────

    def previaturas(self):
        pares = [(f["materia"], f["previa"], TipoPreviatura(f["tipo"].lower())) for f in self.v.filas_previaturas]

        # El Integrador requiere todas las materias de su plan
        integrador = next((c for c, m in self.v.materias.items()
                           if m["codigo"] == CODIGO_INTEGRADOR and m["programa"] == CARRERA_INTEGRADOR
                           and m["plan"] == self._plan_vigente(CARRERA_INTEGRADOR)), None)
        if integrador:
            programa = self.programa_de_clave[integrador]
            otras = [c for c, p in self.programa_de_clave.items() if p is programa and c != integrador]
            pares += [(integrador, c, TipoPreviatura.APROBADA) for c in otras]

        for clave, clave_previa, tipo in pares:
            materia, previa = self.materia_de_clave[clave], self.materia_de_clave[clave_previa]
            existente = self.previaturas_base.get((materia.id, previa.id))
            creado = existente is None
            if creado:
                existente = Previatura(materia_id=materia.id, materia_previa_id=previa.id, tipo_requerido=tipo)
                self.previaturas_base[(materia.id, previa.id)] = existente
            existente.tipo_requerido = tipo
            self.s.add(existente)
            self._contar("previaturas", creado)

    # ── Personas ─────────────────────────────────────────────────────────────

    def _persona(self, fila: dict, rol: RolUsuario) -> Usuario:
        documento, email = fila["documento"], _email(fila["email"])
        usuario = self.usuario_por_doc.get(documento)
        if usuario is None and email:
            usuario = self.usuario_por_email.get(email)
            if usuario is not None and usuario.documento and usuario.documento != documento:
                raise RuntimeError(f"El email {email} ya es de otra persona (cedula {usuario.documento}).")

        creado = usuario is None
        if creado:
            # Igual que usuarioService.create_manual: el login con Google lo vincula
            # por email y activa la cuenta
            usuario = Usuario(nombre=fila["nombre"][:100], apellido=fila["apellido"][:100], rol=rol,
                              google_activo=False, moodle_activo=False)
        # Solo completa lo que falta: lo que ya trae la cuenta (Google) se respeta
        usuario.documento = usuario.documento or documento
        if email and not usuario.email:
            otro = self.usuario_por_email.get(email)
            if otro is None or otro is usuario:
                usuario.email = email
            else:
                self.notas.append(f"{documento}: el email {email} ya lo tiene otro usuario; no se asigna.")
        usuario.email_personal = usuario.email_personal or _email(fila["email_personal"])
        telefono = re.sub(r"[^\d+]", "", fila["telefono"] or "")[:20]
        usuario.telefono = usuario.telefono or telefono or None
        if "nacimiento" in fila:
            usuario.fecha_nacimiento = usuario.fecha_nacimiento or _fecha(fila["nacimiento"])
        self.s.add(usuario)
        self.usuario_por_doc[documento] = usuario
        if usuario.email:
            self.usuario_por_email[usuario.email] = usuario
        self._contar("personas", creado)
        return usuario

    def personas(self):
        docentes = [(f, self._persona(f, RolUsuario.DOCENTE)) for f in self.v.filas_docentes]
        alumnos = {}
        for f in self.v.filas_alumnos:
            if f["documento"] not in alumnos:
                alumnos[f["documento"]] = (f, self._persona(f, RolUsuario.ESTUDIANTE))
        self.s.flush()   # ids de las personas nuevas

        for fila, usuario in docentes:
            profesor = self.profesor_por_usuario.get(usuario.id)
            creado = profesor is None
            if creado:
                profesor = Profesor(usuario_id=usuario.id)
                self.profesor_por_usuario[usuario.id] = profesor
            profesor.activo = fila["activo"]
            self.s.add(profesor)
            self.profesor_de_doc[fila["documento"]] = profesor
            self._contar("perfiles docentes", creado)

        for documento, (fila, usuario) in alumnos.items():
            alumno = self.alumno_por_usuario.get(usuario.id)
            creado = alumno is None
            if creado:
                alumno = Alumno(usuario_id=usuario.id, fecha_ingreso=_inicio_de(fila["anio"] or self.anio_actual))
                self.alumno_por_usuario[usuario.id] = alumno
                self.s.add(alumno)
            self.alumno_de_doc[documento] = alumno
            self._contar("perfiles de alumno", creado)
        self.s.flush()   # ids de alumnos y profesores

    def inscripciones_a_programas(self):
        anios: Dict[Tuple[str, int], List[int]] = defaultdict(list)
        for h in self.v.filas_historial:
            if h["anio"]:
                anios[(h["documento"], self.programa_de_clave[h["materia"]].id)].append(h["anio"])

        for fila in self.v.filas_alumnos:
            alumno = self.alumno_de_doc[fila["documento"]]
            carrera = fila["programa"]
            plan = self._plan_efectivo(carrera, fila["plan"] or self._plan_vigente(carrera))
            programa = self.programas[nombre_programa(carrera, plan)]
            anio = fila["anio"] or min(anios.get((fila["documento"], programa.id), [self.anio_actual]))
            estado = EstadoInscripcionPrograma(fila["estado"].lower())
            inscripcion = self.insc_programa.get((alumno.id, programa.id))
            creado = inscripcion is None
            if creado:
                inscripcion = InscripcionPrograma(alumno_id=alumno.id, programa_id=programa.id, estado=estado,
                                                  anio_ingreso=anio, fecha_inscripcion=_inicio_de(anio))
                self.insc_programa[(alumno.id, programa.id)] = inscripcion
            inscripcion.estado = estado
            self.s.add(inscripcion)
            self._contar("inscripciones a programas", creado)

    # ── Historial ────────────────────────────────────────────────────────────

    def _snapshot_politica(self, materia: Materia) -> dict:
        p = self.politicas[materia.politica_id]
        return {
            "politica_id": p.id, "nombre": p.nombre, "nota_maxima": _numero(p.nota_maxima),
            "tipo_nota": p.tipo_nota.value if p.tipo_nota else None,
            "umbral_aprobacion": _numero(p.umbral_aprobacion), "umbral_examen": _numero(p.umbral_examen),
            "umbral_exoneracion": _numero(p.umbral_exoneracion),
        }

    def historial(self):
        en_la_base = self._estados_en_la_base()
        salteadas: Dict[str, List[int]] = defaultdict(list)
        filas = []
        for h in self.v.filas_historial:
            estado = ESTADO_MATERIA[h["estado"]]
            if en_la_base is not None and estado.name not in en_la_base:
                salteadas[estado.name].append(h["fila"])
                continue
            anio = h["anio"]
            if anio is None:
                anio = self.anio_actual
                self.notas.append(f"5-Historial fila {h['fila']}: sin año, se toma {anio}.")
            filas.append((h, estado, anio))

        # Primero las cursadas (una por materia y año), para tener sus ids
        for h, estado, anio in filas:
            materia = self.materia_de_clave[h["materia"]]
            cursada = self.cursadas.get((materia.id, anio))
            if cursada is None:
                cursada = InstanciaCursado(materia_id=materia.id, anio_lectivo=anio,
                                           estado=EstadoInstanciaCursado.FINALIZADA)
                self.cursadas[(materia.id, anio)] = cursada
                self._contar("cursadas", True)
            if estado == EstadoInscripcionMateria.CURSANDO:
                cursada.estado = EstadoInstanciaCursado.EN_CURSO
            self.s.add(cursada)
        self.s.flush()

        for h, estado, anio in filas:
            materia = self.materia_de_clave[h["materia"]]
            alumno = self.alumno_de_doc[h["documento"]]
            cursada = self.cursadas[(materia.id, anio)]
            inscripcion = self.insc_materia.get((alumno.id, cursada.id))
            creado = inscripcion is None
            if creado:
                inscripcion = InscripcionMateria(alumno_id=alumno.id, instancia_cursado_id=cursada.id,
                                                 estado=estado, fecha_inscripcion=_inicio_de(anio))
                self.insc_materia[(alumno.id, cursada.id)] = inscripcion
            nota = Decimal(str(h["nota"])) if h["nota"] is not None else None
            inscripcion.estado = estado
            inscripcion.nota_curso = nota if estado in CON_NOTA_DE_CURSO else None
            inscripcion.nota_final = nota if estado in CON_NOTA_FINAL else None
            inscripcion.creditos_obtenidos = materia.creditos if estado in QUE_DAN_CREDITOS else 0
            if estado == EstadoInscripcionMateria.REVALIDADA:
                inscripcion.motivo_revalida = (h["observaciones"] or "Reválida (carga inicial)")[:255]
            inscripcion.snapshot_politica = inscripcion.snapshot_politica or self._snapshot_politica(materia)
            if estado == EstadoInscripcionMateria.CURSANDO and not inscripcion.snapshot_instancias:
                inscripcion.snapshot_instancias = [
                    {"id": e.id, "nombre": e.nombre, "peso_maximo": _numero(e.peso_maximo),
                     "orden": e.orden, "es_grupal": e.es_grupal}
                    for e in self.evaluaciones.get(cursada.id, [])
                ]
            self.s.add(inscripcion)
            self._contar("inscripciones a materias", creado)

        for estado, numeros in salteadas.items():
            self.notas.append(
                f"PENDIENTE: {len(numeros)} filas {estado} del historial no entraron (filas "
                f"{', '.join(map(str, numeros))}): la base no tiene ese estado. Falta la migracion "
                f"que lo agrega; despues, volver a correr el importador.")

    # ── Dictado ──────────────────────────────────────────────────────────────

    def dictado(self):
        sin_cursada = 0
        for d in self.v.filas_dictado:
            materia = self.materia_de_clave[d["materia"]]
            cursada = self.cursadas.get((materia.id, self.anio_actual))
            if cursada is None or cursada.estado != EstadoInstanciaCursado.EN_CURSO:
                sin_cursada += bool(d["docentes"])
                continue
            cursada.horario = cursada.horario or d["horario"] or None
            cursada.salon = cursada.salon or d["salon"] or None
            cursada.cupo_maximo = cursada.cupo_maximo or d["cupo"]
            self.s.add(cursada)
            for documento, rol in d["docentes"]:
                profesor = self.profesor_de_doc[documento]
                creado = (profesor.id, cursada.id) not in self.asignaciones
                if creado:
                    self.s.add(DocenteMateria(profesor_id=profesor.id, instancia_cursado_id=cursada.id,
                                              rol_docente=RolDocente(rol.lower())))
                    self.asignaciones.add((profesor.id, cursada.id))
                self._contar("asignaciones docentes", creado)
        if sin_cursada:
            self.notas.append(
                f"{sin_cursada} filas de la hoja 6 con docente son de materias sin alumnos cursando "
                f"este año: no se les crea cursada (el docente se asigna cuando se abra).")

    # ── Todo ─────────────────────────────────────────────────────────────────

    def correr(self):
        with self.s.no_autoflush:
            self._cargar_base()
            self._politicas()
            self.programas_y_materias()
            self.previaturas()
            self.personas()
            self.inscripciones_a_programas()
            self.historial()
            self.dictado()
        self.s.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("archivo", help="Planilla .xlsx de carga inicial, ya validada")
    parser.add_argument("--confirmar", action="store_true", help="Escribe en la base (sin esto, simula)")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    validador = Validador(args.archivo)
    errores = [p for p in validador.correr() if p.nivel == "ERROR"]
    if errores:
        print(f"La planilla tiene {len(errores)} errores: no se importa nada. "
              f"Correr validar_planilla_migracion para verlos.")
        return 1

    from database.database import engine
    with Session(engine) as session:
        importador = Importador(validador, session)
        try:
            importador.correr()
        except Exception:
            session.rollback()
            raise
        for linea, n in sorted(importador.cuenta.items()):
            print(f"  {linea:<45} {n}")
        for nota in importador.notas:
            print(f"  - {nota}")
        if args.confirmar:
            session.commit()
            print("\nImportado.")
        else:
            session.rollback()
            print("\nSimulacion: no se escribio nada. Para importar, agregar --confirmar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
