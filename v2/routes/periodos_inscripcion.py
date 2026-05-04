from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session
from typing import List

from database.database import get_session
from database.services.filter.filters import Filter
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.periodo_inscripcion_materia import (
    PeriodoInscripcionMateriaCreate,
    PeriodoInscripcionMateriaUpdate,
    PeriodoInscripcionMateriaRead,
)

router = APIRouter(
    prefix="/v2/admin/periodos-inscripcion",
    tags=["v2 - Periodos de Inscripcion"],
)


@router.post("", response_model=PeriodoInscripcionMateriaRead, status_code=status.HTTP_201_CREATED)
async def create_periodo(
    data: PeriodoInscripcionMateriaCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        return v2_services.periodoInscripcionService.create(data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{periodo_id}", response_model=PeriodoInscripcionMateriaRead)
async def get_periodo(
    periodo_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    periodo = v2_services.periodoInscripcionService.get_by_id(periodo_id, session)
    if not periodo:
        raise HTTPException(status_code=404, detail="Periodo no encontrado")
    return periodo


@router.get("", response_model=List[PeriodoInscripcionMateriaRead])
async def list_periodos(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    filters = Filter(limit=limit, offset=offset, order_by="id", order_direction="desc")
    result = v2_services.periodoInscripcionService.get_with_filters_clean(session, filters)
    return result.get("data", [])


@router.post("/filters")
async def filter_periodos(
    filters: Filter,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return v2_services.periodoInscripcionService.get_with_filters_clean(session, filters)


@router.put("/{periodo_id}", response_model=PeriodoInscripcionMateriaRead)
async def update_periodo(
    periodo_id: int,
    data: PeriodoInscripcionMateriaUpdate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        return v2_services.periodoInscripcionService.update(periodo_id, data, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{periodo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_periodo(
    periodo_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        v2_services.periodoInscripcionService.delete(periodo_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
