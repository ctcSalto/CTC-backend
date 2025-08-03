from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlmodel import Session
from typing import List, Optional
from database.database import Services, get_services, get_session
from database.models.career import CareerCreate, CareerRead, CareerUpdate, CareerInList, Area, CareerType
from database.models.user import UserRead
from database.services.auth.dependencies import get_current_user, require_admin_role
from exceptions import AppException

from utils.logger import show

router = APIRouter(prefix="/careers", tags=["Careers"])

@router.post("/", response_model=CareerRead, status_code=status.HTTP_201_CREATED)
async def create_career(
    career_data: CareerCreate,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> CareerRead:
    """Crear una nueva carrera (solo admins)"""
    try:
        # Asignar el usuario actual como creador
        career_data.creator = current_user.userId
        
        # Crear la carrera
        new_career = services.careerService.create_career(career_data, session)
        
        show(f"Carrera creada: {new_career.name} por usuario {current_user.email}")
        
        if not new_career:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear la carrera"
            )
        
        return new_career
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/", response_model=List[CareerInList])
async def get_careers(
    offset: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerInList]:
    """Obtener lista de carreras (público)"""
    try:
        careers = services.careerService.get_careers_in_list(session, offset, limit)
        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/published", response_model=List[CareerRead])
async def get_published_careers(
    offset: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerRead]:
    """Obtener solo carreras publicadas (público)"""
    try:
        careers = services.careerService.get_published_careers(session, offset, limit)
        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/admin", response_model=List[CareerRead])
async def get_all_careers_admin(
    offset: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerRead]:
    """Obtener todas las carreras con información completa (solo admins)"""
    try:
        careers = services.careerService.get_careers(session, offset, limit)
        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/area/{area}", response_model=List[CareerRead])
async def get_careers_by_area(
    area: Area,
    offset: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerRead]:
    """Obtener carreras por área (público)"""
    try:
        careers = services.careerService.get_careers_by_area(area.value, session, offset, limit)
        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/type/{career_type}", response_model=List[CareerRead])
async def get_careers_by_type(
    career_type: CareerType,
    offset: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerRead]:
    """Obtener carreras por tipo (público)"""
    try:
        careers = services.careerService.get_careers_by_type(career_type.value, session, offset, limit)
        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/search", response_model=List[CareerRead])
async def search_careers(
    q: str = Query(..., min_length=1, description="Término de búsqueda"),
    offset: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerRead]:
    """Buscar carreras por nombre (público)"""
    try:
        careers = services.careerService.search_careers_by_name(q, session, offset, limit)
        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/{career_id}", response_model=CareerRead)
async def get_career_by_id(
    career_id: int,
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> CareerRead:
    """Obtener una carrera por ID (público)"""
    try:
        career = services.careerService.get_career_by_id(career_id, session)
        if not career:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrera no encontrada"
            )
        return career
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.put("/{career_id}", response_model=CareerRead)
async def update_career(
    career_id: int,
    career_update: CareerUpdate,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> CareerRead:
    """Actualizar una carrera (solo admins)"""
    try:
        # Asignar el usuario actual como modificador
        career_update.modifier = current_user.userId
        
        updated_career = services.careerService.update_career(career_id, career_update, session)
        
        show(f"Carrera {career_id} actualizada por usuario {current_user.email}")
        
        if not updated_career:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrera no encontrada"
            )
        
        return updated_career
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.patch("/{career_id}/publish", response_model=CareerRead)
async def publish_career(
    career_id: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> CareerRead:
    """Publicar una carrera (solo admins)"""
    try:
        career = services.careerService.publish_career(career_id, session)
        
        show(f"Carrera {career_id} publicada por usuario {current_user.email}")
        
        if not career:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrera no encontrada"
            )
        
        return career
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.patch("/{career_id}/unpublish", response_model=CareerRead)
async def unpublish_career(
    career_id: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> CareerRead:
    """Despublicar una carrera (solo admins)"""
    try:
        career = services.careerService.unpublish_career(career_id, session)
        
        show(f"Carrera {career_id} despublicada por usuario {current_user.email}")
        
        if not career:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrera no encontrada"
            )
        
        return career
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.delete("/{career_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_career(
    career_id: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
):
    """Eliminar una carrera (solo admins)"""
    try:
        success = services.careerService.delete_career(career_id, session)
        
        show(f"Carrera {career_id} eliminada por usuario {current_user.email}")
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrera no encontrada"
            )
        
        return None
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/stats/count", response_model=dict)
async def get_career_stats(
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> dict:
    """Obtener estadísticas de carreras (solo admins)"""
    try:
        total_count = services.careerService.get_career_count(session)
        published_count = services.careerService.get_published_career_count(session)
        
        return {
            "total_careers": total_count,
            "published_careers": published_count,
            "draft_careers": total_count - published_count
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)