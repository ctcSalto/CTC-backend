from fastapi import APIRouter, HTTPException, status, UploadFile, File, Depends, Query
from sqlmodel import Session
from typing import List, Optional
from datetime import datetime
from database.database import Services, get_services, get_session
from database.services.filter.filters import Filter
from database.models.career import Area, CareerType, CareerCreate, CareerRead, CareerSimple,  CareerUpdate, CareerInList, CareerReadOptimized, CarrerDropdown, CareerCreateForm
from database.models.user import UserRead
from database.services.auth.dependencies import require_admin_role
from exceptions import AppException

from utils.logger import show

import os
from zoneinfo import ZoneInfo

def get_uruguay_tz():
    """Lee la variable cada vez que se llama"""
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)

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
    career_form: CareerCreateForm = Depends(CareerCreateForm.as_form),
    image: UploadFile = File(...),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> CareerRead:
    """Crear una nueva carrera (solo admins)"""
    try:
        creator = current_user.userId
        
        print(f"Es para publicar: {career_form.published}")
        
        # Upload image
        image_url = None
        try:
            image_url = await services.supabaseService.upload_image(image, folder="images")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al subir la imagen: {str(e)}"
            )
                
        career_data = CareerCreate(
            name=career_form.name,
            subtitle=career_form.subtitle,
            aboutCourse1=career_form.aboutCourse1,
            aboutCourse2=career_form.aboutCourse2,
            graduateProfile=career_form.graduateProfile,
            studyPlan=career_form.studyPlan,
            imageLink=image_url,
            careerType=career_form.careerType,
            area=career_form.area,
            creator=creator,
            published=career_form.published,
            publicationDate=datetime.now(get_uruguay_tz()).date() if career_form.published else None,
            
            duration=career_form.duration,
            hourlyLoad=career_form.hourlyLoad,
            cost=career_form.cost,
            startClasses=career_form.startClasses,
            certificationType=career_form.certificationType
        )
        
        # Crear la carrera
        new_career = services.careerService.create_career(career_data, session)

        show(f"Carrera creada: {new_career.name} por usuario {current_user.email}")

        if not new_career:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear la carrera"
            )

        # Invalidate all career caches
        services.cacheService.invalidate_all_careers()
        show(f"[CACHE] Invalidated all career caches after creating career {new_career.careerId}")

        return new_career
        
    except ValueError as e:
        if image_url:
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
    """Obtener lista de carreras públicas - con cache Redis"""
    try:
        # Try to get from cache first
        cached_careers = services.cacheService.get_cached_careers_list(offset, limit)

        if cached_careers is not None:
            show(f"[CACHE HIT] Careers list (offset={offset}, limit={limit})")
            return cached_careers

        # Cache miss - get from database
        show(f"[CACHE MISS] Careers list (offset={offset}, limit={limit}) - querying DB")
        careers = services.careerService.get_careers_in_list(session, offset, limit)

        # Update cache
        services.cacheService.cache_careers_list(offset, limit, careers)

        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )
      
      
@router.get("/admin/dropdown", response_model=List[CarrerDropdown])  # Cambiar a CarrerDropdown
async def get_careers_dropdown_admin(
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CarrerDropdown]:  # Cambiar el tipo de retorno
    """Obtener lista de carreras para dropdown (solo id y nombre) - con cache Redis"""
    try:
        # Try to get from cache first
        cached_dropdown = services.cacheService.get_cached_generic(
            services.cacheService.CAREERS_DROPDOWN_PREFIX,
            "all",
            CarrerDropdown
        )

        if cached_dropdown is not None:
            show("[CACHE HIT] Careers dropdown")
            return cached_dropdown

        # Cache miss - get from database
        show("[CACHE MISS] Careers dropdown - querying DB")
        careers = services.careerService.get_careers_for_dropdown(session)

        # Update cache
        services.cacheService.cache_generic(
            services.cacheService.CAREERS_DROPDOWN_PREFIX,
            "all",
            careers
        )

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
    """Obtener lista de carreras admin - con cache Redis"""
    try:
        # Try to get from cache first
        cached_careers = services.cacheService.get_cached_generic(
            services.cacheService.CAREERS_LIST_PREFIX,
            f"admin:{offset}:{limit}",
            CareerInList
        )

        if cached_careers is not None:
            show(f"[CACHE HIT] Admin careers list (offset={offset}, limit={limit})")
            return cached_careers

        # Cache miss - get from database
        show(f"[CACHE MISS] Admin careers list (offset={offset}, limit={limit}) - querying DB")
        careers = services.careerService.get_careers_in_list_admin(session, offset, limit)

        # Update cache
        services.cacheService.cache_generic(
            services.cacheService.CAREERS_LIST_PREFIX,
            f"admin:{offset}:{limit}",
            careers
        )

        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )
        
