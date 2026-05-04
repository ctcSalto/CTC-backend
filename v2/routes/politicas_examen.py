from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session
from typing import List

from database.database import get_session
from database.services.filter.filters import Filter
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.politica_examen import (
    PoliticaExamenCreate,
    PoliticaExamenUpdate,
    PoliticaExamenRead,
)

router = APIRouter(
    prefix="/v2/admin/politicas-examen",
    tags=["v2 - Politicas de Examen"],
)


@router.post("", response_model=PoliticaExamenRead, status_code=status.HTTP_201_CREATED)
async def create_politica(
    data: PoliticaExamenCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return v2_services.politicaExamenService.create(data, session)


@router.get("/{politica_id}", response_model=PoliticaExamenRead)
async def get_politica(
    politica_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    politica = v2_services.politicaExamenService.get_by_id(politica_id, session)
    if not politica:
        raise HTTPException(status_code=404, detail="Politica de examen no encontrada")
    return politica


@router.get("", response_model=List[PoliticaExamenRead])
async def list_politicas(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    filters = Filter(limit=limit, offset=offset, order_by="id", order_direction="asc")
    result = v2_services.politicaExamenService.get_with_filters_clean(session, filters)
    return result.get("data", [])


@router.post("/filters")
async def filter_politicas(
    filters: Filter,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return v2_services.politicaExamenService.get_with_filters_clean(session, filters)


@router.put("/{politica_id}", response_model=PoliticaExamenRead)
async def update_politica(
    politica_id: int,
    data: PoliticaExamenUpdate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        return v2_services.politicaExamenService.update(politica_id, data, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{politica_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_politica(
    politica_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        v2_services.politicaExamenService.delete(politica_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
