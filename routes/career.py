from fastapi import APIRouter, HTTPException, status, Form, UploadFile, File, Depends, Query
from sqlmodel import Session
from typing import List, Optional
from datetime import datetime
from datetime import date
from database.database import Services, get_services, get_session
from database.services.filter.filters import Filter
from database.models.career import Area, CareerType, CareerCreate, CareerRead, CareerSimple,  CareerUpdate, CareerInList, CareerType, CareerReadOptimized
from database.models.user import UserRead
from database.services.auth.dependencies import get_current_user, require_admin_role
from exceptions import AppException

from utils.logger import show

router = APIRouter(prefix="/careers", tags=["Careers"])

@router.get("/types", response_model=List[CareerType])
def get_career_types(current_user: UserRead = Depends(require_admin_role)) -> List[Area]:
    """Obtener tipos de carreras (solo admins)"""
    try:
        return [career_type for career_type in CareerType]
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.get("/areas", response_model=List[Area])
def get_career_areas(current_user: UserRead = Depends(require_admin_role)) -> List[Area]:
    """Obtener areas de carreras (solo admins)"""
    try:
        return [area for area in Area]
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.post("/create", response_model=CareerRead, status_code=status.HTTP_201_CREATED)
async def create_career(
    name: str,
    subtitle: str,
    aboutCourse1: str,
    aboutCourse2: Optional[str],
    graduateProfile: Optional[str],
    studyPlan: Optional[str],
    image: UploadFile = File(...),
    careerType: str = "career",
    area: str = "it",
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> CareerRead:
    """Crear una nueva carrera (solo admins)"""
    try:
        # Asignar el usuario actual como creador
        creator = current_user.userId
        
        if image:
            image_url = None
            try:
                image_url = await services.supabaseService.upload_image(image, folder=f"images")
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error al subir la imagen: {str(e)}"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La imagen es requerida"
            )
                
        career_data: CareerCreate = CareerCreate(
            name=name,
            subtitle=subtitle,
            aboutCourse1=aboutCourse1,
            aboutCourse2=aboutCourse2,
            graduateProfile=graduateProfile,
            studyPlan=studyPlan,
            imageLink=image_url,
            careerType=careerType,
            area=area,
            creator=creator
        )
        
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
        services.supabaseService.rollback(image_url=image_url)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.get("/careers", response_model=List[CareerInList])
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error interno del servidor: {str(e)}"
        )
        
@router.get("/admin/careers", response_model=List[CareerInList])
async def get_careers_admin(
    offset: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerInList]:
    """Obtener lista de carreras (público)"""
    try:
        careers = services.careerService.get_careers_in_list_admin(session, offset, limit)
        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error interno del servidor: {str(e)}"
        )
        
# TODO: SACAR TESTIMONIOS, USUARIOS Y QUEDAR SOLO CON TITULO, AREA TIPO ABOUT1 LINK CAREERID 
@router.post("/filters", response_model=List[dict])
async def get_careers(
    filters: Filter,
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerInList]:
    """Obtener lista de carreras (público)"""
    try:
        careers = services.careerService.get_with_filters_clean(session, filters)
        published_careers = [career for career in careers if career.get("published")]
        return published_careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.post("/admin/filters", response_model=List[dict])
async def get_careers_admin(
    filters: Filter,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerInList]:
    """Obtener lista de carreras (público)"""
    try:
        careers = services.careerService.get_with_filters_clean(session, filters)
        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.get("/careers-optimized", response_model=List[CareerReadOptimized])
async def get_careers(
    offset: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerReadOptimized]:
    """Obtener lista de carreras (público)"""
    try:
        careers = services.careerService.get_careers_optimized(session, offset, limit)
        published_carreers = [career for career in careers if career.published]
        return published_carreers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.get("/admin/careers-optimized", response_model=List[CareerReadOptimized])
async def get_careers_admin(
    offset: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerReadOptimized]:
    """Obtener lista de carreras (público)"""
    try:
        careers = services.careerService.get_careers_optimized(session, offset, limit)
        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.get("/career-optimized/{career_id}", response_model=CareerReadOptimized)
async def get_careers_by_id(
    career_id: int,
    services: Services = Depends(get_services),
    session: Session = Depends(get_session),
) -> CareerReadOptimized:
    """Obtener lista de carreras (público)"""
    try:
        careers = services.careerService.get_career_optimized_by_id(session, career_id)
        published_careers = [career for career in careers if career.published]
        return published_careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error interno del servidor: {str(e)}"
        )
        
@router.get("/admin/career-optimized/{career_id}", response_model=CareerReadOptimized)
async def get_careers_by_id_admin(
    career_id: int,
    services: Services = Depends(get_services),
    current_user: UserRead = Depends(require_admin_role),
    session: Session = Depends(get_session),
) -> CareerReadOptimized:
    """Obtener lista de carreras (público)"""
    try:
        careers = services.careerService.get_career_optimized_by_id(session, career_id)
        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error interno del servidor: {str(e)}"
        )
        
