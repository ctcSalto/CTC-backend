from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File, Form
from sqlmodel import Session
from typing import List, Optional
from datetime import date
from database.database import Services, get_services, get_session
from database.models.news import (
    NewsCreate, 
    NewsRead, 
    NewsUpdate, 
    NewsInList, 
    NewsPublic,
    Area
)
from database.models.user import UserRead
from database.services.auth.dependencies import get_current_user, require_admin_role
from exceptions import AppException
from sqlalchemy.exc import NoResultFound

from utils.logger import show

router = APIRouter(prefix="/news", tags=["News"])

# =================== ENDPOINTS PÚBLICOS ===================

@router.get("/public", response_model=List[NewsPublic], status_code=status.HTTP_200_OK)
async def get_public_news(
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsPublic]:
    """Obtener noticias públicas (solo publicadas) con paginación"""
    try:
        news_list = services.newsService.get_news_public(session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al obtener noticias públicas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/public/latest", response_model=List[NewsPublic], status_code=status.HTTP_200_OK)
async def get_latest_published_news(
    limit: int = Query(5, ge=1, le=20, description="Número de noticias recientes a obtener"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsPublic]:
    """Obtener las noticias publicadas más recientes para homepage"""
    try:
        news_list = services.newsService.get_latest_published_news(session, limit)
        return news_list
    except Exception as e:
        show(f"Error al obtener noticias recientes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/public/{news_id}", response_model=NewsPublic, status_code=status.HTTP_200_OK)
async def get_published_news_by_id(
    news_id: int,
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> NewsPublic:
    """Obtener una noticia publicada específica por ID"""
    try:
        news = services.newsService.get_published_news_by_id(news_id, session)
        
        if not news:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Noticia no encontrada o no publicada"
            )
        
        return news
        
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Noticia no encontrada o no publicada"
        )
    except Exception as e:
        show(f"Error al obtener noticia pública: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/public/area/{area}", response_model=List[NewsPublic], status_code=status.HTTP_200_OK)
async def get_published_news_by_area(
    area: Area,
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsPublic]:
    """Obtener noticias publicadas por área"""
    try:
        news_list = services.newsService.get_published_news_by_area(area, session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al obtener noticias por área: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/public/career/{career_id}", response_model=List[NewsPublic], status_code=status.HTTP_200_OK)
async def get_published_news_by_career(
    career_id: int,
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsPublic]:
    """Obtener noticias publicadas por carrera"""
    try:
        news_list = services.newsService.get_published_news_by_career(career_id, session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al obtener noticias por carrera: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/public/search", response_model=List[NewsPublic], status_code=status.HTTP_200_OK)
async def search_published_news(
    q: str = Query(..., min_length=3, description="Término de búsqueda"),
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsPublic]:
    """Buscar noticias publicadas por título o contenido"""
    try:
        news_list = services.newsService.search_published_news(q, session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al buscar noticias: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# =================== ENDPOINTS ADMINISTRATIVOS ===================

@router.post("/", response_model=NewsRead, status_code=status.HTTP_201_CREATED)
async def create_news(
    area: Area = Form(...),
    title: str = Form(...),
    text: str = Form(...),
    career: Optional[int] = Form(None),
    videoLink: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> NewsRead:
    """Crear una nueva noticia con imágenes (solo administradores)"""
    try:
        # Subir imágenes si existen
        image_urls = None
        if images and len(images) > 0:
            # Filtrar archivos vacíos
            valid_images = [img for img in images if img.size > 0]
            if valid_images:
                if len(valid_images) > 6:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Máximo 6 imágenes permitidas"
                    )
                image_urls = await services.supabaseService.upload_multiple_images(
                    valid_images, 
                    folder="news"
                )

        # Crear el objeto NewsCreate
        news_data = NewsCreate(
            area=area,
            career=career,
            title=title,
            text=text,
            videoLink=videoLink,
            imagesLink=image_urls,
            creator=current_user.userId
        )

        new_news = services.newsService.create_news(news_data, session)
        
        show(f"Noticia creada: {new_news}")
        
        if not new_news:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear la noticia"
            )
        
        return new_news
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/", response_model=List[NewsRead], status_code=status.HTTP_200_OK)
async def get_news(
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsRead]:
    """Obtener todas las noticias con detalles completos (solo administradores)"""
    try:
        news_list = services.newsService.get_news(session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al obtener noticias: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/list", response_model=List[NewsInList], status_code=status.HTTP_200_OK)
async def get_news_list(
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsInList]:
    """Obtener lista simplificada de noticias (solo administradores)"""
    try:
        news_list = services.newsService.get_news_in_list(session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al obtener lista de noticias: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/pending", response_model=List[NewsRead], status_code=status.HTTP_200_OK)
async def get_pending_news(
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsRead]:
    """Obtener noticias pendientes de publicación (solo administradores)"""
    try:
        news_list = services.newsService.get_pending_news(session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al obtener noticias pendientes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/scheduled", response_model=List[NewsRead], status_code=status.HTTP_200_OK)
async def get_scheduled_news(
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsRead]:
    """Obtener noticias programadas para publicación futura (solo administradores)"""
    try:
        news_list = services.newsService.get_scheduled_news(session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al obtener noticias programadas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/{news_id}", response_model=NewsRead, status_code=status.HTTP_200_OK)
async def get_news_by_id(
    news_id: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> NewsRead:
    """Obtener una noticia por ID (solo administradores)"""
    try:
        news = services.newsService.get_news_by_id(news_id, session)
        
        if not news:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Noticia no encontrada"
            )
        
        return news
        
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Noticia no encontrada"
        )
    except Exception as e:
        show(f"Error al obtener noticia: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.put("/{news_id}", response_model=NewsRead, status_code=status.HTTP_200_OK)
async def update_news(
    news_id: int,
    area: Optional[Area] = Form(None),
    title: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    career: Optional[int] = Form(None),
    videoLink: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    replace_images: bool = Form(False, description="Si es True, reemplaza todas las imágenes. Si es False, las agrega."),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> NewsRead:
    """Actualizar una noticia con imágenes (solo administradores)"""
    try:
        # Obtener la noticia actual para manejar las imágenes
        current_news = services.newsService.get_news_by_id(news_id, session)
        if not current_news:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Noticia no encontrada"
            )

        # Manejar las imágenes
        image_urls = None
        if images and len(images) > 0:
            # Filtrar archivos vacíos
            valid_images = [img for img in images if img.size > 0]
            if valid_images:
                new_image_urls = await services.supabaseService.upload_multiple_images(
                    valid_images, 
                    folder="news"
                )
                
                if replace_images:
                    # Reemplazar todas las imágenes
                    image_urls = new_image_urls
                else:
                    # Agregar a las existentes
                    existing_urls = current_news.imagesLink or []
                    image_urls = existing_urls + new_image_urls
                    
                    # Verificar límite de 6 imágenes
                    if len(image_urls) > 6:
                        image_urls = image_urls[:6]

        # Crear el objeto NewsUpdate
        news_update = NewsUpdate(
            area=area,
            career=career,
            title=title,
            text=text,
            videoLink=videoLink,
            imagesLink=image_urls,
            modifier=current_user.userId
        )

        updated_news = services.newsService.update_news(news_id, news_update, session)
        
        show(f"Noticia actualizada: {updated_news}")
        
        return updated_news
        
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Noticia no encontrada"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/{news_id}/publish", response_model=NewsRead, status_code=status.HTTP_200_OK)
async def publish_news(
    news_id: int,
    publication_date: Optional[date] = Query(None, description="Fecha de publicación (opcional, por defecto hoy)"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> NewsRead:
    """Publicar una noticia (solo administradores)"""
    try:
        published_news = services.newsService.publish_news(news_id, publication_date, session)
        
        show(f"Noticia publicada: {published_news}")
        
        return published_news
        
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Noticia no encontrada"
        )
    except Exception as e:
        show(f"Error al publicar noticia: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/{news_id}/unpublish", response_model=NewsRead, status_code=status.HTTP_200_OK)
async def unpublish_news(
    news_id: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> NewsRead:
    """Despublicar una noticia (solo administradores)"""
    try:
        unpublished_news = services.newsService.unpublish_news(news_id, session)
        
        show(f"Noticia despublicada: {unpublished_news}")
        
        return unpublished_news
        
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Noticia no encontrada"
        )
    except Exception as e:
        show(f"Error al despublicar noticia: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_news(
    news_id: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
):
    """Eliminar una noticia (solo administradores)"""
    try:
        success = services.newsService.delete_news(news_id, session)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Noticia no encontrada"
            )
        
        show(f"Noticia {news_id} eliminada")
        
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Noticia no encontrada"
        )
    except Exception as e:
        show(f"Error al eliminar noticia: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# =================== ENDPOINTS DE BÚSQUEDA ADMINISTRATIVA ===================

@router.get("/search/title", response_model=List[NewsRead], status_code=status.HTTP_200_OK)
async def search_news_by_title(
    q: str = Query(..., min_length=3, description="Término de búsqueda en el título"),
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsRead]:
    """Buscar noticias por título (solo administradores)"""
    try:
        news_list = services.newsService.search_news_by_title(q, session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al buscar noticias por título: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/search/content", response_model=List[NewsRead], status_code=status.HTTP_200_OK)
async def search_news_by_content(
    q: str = Query(..., min_length=3, description="Término de búsqueda en el contenido"),
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsRead]:
    """Buscar noticias por contenido (solo administradores)"""
    try:
        news_list = services.newsService.search_news_by_content(q, session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al buscar noticias por contenido: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/area/{area}", response_model=List[NewsRead], status_code=status.HTTP_200_OK)
async def get_news_by_area(
    area: Area,
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsRead]:
    """Obtener noticias por área (solo administradores)"""
    try:
        news_list = services.newsService.get_news_by_area(area, session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al obtener noticias por área: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/career/{career_id}", response_model=List[NewsRead], status_code=status.HTTP_200_OK)
async def get_news_by_career(
    career_id: int,
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsRead]:
    """Obtener noticias por carrera (solo administradores)"""
    try:
        news_list = services.newsService.get_news_by_career(career_id, session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al obtener noticias por carrera: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/creator/{creator_id}", response_model=List[NewsRead], status_code=status.HTTP_200_OK)
async def get_news_by_creator(
    creator_id: int,
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsRead]:
    """Obtener noticias creadas por un usuario específico (solo administradores)"""
    try:
        news_list = services.newsService.get_news_by_creator(creator_id, session, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al obtener noticias por creador: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# =================== ENDPOINTS DE ESTADÍSTICAS ===================

@router.get("/stats/general", status_code=status.HTTP_200_OK)
async def get_news_stats(
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> dict:
    """Obtener estadísticas generales de noticias (solo administradores)"""
    try:
        stats = services.newsService.get_news_stats(session)
        return stats
    except Exception as e:
        show(f"Error al obtener estadísticas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/stats/count", status_code=status.HTTP_200_OK)
async def get_news_count(
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> dict:
    """Obtener conteo total de noticias (solo administradores)"""
    try:
        total_count = services.newsService.get_news_count(session)
        published_count = services.newsService.get_published_news_count(session)
        return {
            "total_news": total_count,
            "published_news": published_count,
            "draft_news": total_count - published_count
        }
    except Exception as e:
        show(f"Error al obtener conteo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# =================== ENDPOINTS DE UTILIDAD ===================

@router.post("/bulk/publish", status_code=status.HTTP_200_OK)
async def bulk_publish_news(
    news_ids: List[int],
    publication_date: Optional[date] = Query(None, description="Fecha de publicación (opcional, por defecto hoy)"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> dict:
    """Publicar múltiples noticias en lote (solo administradores)"""
    try:
        published_count = services.newsService.bulk_publish_news(news_ids, publication_date, session)
        
        show(f"{published_count} noticias publicadas")
        
        return {"published_count": published_count, "total_requested": len(news_ids)}
        
    except Exception as e:
        show(f"Error al publicar noticias en lote: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.post("/bulk/unpublish", status_code=status.HTTP_200_OK)
async def bulk_unpublish_news(
    news_ids: List[int],
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> dict:
    """Despublicar múltiples noticias en lote (solo administradores)"""
    try:
        unpublished_count = services.newsService.bulk_unpublish_news(news_ids, session)
        
        show(f"{unpublished_count} noticias despublicadas")
        
        return {"unpublished_count": unpublished_count, "total_requested": len(news_ids)}
        
    except Exception as e:
        show(f"Error al despublicar noticias en lote: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.delete("/bulk/area/{area}", status_code=status.HTTP_200_OK)
async def bulk_delete_news_by_area(
    area: Area,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> dict:
    """Eliminar todas las noticias de un área específica (solo administradores)"""
    try:
        deleted_count = services.newsService.bulk_delete_by_area(area, session)
        
        show(f"{deleted_count} noticias eliminadas del área {area}")
        
        return {"deleted_count": deleted_count}
        
    except Exception as e:
        show(f"Error al eliminar noticias por área: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.delete("/bulk/career/{career_id}", status_code=status.HTTP_200_OK)
async def bulk_delete_news_by_career(
    career_id: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> dict:
    """Eliminar todas las noticias de una carrera específica (solo administradores)"""
    try:
        deleted_count = services.newsService.bulk_delete_by_career(career_id, session)
        
        show(f"{deleted_count} noticias eliminadas de la carrera {career_id}")
        
        return {"deleted_count": deleted_count}
        
    except Exception as e:
        show(f"Error al eliminar noticias por carrera: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

# =================== ENDPOINTS DE MANEJO DE IMÁGENES ===================

@router.post("/{news_id}/images", response_model=NewsRead, status_code=status.HTTP_200_OK)
async def add_image_to_news(
    news_id: int,
    image: UploadFile = File(...),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> NewsRead:
    """Agregar una imagen a una noticia existente (solo administradores)"""
    try:
        # Verificar que la noticia existe
        current_news = services.newsService.get_news_by_id(news_id, session)
        if not current_news:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Noticia no encontrada"
            )

        # Verificar límite de imágenes
        current_images = current_news.imagesLink or []
        if len(current_images) >= 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Máximo 6 imágenes permitidas por noticia"
            )

        # Subir la nueva imagen
        if image.size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo de imagen está vacío"
            )

        image_url = await services.supabaseService.upload_image(image, folder="news")
        
        # Agregar la imagen a la noticia
        updated_news = services.newsService.add_image_to_news(news_id, image_url, session)
        
        show(f"Imagen agregada a la noticia {news_id}")
        
        return updated_news
        
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Noticia no encontrada"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.delete("/{news_id}/images", response_model=NewsRead, status_code=status.HTTP_200_OK)
async def remove_image_from_news(
    news_id: int,
    image_url: str = Query(..., description="URL de la imagen a eliminar"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> NewsRead:
    """Eliminar una imagen específica de una noticia (solo administradores)"""
    try:
        # Verificar que la noticia existe
        current_news = services.newsService.get_news_by_id(news_id, session)
        if not current_news:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Noticia no encontrada"
            )

        # Verificar que la imagen existe en la noticia
        current_images = current_news.imagesLink or []
        if image_url not in current_images:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Imagen no encontrada en esta noticia"
            )

        # Remover la imagen de la noticia
        updated_news = services.newsService.remove_image_from_news(news_id, image_url, session)
        
        show(f"Imagen eliminada de la noticia {news_id}")
        
        return updated_news
        
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Noticia no encontrada"
        )
    except Exception as e:
        show(f"Error al eliminar imagen: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.put("/{news_id}/images", response_model=NewsRead, status_code=status.HTTP_200_OK)
async def update_news_images(
    news_id: int,
    images: List[UploadFile] = File(...),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> NewsRead:
    """Reemplazar todas las imágenes de una noticia (solo administradores)"""
    try:
        # Verificar que la noticia existe
        current_news = services.newsService.get_news_by_id(news_id, session)
        if not current_news:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Noticia no encontrada"
            )

        # Filtrar archivos vacíos
        valid_images = [img for img in images if img.size > 0]
        
        if len(valid_images) > 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Máximo 6 imágenes permitidas"
            )

        # Subir las nuevas imágenes
        image_urls = []
        if valid_images:
            image_urls = await services.supabaseService.upload_multiple_images(
                valid_images, 
                folder="news"
            )

        # Actualizar las imágenes de la noticia
        updated_news = services.newsService.update_news_images(news_id, image_urls, session)
        
        show(f"Imágenes actualizadas en la noticia {news_id}")
        
        return updated_news
        
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Noticia no encontrada"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

# =================== ENDPOINTS ADICIONALES BASADOS EN NewsService ===================

@router.get("/recent", response_model=List[NewsRead], status_code=status.HTTP_200_OK)
async def get_recent_news(
    days: int = Query(30, ge=1, le=365, description="Número de días para considerar como reciente"),
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Número máximo de registros a devolver"),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsRead]:
    """Obtener noticias recientes (últimos N días) - solo administradores"""
    try:
        news_list = services.newsService.get_recent_news(session, days, offset, limit)
        return news_list
    except Exception as e:
        show(f"Error al obtener noticias recientes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/stats/area/{area}", status_code=status.HTTP_200_OK)
async def get_news_count_by_area(
    area: Area,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> dict:
    """Obtener conteo de noticias por área específica (solo administradores)"""
    try:
        count = services.newsService.get_news_count_by_area(area, session)
        return {"area": area.value, "count": count}
    except Exception as e:
        show(f"Error al obtener conteo por área: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/stats/career/{career_id}", status_code=status.HTTP_200_OK)
async def get_news_count_by_career(
    career_id: int,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> dict:
    """Obtener conteo de noticias por carrera específica (solo administradores)"""
    try:
        count = services.newsService.get_news_count_by_career(career_id, session)
        return {"career_id": career_id, "count": count}
    except Exception as e:
        show(f"Error al obtener conteo por carrera: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )