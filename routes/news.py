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
    NewsFilterResponse,
    Area
)
from database.services.filter.filters import Filter
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
    limit: int = Query(4, ge=1, le=20, description="Número de noticias recientes a obtener"),
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

@router.post("/create", response_model=NewsRead, status_code=status.HTTP_201_CREATED)
async def create_news(
    area: Area = Form(...),
    title: str = Form(...),
    text: str = Form(...),
    career_id: Optional[int] = Form(None),
    video_url: Optional[str] = Form(None, description="Enlace del video (opcional)"),
    images: Optional[List[UploadFile]] = File(None),
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> NewsRead:
    """Crear una nueva noticia con imágenes (solo administradores)"""
    image_urls = None
    career = None
    
    try:
        if career_id is not None:
            career = services.careerService.get_career_by_id(career_id, session)
            if career is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Carrera no encontrada"
                )
            
        # Subir imágenes si existen
        if images and len(images) > 0:
            # Filtrar archivos vacíos
            valid_images = [img for img in images if img.size > 0]
            if valid_images:
                if len(valid_images) > 6:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Máximo 6 imágenes permitidas"
                    )
                print(f"📸 Subiendo {len(valid_images)} imágenes...")
                image_urls = await services.supabaseService.upload_multiple_images(
                    valid_images
                )
                
        show(image_urls)

        # Crear el objeto NewsCreate
        news_data = NewsCreate(
            area=area,
            career=career.careerId if career else None,
            title=title,
            text=text,
            videoLink=video_url,
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
        services.supabaseService.rollback(image_urls=image_urls, video_url=video_url)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except AppException as e:
        services.supabaseService.rollback(image_urls=image_urls, video_url=video_url)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        services.supabaseService.rollback(image_urls=image_urls, video_url=video_url)
        show(f"Error al crear noticia: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.get("/admin/news", response_model=List[NewsRead], status_code=status.HTTP_200_OK)
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
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.get("/admin/simple-list", response_model=List[NewsInList], status_code=status.HTTP_200_OK)
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

@router.get("/admin/{news_id}", response_model=NewsRead, status_code=status.HTTP_200_OK)
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
    news_update: NewsUpdate,
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
    except Exception as e:
        show(f"Error al actualizar noticia: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

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

# TODO: Hacer otro endpoint para usuarios (Filtrar que esten publicadas las carreras)
@router.post("/filters", response_model=List[dict], status_code=status.HTTP_200_OK)
async def filter_news(
    filters: Filter,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> List[NewsFilterResponse]:
    """Buscar noticias por título (solo administradores)"""
    try:
        news_list = services.newsService.get_with_filters_clean(session, filters)
        return news_list
    except Exception as e:
        show(f"Error al buscar noticias por título: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
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
            detail=f"Error interno del servidor: {str(e)}"
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
            detail=f"Error interno del servidor: {str(e)}"
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
            detail=f"Error interno del servidor: {str(e)}"
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
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.put("/{news_id}/images", response_model=NewsRead, status_code=status.HTTP_200_OK)
async def update_news_files(
    news_id: int,
    images: List[UploadFile] = File(...),
    replace_files: bool = False,
    current_user: UserRead = Depends(require_admin_role),
    services: Services = Depends(get_services),
    session: Session = Depends(get_session)
) -> NewsRead:
    """
    Actualizar archivos de una noticia (solo administradores).
    
    Args:
        replace_files: Si es True, reemplaza todas las imágenes existentes.
                      Si es False, agrega las nuevas imágenes a las existentes.
    """
    
    # Inicializar variables para rollback
    new_image_urls = None
    
    try:
        # Verificar que la noticia existe
        current_news = services.newsService.get_news_by_id(news_id, session)
        if not current_news:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Noticia no encontrada"
            )

        # Filtrar archivos vacíos
        valid_images = [img for img in images if img.size > 0] if images else []
        
        # Validar límite de imágenes según el modo
        if replace_files:
            # Modo reemplazo: solo validar las nuevas imágenes
            if len(valid_images) > 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Máximo 6 imágenes permitidas"
                )
        else:
            # Modo agregar: validar imágenes existentes + nuevas
            existing_images_count = len(current_news.imagesLink) if current_news.imagesLink else 0
            total_images = existing_images_count + len(valid_images)
            
            if total_images > 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Máximo 6 imágenes permitidas. La noticia tiene {existing_images_count} imágenes, "
                           f"intentas agregar {len(valid_images)}, total sería {total_images}"
                )

        # Subir las nuevas imágenes
        new_image_urls = []
        if valid_images:
            print(f"📸 Subiendo {len(valid_images)} nuevas imágenes...")
            new_image_urls = await services.supabaseService.upload_multiple_images(
                valid_images, 
                folder="news"
            )

        # Preparar las URLs finales según el modo
        if replace_files:
            # Reemplazar: usar solo las nuevas imágenes/video
            final_image_urls = new_image_urls if new_image_urls else None
            
            # Eliminar archivos antiguos después de subir los nuevos
            old_images_to_delete = current_news.imagesLink if current_news.imagesLink else []
            
        else:
            # Agregar: combinar existentes + nuevas
            existing_images = current_news.imagesLink if current_news.imagesLink else []
            final_image_urls = existing_images + new_image_urls if new_image_urls else existing_images
            final_image_urls = final_image_urls if final_image_urls else None
            
            # Para video: reemplazar si se sube uno nuevo, sino mantener el existente
            
            # En modo agregar, solo eliminar video anterior si se reemplaza
            old_images_to_delete = []

        # Actualizar la noticia en la base de datos
        updated_news = services.newsService.update_news_files(
            news_id=news_id,
            image_urls=final_image_urls,
            session=session
        )
        
        # Si la actualización fue exitosa, eliminar archivos antiguos
        if replace_files:
            try:
                if old_images_to_delete:
                    for old_url in old_images_to_delete:
                        services.supabaseService.delete_file(old_url)
                    print(f"🗑️ Eliminadas {len(old_images_to_delete)} imágenes anteriores")
                

                    
            except Exception as cleanup_error:
                print(f"⚠️ Error limpiando archivos antiguos: {cleanup_error}")
                # No fallar la operación por esto, solo loguear
        
        show(f"Archivos actualizados en la noticia {news_id}")
        return updated_news
        
    except HTTPException:
        # Re-lanzar HTTPException sin rollback si es error de validación
        raise
    except NoResultFound:
        services.supabaseService.rollback(image_urls=new_image_urls)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Noticia no encontrada"
        )
    except ValueError as e:
        services.supabaseService.rollback(image_urls=new_image_urls)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AppException as e:
        services.supabaseService.rollback(image_urls=new_image_urls)
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        services.supabaseService.rollback(image_urls=new_image_urls)
        show(f"Error actualizando archivos de la noticia: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

# =================== ENDPOINTS ADICIONALES BASADOS EN NewsService ===================

@router.get("/recent", response_model=List[NewsRead], status_code=status.HTTP_200_OK)
async def get_recent_news(
    days: int = Query(30, ge=1, le=365, description="Número de días para considerar como reciente"),
    offset: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(4, ge=1, le=100, description="Número máximo de registros a devolver"),
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
            detail=f"Error interno del servidor: {str(e)}"
        )