"""
Historico de escolaridades: lo que bedelia llevaba en la planilla
"Escolaridades ver 2023.xlsm" antes del portal.

Son ~20 años de actas (2004-2026, con volumen desde 2008): cada fila es una
evaluacion de un alumno en una materia de un plan. Muchos de esos planes ya no
existen y ninguno tiene una politica de calificacion vigente, asi que estos
datos NO se cuelgan de programa/materia/alumno del portal. Van en tres tablas
propias, de solo lectura, sin FK hacia el resto del esquema:

  historico_plan       el plan tal como lo nombraba la planilla ("TA 2001")
  historico_alumno     la persona, por cedula
  historico_resultado  una fila de acta

El vinculo con el portal es solo por cedula (usuario.documento), en consulta.

Los codigos (tipo_evaluacion, resultado, credito) se guardan como texto y no
como enum de Postgres a proposito: son los codigos historicos de bedelia, no se
van a extender, y un enum obligaria a una migracion por cada valor raro que
aparezca al reimportar. El significado esta documentado en
docs/HISTORICO_ESCOLARIDADES.md y en las constantes de abajo.

Se cargan una vez con v2/scripts/importar_historico.py. No hay endpoints de
escritura.
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict
from datetime import date


# ── Codigos historicos (texto, no enum) ──────────────────────────────────────

TIPOS_EVALUACION = {
    "CUR": "Cursada",
    "EXA": "Examen",
    "TALLER": "Taller",
    "REV": "Revalida",
    "DIP": "Diploma",
}

RESULTADOS = {
    "APR": "Aprobado",
    "EXO": "Exonerado",
    "ELI": "Eliminado",
    "NSP": "No se presento",
    "REV": "Revalidado",
    "EXA": "A examen",
    "PEND": "Pendiente",
}

CREDITOS = {
    "T": "Credito total",
    "P": "Credito parcial (cursada aprobada, examen pendiente)",
}


# ── Tablas ───────────────────────────────────────────────────────────────────

class HistoricoPlan(SQLModel, table=True):
    """
    Un plan de estudios historico, identificado por el codigo que usaba la
    planilla. `carrera` y `creditos_requeridos` salen del catalogo de la hoja
    ESCOLARIDAD; para los codigos que no estaban ahi (cursos cortos) la carrera
    se dedujo de las materias que contiene, y puede ser null.
    """
    __tablename__ = "historico_plan"

    id: Optional[int] = Field(default=None, primary_key=True)
    codigo: str = Field(max_length=30, unique=True, index=True, description="Ej: 'AP 2011', 'TA 2016 N'")
    carrera: Optional[str] = Field(default=None, max_length=150, description="Nombre de la carrera o curso")
    creditos_requeridos: Optional[int] = Field(default=None, description="Creditos para egresar, segun la planilla")

    resultados: List["HistoricoResultado"] = Relationship(back_populates="plan")


class HistoricoAlumno(SQLModel, table=True):
    """
    Una persona de la hoja ALUMNOS (o que aparece solo en RESULTADOS).

    Los datos de contacto son los que tenia el sistema viejo y pueden estar
    desactualizados. Se dejaron afuera las notas de cobranza (cl_observ) y el
    RUC: no son parte de un legajo academico.
    """
    __tablename__ = "historico_alumno"

    id: Optional[int] = Field(default=None, primary_key=True)
    cedula: str = Field(max_length=20, unique=True, index=True, description="Solo digitos, sin puntos ni guion")
    nombre: str = Field(max_length=150, description="Como figura en la planilla: APELLIDOS NOMBRES")
    nombre_busqueda: str = Field(max_length=150, index=True, description="Mayusculas sin acentos ni eñes, para buscar")
    plan_declarado: Optional[str] = Field(default=None, max_length=30, description="Plan segun la hoja ALUMNOS (puede diferir de los resultados)")
    zona: Optional[str] = Field(default=None, max_length=20, description="Codigo de la planilla, parece ser año de ingreso + carrera (ej: '05TA')")
    direccion: Optional[str] = Field(default=None, max_length=200)
    localidad: Optional[str] = Field(default=None, max_length=100)
    departamento: Optional[str] = Field(default=None, max_length=10, description="Codigo numerico tal como venia")
    telefono: Optional[str] = Field(default=None, max_length=100)
    celular: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=255)
    observaciones: Optional[str] = Field(default=None, max_length=500)
    fila_origen: Optional[int] = Field(default=None, description="Fila de la hoja ALUMNOS, para volver a la fuente")

    resultados: List["HistoricoResultado"] = Relationship(back_populates="alumno")


class HistoricoResultado(SQLModel, table=True):
    """
    Una fila de acta: la evaluacion de un alumno en una materia de un plan.

    `puntaje` es la nota; `puntaje_promedio` es la nota que bedelia usaba para
    promediar (0 cuando el alumno fue eliminado o no se presento). `credito`
    dice si la fila otorga credito total o parcial. Ver el resumen del legajo
    en historico_service para como se combinan.
    """
    __tablename__ = "historico_resultado"

    id: Optional[int] = Field(default=None, primary_key=True)
    alumno_id: int = Field(foreign_key="historico_alumno.id", index=True)
    plan_id: int = Field(foreign_key="historico_plan.id", index=True)
    materia: str = Field(max_length=120, index=True, description="Nombre en mayusculas, sin espacios dobles")
    docente: Optional[str] = Field(default=None, max_length=120)
    fecha: Optional[date] = Field(default=None, index=True)
    fecha_texto: Optional[str] = Field(default=None, max_length=20, description="La fecha original cuando no se pudo interpretar")
    tipo_evaluacion: str = Field(max_length=10, description="CUR, EXA, TALLER, REV, DIP")
    resultado: Optional[str] = Field(default=None, max_length=10, description="APR, EXO, ELI, NSP, REV, EXA, PEND")
    puntaje: Optional[int] = Field(default=None, description="0 a 100")
    puntaje_promedio: Optional[int] = Field(default=None, description="Nota que entra en el promedio")
    credito: Optional[str] = Field(default=None, max_length=1, description="T o P")
    acta: Optional[str] = Field(default=None, max_length=20, description="Numero de acta (columna OBS)")
    proyecto: Optional[int] = Field(default=None, description="Numero de proyecto, en los integradores")
    observaciones: Optional[str] = Field(default=None, max_length=200, description="Columna Zona de la planilla")
    operador: Optional[str] = Field(default=None, max_length=10, description="Iniciales de quien cargo la fila")
    fila_origen: Optional[int] = Field(default=None, description="Fila de la hoja RESULTADOS")

    alumno: Optional[HistoricoAlumno] = Relationship(back_populates="resultados")
    plan: Optional[HistoricoPlan] = Relationship(back_populates="resultados")


# ── Schemas de lectura ───────────────────────────────────────────────────────

class HistoricoPlanRead(SQLModel):
    id: int
    codigo: str
    carrera: Optional[str] = None
    creditos_requeridos: Optional[int] = None


class HistoricoAlumnoRead(SQLModel):
    id: int
    cedula: str
    nombre: str
    plan_declarado: Optional[str] = None
    zona: Optional[str] = None
    direccion: Optional[str] = None
    localidad: Optional[str] = None
    departamento: Optional[str] = None
    telefono: Optional[str] = None
    celular: Optional[str] = None
    email: Optional[str] = None
    observaciones: Optional[str] = None


class HistoricoAlumnoResumenRead(SQLModel):
    """Una fila del listado: lo justo para encontrar a la persona."""
    id: int
    cedula: str
    nombre: str
    plan_declarado: Optional[str] = None
    planes: List[str] = Field(default_factory=list, description="Codigos de plan con resultados")
    cantidad_resultados: int = 0
    primera_fecha: Optional[date] = None
    ultima_fecha: Optional[date] = None


class HistoricoResultadoRead(SQLModel):
    id: int
    plan: str = Field(description="Codigo del plan")
    carrera: Optional[str] = None
    materia: str
    docente: Optional[str] = None
    fecha: Optional[date] = None
    fecha_texto: Optional[str] = None
    tipo_evaluacion: str
    tipo_evaluacion_descripcion: Optional[str] = None
    resultado: Optional[str] = None
    resultado_descripcion: Optional[str] = None
    puntaje: Optional[int] = None
    puntaje_promedio: Optional[int] = None
    credito: Optional[str] = None
    acta: Optional[str] = None
    proyecto: Optional[int] = None
    observaciones: Optional[str] = None
    otorga_credito: bool = Field(default=False, description="Cuenta como credito aprobado segun la regla de bedelia")


class ResumenPlanRead(SQLModel):
    """Lo que el certificado de escolaridad calculaba por plan."""
    plan: str
    carrera: Optional[str] = None
    creditos_requeridos: Optional[int] = None
    creditos_aprobados: int = 0
    creditos_revalidados: int = 0
    promedio: Optional[float] = None
    cantidad_resultados: int = 0
    por_resultado: Dict[str, int] = Field(default_factory=dict, description="Ej: {'APR': 10, 'ELI': 2}")
    materias_aprobadas: List[str] = Field(default_factory=list, description="Materias con credito total")
    primera_fecha: Optional[date] = None
    ultima_fecha: Optional[date] = None


class ResumenCarreraRead(SQLModel):
    """
    La escolaridad de una carrera: todas las actas de todos sus planes juntas.
    Es el criterio de bedelia (22/09/2026): si el alumno cambio de plan dentro
    de la misma carrera se suma, si son carreras o cursos distintos, no.
    """
    carrera: str
    planes: List[str] = Field(default_factory=list, description="Codigos de plan que entran, en orden de fecha")
    creditos_requeridos: Optional[int] = Field(default=None, description="Del plan del acta mas reciente")
    creditos_aprobados: int = 0
    creditos_revalidados: int = 0
    promedio: Optional[float] = None
    cantidad_resultados: int = 0
    por_resultado: Dict[str, int] = Field(default_factory=dict)
    materias_aprobadas: List[str] = Field(default_factory=list)
    primera_fecha: Optional[date] = None
    ultima_fecha: Optional[date] = None


class LegajoHistoricoRead(SQLModel):
    alumno: HistoricoAlumnoRead
    carreras: List[ResumenCarreraRead] = Field(
        default_factory=list,
        description="LA ESCOLARIDAD: un promedio por carrera, con todos sus planes juntos",
    )
    general: Optional[ResumenPlanRead] = Field(
        default=None,
        description="Todas las actas juntas, de todas las carreras. Es lo que imprimia el Excel "
                    "viejo (CARRERA = (Todas)); sirve para cotejar certificados ya emitidos",
    )
    planes: List[ResumenPlanRead] = Field(
        default_factory=list,
        description="Desglose plan por plan",
    )
    resultados: List[HistoricoResultadoRead] = Field(default_factory=list, description="Ordenados por fecha")
    codigos: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Diccionarios de tipo_evaluacion, resultado y credito para mostrar",
    )