@router.get("/public/random", response_model=List[CareerSimple], status_code=status.HTTP_200_OK)
async def get_random_careers(
    count: int = Query(4, ge=1, le=20, description="Número de carreras aleatorias a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerSimple]:
    """Obtener carreras aleatorias, una de cada área cuando sea posible"""
    try:
        careers = services.careerService.get_random_careers_by_area(session, count)
        
        if not careers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron carreras"
            )
        
        return careers
    except HTTPException:
        raise  # Re-lanzar HTTPExceptions
    except Exception as e:
        show(f"Error al obtener carreras aleatorias: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )
     
# TODO: Trae mucha info de testimonios y demas, sacar entidades relacionadas?   
@router.get("/public/random-for-area", response_model=List[CareerSimple], status_code=status.HTTP_200_OK)
async def get_careers_of_interest(
    count: int = Query(4, ge=1, le=20, description="Número de carreras a devolver"),
    areas: Optional[str] = Query(None, description="Áreas separadas por comas (ej: 'it,administration')"),
    include_career_id: Optional[int] = Query(None, description="ID de carrera específica a incluir obligatoriamente"),
    exclude_career_id: Optional[int] = Query(None, description="ID de carrera a excluir (útil para no mostrar la carrera actual)"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerSimple]:
    """
    Obtener carreras de interés con filtros flexibles
    - areas: Lista de áreas específicas (opcional)
    - include_career_id: Carrera que debe estar incluida sí o sí (opcional)
    - exclude_career_id: Carrera a excluir (opcional)
    """
    try:
        # Parsear áreas si se proporcionan
        area_list = None
        if areas:
            area_list = [area.strip().lower() for area in areas.split(',')]
            # Validar que las áreas existan
            valid_areas = [area.value for area in Area]
            invalid_areas = [area for area in area_list if area not in valid_areas]
            if invalid_areas:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Áreas inválidas: {', '.join(invalid_areas)}. Áreas válidas: {', '.join(valid_areas)}"
                )
        
        careers = services.careerService.get_careers_of_interest(
            session=session,
            count=count,
            areas=area_list,
            include_career_id=include_career_id,
            exclude_career_id=exclude_career_id
        )
        
        if not careers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron carreras que cumplan los criterios"
            )
        
        return careers
        
    except HTTPException:
        raise
    except Exception as e:
        show(f"Error al obtener carreras de interés: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

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

@router.get("/admin/type/{career_type}", response_model=List[CareerRead])
async def get_careers_by_type_admin(
    career_type: CareerType,
    current_user: UserRead = Depends(require_admin_role),
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
        published_careers = [career for career in careers if career.published]
        return published_careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/search-by-name", response_model=List[CareerRead])
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
async def get_career_by_id_admin(
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

@router.get("/admin/{career_id}", response_model=CareerRead)
async def get_career_by_id_admin(
    career_id: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> CareerRead:
    """Obtener una carrera por ID (público)"""
    try:
        career = services.careerService.get_career_by_id_admin(career_id, session)
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
        if not services.careerService.get_career_by_id(career_id, session):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrera no encontrada"
            )
        
        # Actualizar la carrera
        updated_career = services.careerService.update_career(career_id, career_update, session)
        
        show(f"Carrera {career_id} actualizada por usuario {current_user.email}")
        
        return updated_career
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except HTTPException:
        raise  # Re-raise HTTPException
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )
        
@router.put("/image/{career_id}", response_model=CareerRead)
async def update_career(
    career_id: int,
    image: UploadFile = File(...),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> CareerRead:
    """Actualizar una carrera (solo admins)"""
    try:
        if not image or image.filename == "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La imagen es requerida"
            )
        
        # Subir la imagen
        image_url = None
        try:
            image_url = await services.supabaseService.upload_image(image, folder=f"images")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al subir la imagen: {str(e)}"
            )
        
        # Verificar que la carrera exista
        current_career = services.careerService.get_career_by_id(career_id, session)
        if not current_career:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrera no encontrada"
            )
            
        # Actualizar el enlace de la imagen
        career_update = CareerUpdate(imagesLink=image_url)
        # Actualizar la carrera
        updated_career = services.careerService.update_career(career_id, career_update, session)
        
        show(f"Carrera {career_id} actualizada por usuario {current_user.email}")
        
        return updated_career
        
    except ValueError as e:
        services.supabaseService.rollback(image_url=image_url)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except AppException as e:
        services.supabaseService.rollback(image_url=image_url)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except HTTPException:
        services.supabaseService.rollback(image_url=image_url)
        raise  # Re-raise HTTPException
    except Exception as e:
        services.supabaseService.rollback(image_url=image_url)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

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

# BUG: Al eliminar si la carrera tiene testimonios, estos no se eliminan
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
    except Exception as e:
        show(f"Error al eliminar carrera {career_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

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