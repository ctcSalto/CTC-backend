"""
Mesa de examen: el periodo al que pertenece un conjunto de examenes.

Existe para que el tope de examenes por periodo sea un hecho declarado y no algo
inferido de la fecha. Antes el periodo era el mes calendario de fecha_examen, y
eso fallaba de dos formas: una mesa que cruzaba fin de mes contaba doble (el
alumno se anotaba a 8), y dos mesas dentro de un mismo mes contaban como una (lo
bloqueaba mal, que es peor porque le niega algo que le corresponde).

Con la mesa, dos examenes son del mismo periodo porque bedelia lo dijo.

`max_examenes` permite que una mesa puntual tenga un tope distinto sin tocar
codigo. En null, se usa el de InscripcionExamenService.MAX_EXAMENES_POR_PERIODO.

La ventana de inscripcion se guarda aca para no repetirla en cada examen: al
crear una instancia dentro de la mesa, si no se manda ventana se copia esta. Es
una copia al crear, no una herencia viva: editar la mesa despues no reescribe la
de los examenes ya cargados. La ventana efectiva sigue siendo la de la instancia,
que es lo que leen las notificaciones, los proximos eventos y el chequeo de plazo.
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

if TYPE_CHECKING:
    from v2.models.instancia_examen import InstanciaExamen


# ── Modelo de tabla ──────────────────────────────────────────────────────────

class MesaExamen(SQLModel, table=True):
    __tablename__ = "mesa_examen"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(
        max_length=100,
        description="Ej: 'Julio 2026' o 'Julio 2026 - Extraordinaria'",
    )
    anio_lectivo: int = Field(index=True, description="Año lectivo de la mesa")
    fecha_inicio_inscripcion: datetime = Field(
        description="Inicio de inscripcion, para copiar a los examenes de la mesa"
    )
    fecha_fin_inscripcion: datetime = Field(
        description="Fin de inscripcion, para copiar a los examenes de la mesa"
    )
    max_examenes: Optional[int] = Field(
        default=None,
        description="Tope de examenes del alumno en esta mesa. Null usa el general",
    )
    activo: bool = Field(default=True)
    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True,
        description="UUID de trazabilidad",
    )

    # Relaciones
    instancias: List["InstanciaExamen"] = Relationship(back_populates="mesa")


# ── Schemas ──────────────────────────────────────────────────────────────────

class MesaExamenCreate(SQLModel):
    nombre: str = Field(max_length=100)
    anio_lectivo: int
    fecha_inicio_inscripcion: datetime
    fecha_fin_inscripcion: datetime
    max_examenes: Optional[int] = None


class MesaExamenUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, max_length=100)
    anio_lectivo: Optional[int] = None
    fecha_inicio_inscripcion: Optional[datetime] = None
    fecha_fin_inscripcion: Optional[datetime] = None
    max_examenes: Optional[int] = None
    activo: Optional[bool] = None


class MesaExamenRead(SQLModel):
    id: int
    nombre: str
    anio_lectivo: int
    fecha_inicio_inscripcion: datetime
    fecha_fin_inscripcion: datetime
    max_examenes: Optional[int] = None
    activo: bool
    id_rastreo: Optional[str] = None
