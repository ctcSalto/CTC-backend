from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.previatura import PreviaturaCreate, PreviaturaRead, PreviaturaConNombres

router = APIRouter(
    prefix="/v2/admin/previaturas",
    tags=["v2 - Previaturas"],
)


@router.post("", response_model=PreviaturaRead, status_code=status.HTTP_201_CREATED)
async def create_previatura(
    data: PreviaturaCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        return v2_services.previaturaService.create(data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/materia/{materia_id}", response_model=List[PreviaturaConNombres])
async def get_previaturas_materia(
    materia_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return v2_services.previaturaService.get_by_materia(materia_id, session)


@router.get("/malla/{programa_id}")
async def get_malla_programa(
    programa_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    # Verificar que el programa exista
    programa = v2_services.programaService.get_by_id(programa_id, session)
    if not programa:
        raise HTTPException(status_code=404, detail="Programa no encontrado")

    return v2_services.previaturaService.get_malla_programa(programa_id, session)


@router.delete("/{previatura_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_previatura(
    previatura_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        v2_services.previaturaService.delete(previatura_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
