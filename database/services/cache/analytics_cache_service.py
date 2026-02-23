"""
Cache service for Google Analytics data.
Stores GA4 API responses in Redis to reduce API quota usage.
"""
import json
import logging
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
from sqlmodel import Session, select
from database.services.redis.redis import RedisService

logger = logging.getLogger(__name__)

# Páginas estáticas conocidas del sitio
STATIC_PAGES = {
    "/": "Inicio",
    "/ofertaAcademica": "Oferta Académica",
    "/noticiasNovedades": "Noticias y Novedades",
    "/conocenos": "Conócenos",
    "/becasConvenios": "Becas y Convenios",
    "/administracion": "Administración",
    "/comunicacion": "Comunicación",
    "/informatica": "Informática",
    "/cultura": "Cultura",
}

# TTLs por defecto (en segundos)
TTL_DEFAULT = 7200       # 2 horas
TTL_DASHBOARD = 3600     # 1 hora
TTL_HISTORICAL = 14400   # 4 horas


class AnalyticsCacheService:
    """
    Cache service for GA4 analytics data.
    Works with plain dicts/lists (not Pydantic models).
    """

    PREFIX = "analytics:"

    def __init__(self, redis_service: RedisService):
        self.redis = redis_service
        logger.info("AnalyticsCacheService initialized")

    def build_cache_key(self, endpoint: str, **params) -> str:
        """Build a deterministic cache key from endpoint name and params."""
        parts = [self.PREFIX + endpoint]
        for key in sorted(params.keys()):
            parts.append(f"{key}={params[key]}")
        return ":".join(parts)

    def cache_data(self, key: str, data: Any, ttl: int = TTL_DEFAULT) -> bool:
        """Store data in Redis with TTL."""
        try:
            serialized = json.dumps(data, ensure_ascii=False)
            result = self.redis.redis_client.setex(key, ttl, serialized)
            logger.info(f"Cached {key} (TTL={ttl}s)")
            return bool(result)
        except Exception as e:
            logger.error(f"Error caching {key}: {e}")
            return False

    def get_data(self, key: str) -> Optional[Any]:
        """Get data from Redis. Returns None on miss or error."""
        try:
            data = self.redis.redis_client.get(key)
            if data:
                logger.info(f"Cache HIT: {key}")
                return json.loads(data)
            logger.info(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"Error getting {key}: {e}")
            return None

    # ==================== Enrichment Methods ====================

    @staticmethod
    def enrich_courses(courses: List[Dict], session: Session) -> List[Dict]:
        """Enrich course analytics with career names from DB."""
        from database.models.career import Career

        enriched = []
        for course in courses:
            item = course.copy()
            try:
                career_id = int(course.get("slug", "0"))
                item["careerId"] = career_id
                career = session.exec(
                    select(Career).where(Career.careerId == career_id)
                ).one_or_none()
                item["careerName"] = career.name if career else None
            except (ValueError, AttributeError):
                item["careerId"] = None
                item["careerName"] = None
            enriched.append(item)
        return enriched

    @staticmethod
    def enrich_news(news_list: List[Dict], session: Session) -> List[Dict]:
        """Enrich news analytics with news titles from DB."""
        from database.models.news import News

        enriched = []
        for news_item in news_list:
            item = news_item.copy()
            try:
                news_id = int(news_item.get("slug", "0"))
                item["newsId"] = news_id
                news_data = session.exec(
                    select(News).where(News.newsId == news_id)
                ).one_or_none()
                item["newsTitle"] = news_data.title if news_data else None
            except (ValueError, AttributeError):
                item["newsId"] = None
                item["newsTitle"] = None
            enriched.append(item)
        return enriched

    @staticmethod
    def enrich_pages(pages: List[Dict], session: Session) -> List[Dict]:
        """Enrich top pages with names from DB (for complete-report)."""
        from database.models.career import Career
        from database.models.news import News

        enriched = []
        for page in pages:
            item = page.copy()
            page_path = page.get("page_path", "")

            item["page_name"] = None
            item["page_type"] = None
            item["record_id"] = None

            if "/ofertaAcademica/" in page_path:
                try:
                    career_id = int(page_path.rstrip('/').split('/')[-1].split('?')[0])
                    career = session.exec(
                        select(Career).where(Career.careerId == career_id)
                    ).one_or_none()
                    if career:
                        item["page_name"] = career.name
                        item["page_type"] = "career"
                        item["record_id"] = career_id
                except (ValueError, AttributeError):
                    pass
            elif "/noticiasNovedades/" in page_path:
                try:
                    news_id = int(page_path.rstrip('/').split('/')[-1].split('?')[0])
                    news_data = session.exec(
                        select(News).where(News.newsId == news_id)
                    ).one_or_none()
                    if news_data:
                        item["page_name"] = news_data.title
                        item["page_type"] = "news"
                        item["record_id"] = news_id
                except (ValueError, AttributeError):
                    pass
            else:
                normalized_path = page_path.rstrip('/') or "/"
                item["page_name"] = STATIC_PAGES.get(normalized_path)
                if item["page_name"]:
                    item["page_type"] = "static"

            enriched.append(item)
        return enriched