# TODO: SACAR TESTIMONIOS, USUARIOS Y QUEDAR SOLO CON TITULO, AREA TIPO ABOUT1 LINK CAREERID 
@router.post("/public/filters")
async def get_careers_with_filters(
    filters: Filter,
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
):
    """Obtener lista de carreras (público)"""
    try:
        careers = services.careerService.get_with_filters_clean_public(session, filters)
        return careers
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.post("/admin/filters")
async def get_careers_admin_filters(
    filters: Filter,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
):
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
async def get_careers_optimized(
    offset: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[CareerReadOptimized]:
    """Obtener lista de carreras publicadas (público) - con cache Redis"""
    try:
        # Try to get from cache first
        cached_careers = services.cacheService.get_cached_careers_optimized(
            offset=offset,
            limit=limit,
            published_only=True
        )

        if cached_careers is not None:
            show(f"[CACHE HIT] Careers optimized (offset={offset}, limit={limit})")
            return cached_careers

        # Cache miss - get from database
        show(f"[CACHE MISS] Careers optimized (offset={offset}, limit={limit}) - querying DB")
        careers = services.careerService.get_careers_optimized(session, offset, limit)
        published_careers = [career for career in careers if career.published]

        # Update cache
        services.cacheService.cache_careers_optimized(
            offset=offset,
            limit=limit,
            published_only=True,
            careers=published_careers
        )

        return published_careers
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
    """Obtener lista de carreras para admin - con cache Redis"""
    try:
        # Try to get from cache first
        cached_careers = services.cacheService.get_cached_careers_optimized(
            offset=offset,
            limit=limit,
            published_only=False
        )

        if cached_careers is not None:
            show(f"[CACHE HIT] Admin careers optimized (offset={offset}, limit={limit})")
            return cached_careers

        # Cache miss - get from database
        show(f"[CACHE MISS] Admin careers optimized (offset={offset}, limit={limit}) - querying DB")
        careers = services.careerService.get_careers_optimized(session, offset, limit)

        if not careers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carreras no encontradas"
            )

        # Update cache
        services.cacheService.cache_careers_optimized(
            offset=offset,
            limit=limit,
            published_only=False,
            careers=careers
        )

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
    """Obtener carrera por ID (público) - con cache Redis"""
    try:
        # Try to get from cache first
        cached_career = services.cacheService.get_cached_career_optimized(career_id)

        if cached_career is not None:
            # Verify it's published before returning
            if cached_career.published:
                show(f"[CACHE HIT] Career {career_id}")
                return cached_career

        # Cache miss or not published - get from database
        show(f"[CACHE MISS] Career {career_id} - querying DB")
        career = services.careerService.get_public_career_optimized_by_id(session, career_id)

        if not career:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrera no encontrada o no disponible públicamente"
            )

        # Update cache
        services.cacheService.cache_career_optimized(career_id, career)

        return career
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
    """Obtener carreras aleatorias, una de cada área cuando sea posible - con cache Redis"""
    try:
        # Try to get from cache first
        cached_careers = services.cacheService.get_cached_simple_careers(f"random:{count}")

        if cached_careers is not None:
            show(f"[CACHE HIT] Random careers (count={count})")
            return cached_careers

        # Cache miss - get from database
        show(f"[CACHE MISS] Random careers (count={count}) - querying DB")
        careers = services.careerService.get_random_careers_by_area(session, count)

        if not careers:
            return []

        # Update cache with shorter TTL for random results (5 minutes)
        services.cacheService.cache_simple_careers(f"random:{count}", careers, ttl=300)

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
    Obtener carreras de interés con filtros flexibles - con cache Redis
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

        # Build cache key based on parameters
        cache_key = f"interest:{count}:{areas or 'all'}:{include_career_id or 'none'}:{exclude_career_id or 'none'}"

        # Try to get from cache first
        cached_careers = services.cacheService.get_cached_simple_careers(cache_key)

        if cached_careers is not None:
            show(f"[CACHE HIT] Careers of interest ({cache_key})")
            return cached_careers

        # Cache miss - get from database
        show(f"[CACHE MISS] Careers of interest ({cache_key}) - querying DB")
        careers = services.careerService.get_careers_of_interest(
            session=session,
            count=count,
            areas=area_list,
            include_career_id=include_career_id,
            exclude_career_id=exclude_career_id
        )

        if not careers:
            return []

        # Update cache with shorter TTL (5 minutes) for dynamic results
        services.cacheService.cache_simple_careers(cache_key, careers, ttl=300)

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
    """Obtener solo carreras publicadas (público) - con cache Redis"""
    try:
        # Try to get from cache first
        from database.models.career import CareerRead
        cached_careers = services.cacheService.get_cached_generic(
            services.cacheService.CAREERS_PUBLISHED_PREFIX,
            f"full:{offset}:{limit}",
            CareerRead
        )

        if cached_careers is not None:
            show(f"[CACHE HIT] Published careers (offset={offset}, limit={limit})")
            return cached_careers

        # Cache miss - get from database
        show(f"[CACHE MISS] Published careers (offset={offset}, limit={limit}) - querying DB")
        careers = services.careerService.get_published_careers(session, offset, limit)

        # Update cache
        services.cacheService.cache_generic(
            services.cacheService.CAREERS_PUBLISHED_PREFIX,
            f"full:{offset}:{limit}",
            careers
        )

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
    """Obtener todas las carreras con información completa (solo admins) - con cache Redis"""
    try:
        # Try to get from cache first
        from database.models.career import CareerRead
        cached_careers = services.cacheService.get_cached_generic(
            services.cacheService.CAREERS_LIST_PREFIX,
            f"admin_full:{offset}:{limit}",
            CareerRead
        )

        if cached_careers is not None:
            show(f"[CACHE HIT] Admin all careers (offset={offset}, limit={limit})")
            return cached_careers

        # Cache miss - get from database
        show(f"[CACHE MISS] Admin all careers (offset={offset}, limit={limit}) - querying DB")
        careers = services.careerService.get_careers(session, offset, limit)

        # Update cache
        services.cacheService.cache_generic(
            services.cacheService.CAREERS_LIST_PREFIX,
            f"admin_full:{offset}:{limit}",
            careers
        )

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
    """Obtener carreras por área (público) - con cache Redis"""
    try:
        # Try to get from cache first
        from database.models.career import CareerRead
        cached_careers = services.cacheService.get_cached_generic(
            services.cacheService.CAREERS_BY_AREA_PREFIX,
            f"{area.value}:{offset}:{limit}",
            CareerRead
        )

        if cached_careers is not None:
            show(f"[CACHE HIT] Careers by area {area.value} (offset={offset}, limit={limit})")
            return cached_careers

        # Cache miss - get from database
        show(f"[CACHE MISS] Careers by area {area.value} (offset={offset}, limit={limit}) - querying DB")
        careers = services.careerService.get_careers_by_area(area.value, session, offset, limit)

        # Update cache
        services.cacheService.cache_generic(
            services.cacheService.CAREERS_BY_AREA_PREFIX,
            f"{area.value}:{offset}:{limit}",
            careers
        )

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
    """Obtener carreras por tipo admin - con cache Redis"""
    try:
        # Try to get from cache first
        from database.models.career import CareerRead
        cached_careers = services.cacheService.get_cached_generic(
            services.cacheService.CAREERS_BY_TYPE_PREFIX,
            f"admin:{career_type.value}:{offset}:{limit}",
            CareerRead
        )

        if cached_careers is not None:
            show(f"[CACHE HIT] Admin careers by type {career_type.value} (offset={offset}, limit={limit})")
            return cached_careers

        # Cache miss - get from database
        show(f"[CACHE MISS] Admin careers by type {career_type.value} (offset={offset}, limit={limit}) - querying DB")
        careers = services.careerService.get_careers_by_type(career_type.value, session, offset, limit)

        # Update cache
        services.cacheService.cache_generic(
            services.cacheService.CAREERS_BY_TYPE_PREFIX,
            f"admin:{career_type.value}:{offset}:{limit}",
            careers
        )

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
    """Obtener carreras por tipo (público) - con cache Redis"""
    try:
        # Try to get from cache first
        from database.models.career import CareerRead
        cached_careers = services.cacheService.get_cached_generic(
            services.cacheService.CAREERS_BY_TYPE_PREFIX,
            f"public:{career_type.value}:{offset}:{limit}",
            CareerRead
        )

        if cached_careers is not None:
            show(f"[CACHE HIT] Public careers by type {career_type.value} (offset={offset}, limit={limit})")
            return cached_careers

        # Cache miss - get from database
        show(f"[CACHE MISS] Public careers by type {career_type.value} (offset={offset}, limit={limit}) - querying DB")
        careers = services.careerService.get_careers_by_type(career_type.value, session, offset, limit)
        published_careers = [career for career in careers if career.published]

        # Update cache
        services.cacheService.cache_generic(
            services.cacheService.CAREERS_BY_TYPE_PREFIX,
            f"public:{career_type.value}:{offset}:{limit}",
            published_careers
        )

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
async def get_career_by_id_public(
    career_id: int,
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> CareerRead:
    """Obtener una carrera por ID (público) - con cache Redis"""
    try:
        # Try to get from cache first
        from database.models.career import CareerRead
        cached_career = services.cacheService.get_cached_generic(
            services.cacheService.CAREER_PREFIX,
            f"full:{career_id}",
            CareerRead
        )

        if cached_career is not None:
            show(f"[CACHE HIT] Career full by id {career_id}")
            return cached_career

        # Cache miss - get from database
        show(f"[CACHE MISS] Career full by id {career_id} - querying DB")
        career = services.careerService.get_career_by_id(career_id, session)

        if not career:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrera no encontrada"
            )

        # Update cache
        services.cacheService.cache_generic(
            services.cacheService.CAREER_PREFIX,
            f"full:{career_id}",
            career
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
    """Obtener una carrera por ID admin - con cache Redis"""
    try:
        # Try to get from cache first
        from database.models.career import CareerRead
        cached_career = services.cacheService.get_cached_generic(
            services.cacheService.CAREER_PREFIX,
            f"admin_full:{career_id}",
            CareerRead
        )

        if cached_career is not None:
            show(f"[CACHE HIT] Admin career full by id {career_id}")
            return cached_career

        # Cache miss - get from database
        show(f"[CACHE MISS] Admin career full by id {career_id} - querying DB")
        career = services.careerService.get_career_by_id_admin(career_id, session)

        if not career:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrera no encontrada"
            )

        # Update cache
        services.cacheService.cache_generic(
            services.cacheService.CAREER_PREFIX,
            f"admin_full:{career_id}",
            career
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
        updated_career = services.careerService.update_career(career_id, career_update, session, None)

        show(f"Carrera {career_id} actualizada por usuario {current_user.email}")

        # Invalidate all career caches
        services.cacheService.invalidate_all_careers()
        show(f"[CACHE] Invalidated all career caches after updating career {career_id}")

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
async def update_career_image(
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
        supabaseService = services.supabaseService
        try:
            image_url = await supabaseService.upload_image(image, folder="images")
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
        career_update = CareerUpdate(imageLink=image_url)
        # Actualizar la carrera
        updated_career = services.careerService.update_career(career_id, career_update, session, supabaseService)

        show(f"Carrera {career_id} actualizada por usuario {current_user.email}")

        # Invalidate all career caches
        services.cacheService.invalidate_all_careers()
        show(f"[CACHE] Invalidated all career caches after updating image for career {career_id}")

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

        # Invalidate all career caches
        services.cacheService.invalidate_all_careers()
        show(f"[CACHE] Invalidated all career caches after publishing career {career_id}")

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

        # Invalidate all career caches
        services.cacheService.invalidate_all_careers()
        show(f"[CACHE] Invalidated all career caches after unpublishing career {career_id}")

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

        # Invalidate all career caches
        services.cacheService.invalidate_all_careers()
        show(f"[CACHE] Invalidated all career caches after deleting career {career_id}")

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