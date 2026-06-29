from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session
from typing import List

from database.database import get_session
from database.services.filter.filters import Filter
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.materia import MateriaCreate, MateriaUpdate, MateriaRead

router = APIRouter(
    prefix="/v2/admin/materias",
    tags=["v2 - Materias"],
)


@router.post("", response_model=MateriaRead, status_code=status.HTTP_201_CREATED)
async def create_materia(
    data: MateriaCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Crear una materia nueva asociada a un programa. Valida codigo unico dentro del programa."""
    try:
        return v2_services.materiaService.create(data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/por-programa/{programa_id}", response_model=List[MateriaRead])
async def get_materias_por_programa(
    programa_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Listar todas las materias de un programa, ordenadas por semestre."""
    return v2_services.materiaService.get_by_programa(programa_id, session)


@router.get("/{materia_id}", response_model=MateriaRead)
async def get_materia(
    materia_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Obtener una materia por su ID."""
    materia = v2_services.materiaService.get_by_id(materia_id, session)
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    return materia


@router.get("", response_model=List[MateriaRead])
async def list_materias(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Listar materias con paginacion basica."""
    filters = Filter(limit=limit, offset=offset, order_by="id", order_direction="asc")
    result = v2_services.materiaService.get_with_filters_clean(session, filters)
    return result.get("data", [])


@router.post("/filters")
async def filter_materias(
    filters: Filter,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Buscar materias con filtros avanzados (condiciones, ordenamiento, paginacion)."""
    return v2_services.materiaService.get_with_filters_clean(session, filters)


@router.put("/{materia_id}", response_model=MateriaRead)
async def update_materia(
    materia_id: int,
    data: MateriaUpdate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Actualizar una materia existente. Solo se modifican los campos enviados."""
    try:
        return v2_services.materiaService.update(materia_id, data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{materia_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_materia(
    materia_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Eliminar una materia. Falla si tiene inscripciones o instancias asociadas."""
    try:
        v2_services.materiaService.delete(materia_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
