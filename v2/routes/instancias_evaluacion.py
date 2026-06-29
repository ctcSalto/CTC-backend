from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List

from database.database import get_session
from database.services.filter.filters import Filter
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.materia_instancia_evaluacion import (
    InstanciaEvaluacionCreate,
    InstanciaEvaluacionUpdate,
    InstanciaEvaluacionRead,
)

router = APIRouter(
    prefix="/v2/admin/instancias-evaluacion",
    tags=["v2 - Instancias de Evaluacion"],
)


@router.post("", response_model=InstanciaEvaluacionRead, status_code=status.HTTP_201_CREATED)
async def create_instancia(
    data: InstanciaEvaluacionCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Crear una instancia de evaluacion (parcial, trabajo, etc.) asociada a una instancia de cursado."""
    try:
        return v2_services.instanciaEvaluacionService.create(data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/instancia-cursado/{instancia_cursado_id}", response_model=List[InstanciaEvaluacionRead])
async def get_instancias_by_instancia_cursado(
    instancia_cursado_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Obtener instancias de evaluación de una instancia de cursado."""
    return v2_services.instanciaEvaluacionService.get_by_instancia_cursado(
        instancia_cursado_id, session
    )


@router.post("/filters")
async def filter_instancias(
    filters: Filter,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Buscar instancias de evaluacion con filtros avanzados."""
    return v2_services.instanciaEvaluacionService.get_with_filters_clean(session, filters)


@router.put("/{instancia_id}", response_model=InstanciaEvaluacionRead)
async def update_instancia(
    instancia_id: int,
    data: InstanciaEvaluacionUpdate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Actualizar una instancia de evaluacion (nombre, ponderacion, fecha, etc.)."""
    try:
        return v2_services.instanciaEvaluacionService.update(instancia_id, data, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{instancia_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instancia(
    instancia_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Eliminar una instancia de evaluacion. Falla si tiene calificaciones registradas."""
    try:
        v2_services.instanciaEvaluacionService.delete(instancia_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
