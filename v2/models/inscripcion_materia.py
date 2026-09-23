from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON
from typing import Optional, List, Any, TYPE_CHECKING
from datetime import datetime, date
from decimal import Decimal
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

from v2.models.enums import EstadoInscripcionMateria

if TYPE_CHECKING:
    from v2.models.alumno import Alumno
    from v2.models.instancia_cursado import InstanciaCursado
    from v2.models.calificacion import Calificacion
    from v2.models.inscripcion_examen import InscripcionExamen


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


class InscripcionMateria(SQLModel, table=True):
    __tablename__ = "inscripcion_materia"

    id: Optional[int] = Field(default=None, primary_key=True)
    alumno_id: int = Field(foreign_key="alumno.id", index=True, description="Alumno inscripto")
    instancia_cursado_id: int = Field(foreign_key="instancia_cursado.id", index=True, description="Instancia de cursado")
    estado: EstadoInscripcionMateria = Field(
        default=EstadoInscripcionMateria.CURSANDO,
        description="Estado actual de la inscripción"
    )
    nota_curso: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="Suma de notas de instancias")
    nota_final: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="Nota final (puede ser nota examen)")
    nota_final_directa: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2, description="Nota final cargada directamente por profesor")
    creditos_obtenidos: int = Field(default=0, description="Créditos si aprobó, 0 si no")
    faltas: int = Field(default=0, description="Cantidad de faltas acumuladas")

    # Snapshots JSONB - preservan las reglas históricas al momento de inscripción
    snapshot_politica: Optional[dict] = Field(default=None, sa_column=Column(JSON), description="Snapshot de la política de calificación vigente")
    snapshot_instancias: Optional[list] = Field(default=None, sa_column=Column(JSON), description="Snapshot de las instancias de evaluación vigentes")

    fecha_inscripcion: datetime = Field(default_factory=lambda: datetime.now(get_uruguay_tz()))
    fecha_cierre: Optional[datetime] = Field(default=None, description="Fecha en que se determinó el estado final")
    motivo_cierre: Optional[str] = Field(default=None, max_length=255, description="Motivo de inasistencia/abandono")
    motivo_revalida: Optional[str] = Field(default=None, max_length=255, description="Motivo de reválida (ej: 'Aprobada en UTEC - 2025')")
    fecha_baja: Optional[datetime] = Field(default=None, description="Fecha de baja/desinscripción")
    notificacion_calificacion_enviada: bool = Field(
        default=False,
        description="Si se envió notificación de calificación al estudiante"
    )
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad"
    )

    # Relaciones
    alumno: Optional["Alumno"] = Relationship(back_populates="inscripciones")
    instancia_cursado: Optional["InstanciaCursado"] = Relationship(back_populates="inscripciones")
    calificaciones: List["Calificacion"] = Relationship(back_populates="inscripcion")
    inscripciones_examen: List["InscripcionExamen"] = Relationship(back_populates="inscripcion_materia")


# ── Schemas ──────────────────────────────────────────────────────────────────

class InscripcionMateriaCreate(SQLModel):
    alumno_id: int
    instancia_cursado_id: int


class InscripcionMateriaRead(SQLModel):
    id: int
    alumno_id: int
    instancia_cursado_id: int
    estado: EstadoInscripcionMateria
    nota_curso: Optional[Decimal] = None
    nota_final: Optional[Decimal] = None
    nota_final_directa: Optional[Decimal] = None
    creditos_obtenidos: int
    faltas: int = 0
    snapshot_politica: Optional[dict] = None
    snapshot_instancias: Optional[list] = None
    fecha_inscripcion: datetime
    fecha_cierre: Optional[datetime] = None
    motivo_cierre: Optional[str] = None
    motivo_revalida: Optional[str] = None
    fecha_baja: Optional[datetime] = None
    notificacion_calificacion_enviada: bool = False
    id_rastreo: Optional[str] = None
    id_rastreo_notificacion: Optional[str] = None


# Pseudo-estado para materias del plan en las que el alumno nunca se inscribio.
# No pertenece a EstadoInscripcionMateria porque ese enum es el tipo de la
# columna inscripcion_materia.estado y no admite valores sin respaldo en la tabla.
SIN_INSCRIPCION = "sin_inscripcion"


class EscolaridadMateriaItem(SQLModel):
    """
    Fila de escolaridad: una materia del plan del programa, con o sin
    inscripcion del alumno.

    Todas las filas traen el mismo conjunto de campos. Cuando el alumno nunca
    se inscribio, `estado` es SIN_INSCRIPCION y los campos propios de la
    inscripcion vienen en None (o 0 para los contadores).
    """
    inscripcion_id: Optional[int] = None
    materia_nombre: str
    materia_codigo: Optional[str] = None
    semestre: int
    anio_lectivo: Optional[int] = None
    estado: str = Field(
        description=f'Valor de EstadoInscripcionMateria, o "{SIN_INSCRIPCION}"'
    )
    nota_curso: Optional[Decimal] = None
    nota_final: Optional[Decimal] = None
    creditos_obtenidos: int = 0
    faltas: int = 0


class EscolaridadSemestre(SQLModel):
    """Materias de un semestre. Lista ordenada, no dict, para preservar el orden."""
    semestre: int
    materias: List[EscolaridadMateriaItem]


class ActividadEscolaridadRead(SQLModel):
    """
    Una actividad rendida: una cursada o una rendicion de examen. Es una fila
    del certificado, como en el Excel de bedelia.
    """
    fecha: Optional[date] = None
    materia: str
    tipo: str = Field(description="CUR, EXA, TALLER o REV")
    resultado: str = Field(description="APR, EXO, ELI, NSP o REV")
    nota: Optional[float] = Field(default=None, description="La nota original")
    nota_promedio: float = Field(description="Lo que suma al promedio (0 si fue eliminado o ausente)")
    cuenta_en_promedio: bool = Field(description="Si entra al divisor")
    origen: str = Field(description="historico (Excel de Escolaridades) o portal")
    detalle: Optional[str] = None


class PromedioEscolaridadRead(SQLModel):
    """
    Promedio con la regla de bedelia: todas las actividades rendidas de la
    carrera, historicas y del portal. Ver v2/services/promedio_escolaridad.py.
    """
    promedio: Optional[float] = Field(default=None, description="None si no hay nada que promediar")
    suma_notas: float = 0
    divisor: int = 0
    actividades_que_cuentan: int = 0
    del_historico: int = Field(default=0, description="Actividades que vienen del legajo historico")
    del_portal: int = Field(default=0, description="Actividades registradas en el portal despues del corte")
    carrera_historica: Optional[str] = Field(
        default=None, description="Carrera del historico que corresponde a este programa",
    )
    fecha_corte: Optional[date] = Field(
        default=None, description="Hasta aca vale el historico; despues, el portal",
    )
    actividades: List[ActividadEscolaridadRead] = Field(default_factory=list, description="Ordenadas por fecha")


class EscolaridadRead(SQLModel):
    """Escolaridad completa del alumno en un programa"""
    alumno_id: int
    programa_id: int
    semestres: List[EscolaridadSemestre]
    total_creditos: int
    total_creditos_posibles: int
    promedio: Optional[float] = Field(
        default=None,
        description="Promedio de la escolaridad con la regla de bedelia (todas las actividades rendidas)",
    )
    promedio_detalle: Optional[PromedioEscolaridadRead] = None


class MarcarInasistenciaRequest(SQLModel):
    inscripcion_id: int
    motivo: Optional[str] = None


class MarcarAbandonoRequest(SQLModel):
    inscripcion_id: int
    motivo: Optional[str] = None
