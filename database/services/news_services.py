from sqlmodel import Session, select
from ..models.news import News, NewsCreate, NewsRead, NewsUpdate, NewsInList, NewsPublic, NewsReadWithUsers, Area
from ..models.career import Career
from typing import List, Optional
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload

from datetime import datetime, date, timedelta, timezone

from database.services.filter.filters import BaseServiceWithFilters
from database.models.user import UserRead

import os
from zoneinfo import ZoneInfo

def get_uruguay_tz():
    """Lee la variable cada vez que se llama"""
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)

class NewsService(BaseServiceWithFilters[News]):
    def __init__(self):
        super().__init__(News)

    def create_news(self, news: NewsCreate, session: Session) -> NewsRead:
        """Crear una nueva noticia"""
        with session:
            new_news = News(**news.model_dump())
            session.add(new_news)
            session.commit()
            session.refresh(new_news)
            return NewsRead.model_validate(new_news)

    def get_news(self, session: Session, offset: int = 0, limit: int = 10) -> List[NewsRead]:
        """Obtener lista de noticias con paginación"""
        
        # Remover "with session:" - la sesión ya está manejada por FastAPI
        statement = (
            select(News)
            .options(
                selectinload(News.creator_user),
                selectinload(News.modifier_user),
                selectinload(News.career_ref)
            )
            .order_by(News.creationDate.desc())
            .offset(offset)
            .limit(limit)
        )
        
        news_list = session.exec(statement).all()
        
        if not news_list:
            return []
        
        return [NewsRead.model_validate(news) for news in news_list]

    def get_news_in_list(self, session: Session, offset: int = 0, limit: int = 10) -> List[NewsInList]:
        """Obtener lista simplificada de noticias para listados"""
        with session:
            statement = select(News).offset(offset).limit(limit).order_by(News.creationDate.desc())
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsInList.from_news(news) for news in news_list]

    def get_news_public(self, session: Session, offset: int = 0, limit: int = 10) -> List[NewsPublic]:
        """Obtener noticias públicas (solo publicadas)"""
        with session:            
            statement = select(News).where(
                News.published
            ).offset(offset).limit(limit).order_by(News.publicationDate.desc())
            
            news_list = session.exec(statement).all()
            
            if not news_list:
                print("No se encontraron noticias públicas")
                return []
                
            return [NewsPublic.model_validate(news) for news in news_list]


    def get_news_by_id(self, news_id: int, session: Session) -> NewsRead:
        """Obtener una noticia por ID"""  
        statement = (
            select(News)
            .where(News.newsId == news_id)
            .options(
                selectinload(News.creator_user),
                selectinload(News.modifier_user),
                selectinload(News.career_ref)
            )
        )
        news = session.exec(statement).first()
        
        if not news:
            raise ValueError(f"Noticia con ID {news_id} no encontrada")
        
        # DEBUG
        print(f"DEBUG get_news_by_id - news.creator_user: {news.creator_user}")
        
        return NewsRead.model_validate(news)
            
    def get_news_by_id_with_users(self, news_id: int, session: Session) -> NewsReadWithUsers:
        """Obtener una noticia por su ID"""
        with session:
            statement = select(News).options(
                selectinload(News.career_ref),
                selectinload(News.creator_user),
                selectinload(News.modifier_user)
            ).where(News.newsId == news_id)
            
            news = session.exec(statement).first()
            
            if not news:
                return None
            
            return NewsReadWithUsers(
                newsId=news.newsId,
                area=news.area,
                career=news.career,
                title=news.title,
                text=news.text,
                videoLink=news.videoLink,
                creationDate=news.creationDate,
                modificationDate=news.modificationDate,
                publicationDate=news.publicationDate,
                published=news.published,
                creator_user=UserRead.model_validate(news.creator_user),
                modifier_user=UserRead.model_validate(news.modifier_user) if news.modifier_user else None,
                imagesLink=news.images_list,
                career_name=news.career_ref.name if news.career_ref else None
            )

    def get_published_news_by_id(self, news_id: int, session: Session) -> NewsPublic:
        """Obtener una noticia publicada por su ID (para público)"""
        with session:
            statement = select(News, Career.name).outerjoin(
                Career, News.career == Career.careerId
            ).where(
                News.newsId == news_id,
                News.published,
                News.publicationDate <= datetime.now(get_uruguay_tz()).date()
            )
            result = session.exec(statement).first()
            
            if not result:
                return None
                
            news, career_name = result
            
            # Crear el modelo NewsPublic manualmente
            return NewsPublic(
                newsId=news.newsId,
                title=news.title,
                text=news.text,
                area=news.area,
                publicationDate=news.publicationDate,
                videoLink=news.videoLink,
                imagesLink=news.images_list,
                career_name=career_name
            )

    def get_news_by_area(self, area: Area, session: Session, offset: int = 0, limit: int = 10) -> List[NewsRead]:
        """Obtener noticias por área""" 
        with session:
            statement = (
                select(News)
                .where(News.area == area)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
                .order_by(News.creationDate.desc())
                .offset(offset)
                .limit(limit)
            )
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsRead.model_validate(news) for news in news_list]

    def get_published_news_by_area(self, area: Area, session: Session, offset: int = 0, limit: int = 10) -> List[NewsPublic]:
        """Obtener noticias publicadas por área"""
        with session:
            statement = select(News).where(
                News.area == area,
                News.published,
                News.publicationDate <= datetime.now(get_uruguay_tz()).date()
            ).offset(offset).limit(limit).order_by(News.publicationDate.desc())
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsPublic.model_validate(news) for news in news_list]

    def get_news_by_career(self, career_id: int, session: Session, offset: int = 0, limit: int = 10) -> List[NewsRead]:
        """Obtener noticias por carrera"""        
        with session:
            statement = (
                select(News)
                .where(News.career == career_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
                .order_by(News.creationDate.desc())
                .offset(offset)
                .limit(limit)
            )
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsRead.model_validate(news) for news in news_list]

    def get_published_news_by_career(self, career_id: int, session: Session, offset: int = 0, limit: int = 10) -> List[NewsPublic]:
        """Obtener noticias publicadas por carrera"""
        with session:
            statement = select(News).where(
                News.career == career_id,
                News.published,
                News.publicationDate <= datetime.now(get_uruguay_tz()).date()
            ).offset(offset).limit(limit).order_by(News.publicationDate.desc())
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsPublic.model_validate(news) for news in news_list]

    def get_news_by_creator(self, creator_id: int, session: Session, offset: int = 0, limit: int = 10) -> List[NewsRead]:
        """Obtener noticias creadas por un usuario específico"""        
        with session:
            statement = (
                select(News)
                .where(News.creator == creator_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
                .order_by(News.creationDate.desc())
                .offset(offset)
                .limit(limit)
            )
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsRead.model_validate(news) for news in news_list]

    def search_news_by_title(self, search_term: str, session: Session, offset: int = 0, limit: int = 10) -> List[NewsRead]:
        """Buscar noticias por título (búsqueda parcial)"""        
        with session:
            statement = (
                select(News)
                .where(News.title.ilike(f"%{search_term}%"))
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
                .order_by(News.creationDate.desc())
                .offset(offset)
                .limit(limit)
            )
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsRead.model_validate(news) for news in news_list]

    def search_news_by_content(self, search_term: str, session: Session, offset: int = 0, limit: int = 10) -> List[NewsRead]:
        """Buscar noticias por contenido (búsqueda parcial)"""
        from sqlalchemy.orm import selectinload
        
        with session:
            statement = (
                select(News)
                .where(News.text.ilike(f"%{search_term}%"))
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
                .order_by(News.creationDate.desc())
                .offset(offset)
                .limit(limit)
            )
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsRead.model_validate(news) for news in news_list]

    def search_published_news(self, search_term: str, session: Session, offset: int = 0, limit: int = 10) -> List[NewsPublic]:
        """Buscar noticias publicadas por título o contenido"""
        with session:
            statement = select(News).where(
                News.published,
                News.publicationDate <= datetime.now(get_uruguay_tz()).date(),
                (News.title.ilike(f"%{search_term}%") | News.text.ilike(f"%{search_term}%"))
            ).offset(offset).limit(limit).order_by(News.publicationDate.desc())
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsPublic.model_validate(news) for news in news_list]

    def get_recent_news(self, session: Session, days: int = 30, offset: int = 0, limit: int = 10) -> List[NewsRead]:
        """Obtener noticias recientes (últimos N días)"""
        with session:
            cutoff_date = datetime.now(get_uruguay_tz()).date() - timedelta(days=days)
            statement = (
                select(News)
                .where(News.creationDate >= cutoff_date)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
                .order_by(News.creationDate.desc())
                .offset(offset)
                .limit(limit)
            )
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsRead.model_validate(news) for news in news_list]

    def get_latest_published_news(self, session: Session, limit: int = 5) -> List[NewsPublic]:
        """Obtener las noticias publicadas más recientes (para mostrar en homepage)"""
        with session:
            statement = select(News).where(
                News.published,
                News.publicationDate <= datetime.now(get_uruguay_tz()).date()
            ).order_by(News.publicationDate.desc()).limit(limit)
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsPublic.model_validate(news) for news in news_list]

    def get_pending_news(self, session: Session, offset: int = 0, limit: int = 10) -> List[NewsRead]:
        """Obtener noticias pendientes de publicación"""
        with session:
            statement = (
                select(News)
                .where(not News.published)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
                .order_by(News.creationDate.desc())
                .offset(offset)
                .limit(limit)
            )
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsRead.model_validate(news) for news in news_list]

    def get_scheduled_news(self, session: Session, offset: int = 0, limit: int = 10) -> List[NewsRead]:
        """Obtener noticias programadas para publicación futura"""
        with session:
            statement = (
                select(News)
                .where(
                    News.published,
                    News.publicationDate > datetime.now(get_uruguay_tz()).date()
                )
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
                .order_by(News.publicationDate.asc())
                .offset(offset)
                .limit(limit)
            )
            news_list = session.exec(statement).all()
            if not news_list:
                return []
            return [NewsRead.model_validate(news) for news in news_list]

    def update_news(self, news_id: int, news_update: NewsUpdate, session: Session) -> NewsRead:
        """Actualizar una noticia existente"""        
        with session:
            # Validar que la carrera existe si se está actualizando
            if news_update.career is not None:
                career_statement = select(Career).where(Career.careerId == news_update.career)
                career = session.exec(career_statement).first()
                if not career:
                    raise ValueError(f"La carrera con ID {news_update.career} no existe")
            
            # Cargar la noticia CON sus relaciones
            statement = (
                select(News)
                .where(News.newsId == news_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
            )
            old_news = session.exec(statement).one()
            
            update_data = news_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(old_news, key, value)
            
            old_news.modificationDate = datetime.now(get_uruguay_tz()).date()
                
            session.commit()
            
            # VOLVER A CARGAR CON RELACIONES después del commit
            statement = (
                select(News)
                .where(News.newsId == news_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
            )
            refreshed_news = session.exec(statement).one()
            
            return NewsRead.model_validate(refreshed_news)

    def publish_news(self, news_id: int, publication_date: Optional[date], session: Session) -> NewsRead:
        """Publicar una noticia (cambiar estado y fecha de publicación)"""
        from sqlalchemy.orm import selectinload
        
        with session:
            statement = (
                select(News)
                .where(News.newsId == news_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
            )
            news = session.exec(statement).one()
            
            news.published = True
            news.publicationDate = publication_date or datetime.now(get_uruguay_tz()).date()
            news.modificationDate = datetime.now(get_uruguay_tz()).date()
            
            session.commit()
            
            # Recargar con relaciones después del commit
            statement = (
                select(News)
                .where(News.newsId == news_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
            )
            refreshed_news = session.exec(statement).one()
            
            return NewsRead.model_validate(refreshed_news)

    def unpublish_news(self, news_id: int, session: Session) -> NewsRead:
        """Despublicar una noticia"""
        from sqlalchemy.orm import selectinload
        
        with session:
            statement = (
                select(News)
                .where(News.newsId == news_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
            )
            news = session.exec(statement).one()
            
            news.published = False
            news.publicationDate = None
            news.modificationDate = datetime.now(get_uruguay_tz()).date()
            
            session.commit()
            
            # Recargar con relaciones después del commit
            statement = (
                select(News)
                .where(News.newsId == news_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
            )
            refreshed_news = session.exec(statement).one()
            
            return NewsRead.model_validate(refreshed_news)

    def delete_news(self, news_id: int, session: Session) -> bool:
        """Eliminar una noticia"""
        with session:
            statement = select(News).where(News.newsId == news_id)
            news = session.exec(statement).one()
            session.delete(news)
            session.commit()
            return True

    def get_news_count(self, session: Session) -> int:
        """Obtener el conteo total de noticias"""
        with session:
            statement = select(News)
            news_list = session.exec(statement).all()
            return len(news_list)

    def get_published_news_count(self, session: Session) -> int:
        """Obtener el conteo de noticias publicadas"""
        with session:
            statement = select(News).where(
                News.published,
                News.publicationDate <= datetime.now(get_uruguay_tz()).date()
            )
            news_list = session.exec(statement).all()
            return len(news_list)

    def get_news_count_by_area(self, area: Area, session: Session) -> int:
        """Obtener el conteo de noticias por área"""
        with session:
            statement = select(News).where(News.area == area)
            news_list = session.exec(statement).all()
            return len(news_list)

    def get_news_count_by_career(self, career_id: int, session: Session) -> int:
        """Obtener el conteo de noticias por carrera"""
        with session:
            statement = select(News).where(News.career == career_id)
            news_list = session.exec(statement).all()
            return len(news_list)

    def get_news_stats(self, session: Session) -> dict:
        """Obtener estadísticas de noticias"""
        with session:
            total_count = self.get_news_count(session)
            published_count = self.get_published_news_count(session)
            pending_count = len(self.get_pending_news(session, limit=1000))
            recent_count = len(self.get_recent_news(session, days=7, limit=1000))  # Últimos 7 días
            
            # Obtener noticias por área
            statement = select(News)
            all_news = session.exec(statement).all()
            
            area_stats = {}
            career_stats = {}
            
            for news in all_news:
                # Estadísticas por área
                area = news.area.value
                if area in area_stats:
                    area_stats[area] += 1
                else:
                    area_stats[area] = 1
                
                # Estadísticas por carrera (si existe)
                if news.career:
                    career_id = news.career
                    if career_id in career_stats:
                        career_stats[career_id] += 1
                    else:
                        career_stats[career_id] = 1
            
            return {
                "total_news": total_count,
                "published_news": published_count,
                "pending_news": pending_count,
                "recent_news": recent_count,
                "news_by_area": area_stats,
                "news_by_career": career_stats
            }

    def bulk_delete_by_area(self, area: Area, session: Session) -> int:
        """Eliminar todas las noticias de un área específica"""
        with session:
            statement = select(News).where(News.area == area)
            news_list = session.exec(statement).all()
            count = len(news_list)
            
            for news in news_list:
                session.delete(news)
            
            session.commit()
            return count

    def bulk_delete_by_career(self, career_id: int, session: Session) -> int:
        """Eliminar todas las noticias de una carrera específica"""
        with session:
            statement = select(News).where(News.career == career_id)
            news_list = session.exec(statement).all()
            count = len(news_list)
            
            for news in news_list:
                session.delete(news)
            
            session.commit()
            return count

    def bulk_publish_news(self, news_ids: List[int], publication_date: Optional[date], session: Session) -> int:
        """Publicar múltiples noticias en lote"""
        with session:
            pub_date = publication_date or datetime.now(get_uruguay_tz()).date()
            count = 0
            
            for news_id in news_ids:
                try:
                    statement = select(News).where(News.newsId == news_id)
                    news = session.exec(statement).one()
                    news.published = True
                    news.publicationDate = pub_date
                    news.modificationDate = datetime.now(get_uruguay_tz()).date()
                    count += 1
                except NoResultFound:
                    continue
            
            session.commit()
            return count

    def bulk_unpublish_news(self, news_ids: List[int], session: Session) -> int:
        """Despublicar múltiples noticias en lote"""
        with session:
            count = 0
            
            for news_id in news_ids:
                try:
                    statement = select(News).where(News.newsId == news_id)
                    news = session.exec(statement).one()
                    news.published = False
                    news.publicationDate = None
                    news.modificationDate = datetime.now(get_uruguay_tz()).date()
                    count += 1
                except NoResultFound:
                    continue
            
            session.commit()
            return count

    # Métodos específicos para manejo de imágenes
    def add_image_to_news(self, news_id: int, image_url: str, session: Session) -> NewsRead:
        """Agregar una imagen a una noticia"""        
        with session:
            statement = (
                select(News)
                .where(News.newsId == news_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
            )
            news = session.exec(statement).one()
            
            news.add_image_url(image_url)
            news.modificationDate = datetime.now(get_uruguay_tz()).date()
            
            session.commit()
            
            # Recargar con relaciones después del commit
            statement = (
                select(News)
                .where(News.newsId == news_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
            )
            refreshed_news = session.exec(statement).one()
            
            return NewsRead.model_validate(refreshed_news)

    def remove_image_from_news(self, news_id: int, image_url: str, session: Session) -> NewsRead:
        """Remover una imagen de una noticia"""  
        with session:
            statement = (
                select(News)
                .where(News.newsId == news_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
            )
            news = session.exec(statement).one()
            
            news.remove_image_url(image_url)
            news.modificationDate = datetime.now(get_uruguay_tz()).date()
            
            session.commit()
            
            # Recargar con relaciones después del commit
            statement = (
                select(News)
                .where(News.newsId == news_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
            )
            refreshed_news = session.exec(statement).one()
            
            return NewsRead.model_validate(refreshed_news)

    def update_news_images(self, news_id: int, image_urls: List[str], session: Session) -> NewsRead:
        """Actualizar todas las imágenes de una noticia"""        
        with session:
            statement = (
                select(News)
                .where(News.newsId == news_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
            )
            news = session.exec(statement).one()
            
            news.set_images_list(image_urls)
            news.modificationDate = datetime.now(get_uruguay_tz()).date()
            
            session.commit()
            
            statement = (
                select(News)
                .where(News.newsId == news_id)
                .options(
                    selectinload(News.creator_user),
                    selectinload(News.modifier_user),
                    selectinload(News.career_ref)
                )
            )
            refreshed_news = session.exec(statement).one()
            
            return NewsRead.model_validate(refreshed_news)