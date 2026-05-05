from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session
from typing import List

from database.database import get_session
from database.services.filter.filters import Filter
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.programa import ProgramaCreate, ProgramaUpdate, ProgramaRead

router = APIRouter(
    prefix="/v2/admin/programas",
    tags=["v2 - Programas"],
)


@router.post("", response_model=ProgramaRead, status_code=status.HTTP_201_CREATED)
async def create_programa(
    data: ProgramaCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Crear un programa academico (carrera, curso, taller o diplomatura)."""
    return v2_services.programaService.create(data, session)


@router.get("/{programa_id}", response_model=ProgramaRead)
async def get_programa(
    programa_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Obtener un programa por su ID."""
    programa = v2_services.programaService.get_by_id(programa_id, session)
    if not programa:
        raise HTTPException(status_code=404, detail="Programa no encontrado")
    return programa


@router.get("/{programa_id}/con-materias")
async def get_programa_con_materias(
    programa_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Obtener un programa con la lista completa de sus materias ordenadas por semestre."""
    programa = v2_services.programaService.get_con_materias(programa_id, session)
    if not programa:
        raise HTTPException(status_code=404, detail="Programa no encontrado")
    return programa


@router.get("", response_model=List[ProgramaRead])
async def list_programas(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Listar programas con paginacion basica."""
    filters = Filter(limit=limit, offset=offset, order_by="id", order_direction="asc")
    result = v2_services.programaService.get_with_filters_clean(session, filters)
    return result.get("data", [])


@router.post("/filters")
async def filter_programas(
    filters: Filter,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Buscar programas con filtros avanzados (condiciones, ordenamiento, paginacion)."""
    return v2_services.programaService.get_with_filters_clean(session, filters)


@router.put("/{programa_id}", response_model=ProgramaRead)
async def update_programa(
    programa_id: int,
    data: ProgramaUpdate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Actualizar un programa existente. Solo se modifican los campos enviados."""
    try:
        return v2_services.programaService.update(programa_id, data, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{programa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_programa(
    programa_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Eliminar un programa. Falla si tiene materias o inscripciones asociadas."""
    try:
        v2_services.programaService.delete(programa_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
