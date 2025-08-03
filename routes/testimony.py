from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlmodel import Session
from typing import List, Optional
from database.database import Services, get_services, get_session
from database.models.testimony import (
    TestimonyCreate, 
    TestimonyRead, 
    TestimonyUpdate, 
    TestimonyInList, 
    TestimonyPublic
)
from database.models.user import UserRead
from database.services.auth.dependencies import get_current_user, require_admin_role
from exceptions import AppException
from sqlalchemy.exc import NoResultFound

from utils.logger import show

router = APIRouter(prefix="/testimonies", tags=["Testimonies"])

# =================== ENDPOINTS PÚBLICOS ===================

@router.get("/public", response_model=List[TestimonyPublic], status_code=status.HTTP_200_OK)
async def get_public_testimonies(
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[TestimonyPublic]:
    """Obtener testimonios públicos con paginación"""
    try:
        testimonies = services.testimonyService.get_testimonies_public(session, offset, limit)
        return testimonies
    except Exception as e:
        show(f"Error al obtener testimonios públicos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/public/latest", response_model=List[TestimonyPublic], status_code=status.HTTP_200_OK)
async def get_latest_testimonies(
    limit: int = Query(5, ge=1, le=20, description="Número de testimonios recientes a obtener"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[TestimonyPublic]:
    """Obtener los testimonios más recientes para homepage"""
    try:
        testimonies = services.testimonyService.get_latest_testimonies(session, limit)
        return testimonies
    except Exception as e:
        show(f"Error al obtener testimonios recientes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/public/career/{career_id}", response_model=List[TestimonyPublic], status_code=status.HTTP_200_OK)
async def get_public_testimonies_by_career(
    career_id: int,
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[TestimonyPublic]:
    """Obtener testimonios públicos por carrera"""
    try:
        testimonies = services.testimonyService.get_testimonies_by_career_public(career_id, session, offset, limit)
        return testimonies
    except Exception as e:
        show(f"Error al obtener testimonios por carrera: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# =================== ENDPOINTS ADMINISTRATIVOS ===================

@router.post("/", response_model=TestimonyRead, status_code=status.HTTP_201_CREATED)
async def create_testimony(
    testimony_data: TestimonyCreate,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> TestimonyRead:
    """Crear un nuevo testimonio (solo administradores)"""
    try:
        # Asignar el usuario actual como creador
        testimony_data.creator = current_user.userId
        
        new_testimony = services.testimonyService.create_testimony(testimony_data, session)
        
        show(f"Testimonio creado: {new_testimony}")
        
        if not new_testimony:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear el testimonio"
            )
        
        return new_testimony
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/", response_model=List[TestimonyRead], status_code=status.HTTP_200_OK)
async def get_testimonies(
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[TestimonyRead]:
    """Obtener todos los testimonios con detalles completos (solo administradores)"""
    try:
        testimonies = services.testimonyService.get_testimonies(session, offset, limit)
        return testimonies
    except Exception as e:
        show(f"Error al obtener testimonios: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/list", response_model=List[TestimonyInList], status_code=status.HTTP_200_OK)
async def get_testimonies_list(
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[TestimonyInList]:
    """Obtener lista simplificada de testimonios (solo administradores)"""
    try:
        testimonies = services.testimonyService.get_testimonies_in_list(session, offset, limit)
        return testimonies
    except Exception as e:
        show(f"Error al obtener lista de testimonios: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/{testimony_id}", response_model=TestimonyRead, status_code=status.HTTP_200_OK)
async def get_testimony_by_id(
    testimony_id: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> TestimonyRead:
    """Obtener un testimonio por ID (solo administradores)"""
    try:
        testimony = services.testimonyService.get_testimony_by_id(testimony_id, session)
        
        if not testimony:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Testimonio no encontrado"
            )
        
        return testimony
        
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Testimonio no encontrado"
        )
    except Exception as e:
        show(f"Error al obtener testimonio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.put("/{testimony_id}", response_model=TestimonyRead, status_code=status.HTTP_200_OK)
async def update_testimony(
    testimony_id: int,
    testimony_update: TestimonyUpdate,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> TestimonyRead:
    """Actualizar un testimonio (solo administradores)"""
    try:
        # Asignar el usuario actual como modificador
        testimony_update.modifier = current_user.userId
        
        updated_testimony = services.testimonyService.update_testimony(testimony_id, testimony_update, session)
        
        show(f"Testimonio actualizado: {updated_testimony}")
        
        return updated_testimony
        
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Testimonio no encontrado"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.delete("/{testimony_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_testimony(
    testimony_id: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
):
    """Eliminar un testimonio (solo administradores)"""
    try:
        success = services.testimonyService.delete_testimony(testimony_id, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Testimonio no encontrado"
            )
        
        show(f"Testimonio {testimony_id} eliminado")
        
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Testimonio no encontrado"
        )
    except Exception as e:
        show(f"Error al eliminar testimonio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# =================== ENDPOINTS DE BÚSQUEDA ===================

@router.get("/search/text", response_model=List[TestimonyRead], status_code=status.HTTP_200_OK)
async def search_testimonies_by_text(
    q: str = Query(..., min_length=3, description="Término de búsqueda en el texto"),
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[TestimonyRead]:
    """Buscar testimonios por contenido de texto (solo administradores)"""
    try:
        testimonies = services.testimonyService.search_testimonies_by_text(q, session, offset, limit)
        return testimonies
    except Exception as e:
        show(f"Error al buscar testimonios por texto: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/search/name", response_model=List[TestimonyRead], status_code=status.HTTP_200_OK)
async def search_testimonies_by_name(
    q: str = Query(..., min_length=2, description="Término de búsqueda en nombre o apellido"),
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[TestimonyRead]:
    """Buscar testimonios por nombre o apellido (solo administradores)"""
    try:
        testimonies = services.testimonyService.search_testimonies_by_name(q, session, offset, limit)
        return testimonies
    except Exception as e:
        show(f"Error al buscar testimonios por nombre: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/career/{career_id}", response_model=List[TestimonyRead], status_code=status.HTTP_200_OK)
async def get_testimonies_by_career(
    career_id: int,
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[TestimonyRead]:
    """Obtener testimonios por carrera (solo administradores)"""
    try:
        testimonies = services.testimonyService.get_testimonies_by_career(career_id, session, offset, limit)
        return testimonies
    except Exception as e:
        show(f"Error al obtener testimonios por carrera: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/creator/{creator_id}", response_model=List[TestimonyRead], status_code=status.HTTP_200_OK)
async def get_testimonies_by_creator(
    creator_id: int,
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[TestimonyRead]:
    """Obtener testimonios creados por un usuario específico (solo administradores)"""
    try:
        testimonies = services.testimonyService.get_testimonies_by_creator(creator_id, session, offset, limit)
        return testimonies
    except Exception as e:
        show(f"Error al obtener testimonios por creador: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# =================== ENDPOINTS DE ESTADÍSTICAS ===================

@router.get("/stats/general", status_code=status.HTTP_200_OK)
async def get_testimonies_stats(
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> dict:
    """Obtener estadísticas generales de testimonios (solo administradores)"""
    try:
        stats = services.testimonyService.get_testimonies_stats(session)
        return stats
    except Exception as e:
        show(f"Error al obtener estadísticas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/stats/count", status_code=status.HTTP_200_OK)
async def get_testimonies_count(
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> dict:
    """Obtener conteo total de testimonios (solo administradores)"""
    try:
        count = services.testimonyService.get_testimony_count(session)
        return {"total_testimonies": count}
    except Exception as e:
        show(f"Error al obtener conteo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# =================== ENDPOINTS DE UTILIDAD ===================

@router.delete("/bulk/career/{career_id}", status_code=status.HTTP_200_OK)
async def bulk_delete_testimonies_by_career(
    career_id: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> dict:
    """Eliminar todos los testimonios de una carrera específica (solo administradores)"""
    try:
        deleted_count = services.testimonyService.bulk_delete_by_career(career_id, session)
        
        show(f"{deleted_count} testimonios eliminados de la carrera {career_id}")
        
        return {"deleted_count": deleted_count, "career_id": career_id}
        
    except Exception as e:
        show(f"Error al eliminar testimonios por carrera: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )