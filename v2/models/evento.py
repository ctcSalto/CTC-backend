"""
DTO de "proximos eventos" para la pantalla de inicio del portal.

No hay tabla `evento`: un evento es una vista computada que unifica fechas que
viven en varias tablas (periodos de inscripcion, instancias de examen, instancias
de cursado) en un unico formato que el frontend puede renderizar sin saber de que
tabla salio cada fecha.
"""
from sqlmodel import SQLModel
from typing import Optional
from datetime import datetime

from v2.models.enums import TipoEventoProximo


class EventoProximo(SQLModel):
    """Un evento proximo, en formato unificado para el frontend."""

    tipo: TipoEventoProximo
    titulo: str
    descripcion: Optional[str] = None

    # `fecha` es la fecha por la que se ordena y filtra: la ocurrencia del evento
    # (apertura, cierre, examen, inicio o fin de dictado). Un rango que en la BD
    # es una sola fila (un periodo con inicio y fin) se parte en dos eventos, cada
    # uno con su propia `fecha`, para que cada extremo aparezca o desaparezca del
    # listado por si mismo segun se acerque o pase.
    fecha: datetime

    # Contexto para que el frontend enlace al detalle sin adivinar la tabla.
    referencia_tipo: str   # "periodo_inscripcion_materia" | "instancia_examen" | "instancia_cursado"
    referencia_id: int

    # Datos utiles para la tarjeta, opcionales segun el tipo de evento.
    programa_nombre: Optional[str] = None
    materia_nombre: Optional[str] = None
    materia_codigo: Optional[str] = None
    anio_lectivo: Optional[int] = None
