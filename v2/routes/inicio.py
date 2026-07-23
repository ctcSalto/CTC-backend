"""
Endpoints de la pantalla de inicio del portal, comunes a todos los roles.

`GET /v2/portal/proximos-eventos` identifica al usuario por el JWT y arma el
listado de proximas fechas importantes segun su rol activo (ESTUDIANTE, DOCENTE
o ADMINISTRATIVO). Ver v2/services/proximos_eventos_service.py.
"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from typing import List, Optional

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import get_current_usuario
from v2.models.usuario import UsuarioRead
from v2.models.evento import EventoProximo

router = APIRouter(
    prefix="/v2/portal",
    tags=["v2 - Portal Inicio"],
)


@router.get("/proximos-eventos", response_model=List[EventoProximo])
async def proximos_eventos(
    limit: int = Query(default=10, ge=1, le=100, description="Maximo de eventos a devolver"),
    days: Optional[int] = Query(default=None, ge=1, le=365, description="Solo eventos dentro de los proximos N dias"),
    current_usuario: UsuarioRead = Depends(get_current_usuario),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """
    Proximas fechas importantes segun el rol del usuario, ordenadas de la mas
    cercana a la mas lejana. Solo eventos cuya fecha es >= ahora. Si no hay
    eventos, devuelve 200 con lista vacia.

    - ESTUDIANTE: inscripciones a materias/examenes de sus programas, examenes en
      los que esta inscripto, e inicio/fin de dictado de lo que cursa.
    - DOCENTE: inicio/fin de dictado de sus asignaturas y mesas de examen a cargo.
    - ADMINISTRATIVO: todo lo anterior a nivel institucional, sin filtrar por
      asignacion personal.
    """
    return v2_services.proximosEventosService.get_eventos(
        current_usuario, session, limit=limit, days=days
    )
