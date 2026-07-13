"""
Cache service for managing Redis cache for careers and other entities.
Implements cache-aside pattern with automatic fallback to database.
"""
import json
import logging
from typing import Optional, List, Any, Dict
from sqlmodel import Session
from database.services.redis.redis import RedisService
from database.models.career import CareerReadOptimized, CareerInList, CareerSimple

logger = logging.getLogger(__name__)

class CacheService:
    """
    Service for managing Redis cache with automatic serialization/deserialization.
    Implements cache-aside pattern for careers.
    """

    # Cache key prefixes
    CAREER_PREFIX = "career:"
    CAREERS_LIST_PREFIX = "careers:list:"
    CAREERS_OPTIMIZED_PREFIX = "careers:optimized:"
    CAREERS_PUBLISHED_PREFIX = "careers:published:"
    CAREERS_SIMPLE_PREFIX = "careers:simple:"
    CAREERS_DROPDOWN_PREFIX = "careers:dropdown:"
    CAREERS_BY_AREA_PREFIX = "careers:area:"
    CAREERS_BY_TYPE_PREFIX = "careers:type:"
    CAREERS_RANDOM_PREFIX = "careers:random:"

    # Cache TTL in seconds (1 hour by default)
    DEFAULT_TTL = 3600

    def __init__(self, redis_service: RedisService):
        """
        Initialize cache service with Redis connection.

        Args:
            redis_service: RedisService instance for Redis operations
        """
        self.redis = redis_service
        logger.info("CacheService initialized")

    # ==================== Generic Cache Methods ====================

    def _build_key(self, prefix: str, identifier: str = "") -> str:
        """Build cache key with prefix and identifier"""
        if identifier:
            return f"{prefix}{identifier}"
        return prefix.rstrip(":")

    def _serialize_model(self, data: Any) -> str:
        """Serialize Pydantic model or list of models to JSON string"""
        try:
            if isinstance(data, list):
                # List of models - use mode='json' to handle dates properly
                return json.dumps([item.model_dump(mode='json') for item in data], ensure_ascii=False)
            else:
                # Single model - use mode='json' to handle dates properly
                return json.dumps(data.model_dump(mode='json'), ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error serializing data: {e}")
            raise

    def _deserialize_model(self, data_str: str, model_class: type) -> Any:
        """Deserialize JSON string to Pydantic model or list of models"""
        try:
            data = json.loads(data_str)

            if isinstance(data, list):
                # List of models
                return [model_class(**item) for item in data]
            else:
                # Single model
                return model_class(**data)
        except Exception as e:
            logger.error(f"Error deserializing data: {e}")
            return None

    # ==================== Career Cache Methods ====================

    def cache_career_optimized(self, career_id: int, career_data: CareerReadOptimized, ttl: int = DEFAULT_TTL) -> bool:
        """
        Cache a single optimized career by ID.

        Args:
            career_id: Career ID
            career_data: CareerReadOptimized instance
            ttl: Time to live in seconds

        Returns:
            bool: True if cached successfully
        """
        try:
            key = self._build_key(self.CAREER_PREFIX, str(career_id))
            serialized = self._serialize_model(career_data)

            # Use Redis set with EX flag for expiration
            result = self.redis.redis_client.setex(key, ttl, serialized)

            logger.info(f"Cached career {career_id} with TTL {ttl}s")
            return bool(result)
        except Exception as e:
            logger.error(f"Error caching career {career_id}: {e}")
            return False

    def get_cached_career_optimized(self, career_id: int) -> Optional[CareerReadOptimized]:
        """
        Get cached optimized career by ID.

        Args:
            career_id: Career ID

        Returns:
            CareerReadOptimized instance or None if not cached
        """
        try:
            key = self._build_key(self.CAREER_PREFIX, str(career_id))
            data = self.redis.redis_client.get(key)

            if data:
                logger.info(f"Cache HIT for career {career_id}")
                return self._deserialize_model(data, CareerReadOptimized)

            logger.info(f"Cache MISS for career {career_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting cached career {career_id}: {e}")
            return None

    def cache_careers_list(self, offset: int, limit: int, careers: List[CareerInList], ttl: int = DEFAULT_TTL) -> bool:
        """
        Cache a paginated list of careers.

        Args:
            offset: Pagination offset
            limit: Pagination limit
            careers: List of CareerInList instances
            ttl: Time to live in seconds

        Returns:
            bool: True if cached successfully
        """
        try:
            key = self._build_key(self.CAREERS_LIST_PREFIX, f"{offset}:{limit}")
            serialized = self._serialize_model(careers)

            result = self.redis.redis_client.setex(key, ttl, serialized)

            logger.info(f"Cached careers list (offset={offset}, limit={limit}) with {len(careers)} items")
            return bool(result)
        except Exception as e:
            logger.error(f"Error caching careers list: {e}")
            return False

    def get_cached_careers_list(self, offset: int, limit: int) -> Optional[List[CareerInList]]:
        """
        Get cached paginated list of careers.

        Args:
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of CareerInList instances or None if not cached
        """
        try:
            key = self._build_key(self.CAREERS_LIST_PREFIX, f"{offset}:{limit}")
            data = self.redis.redis_client.get(key)

            if data:
                logger.info(f"Cache HIT for careers list (offset={offset}, limit={limit})")
                return self._deserialize_model(data, CareerInList)

            logger.info(f"Cache MISS for careers list (offset={offset}, limit={limit})")
            return None
        except Exception as e:
            logger.error(f"Error getting cached careers list: {e}")
            return None

    def cache_careers_optimized(self, offset: int, limit: int, published_only: bool, careers: List[CareerReadOptimized], ttl: int = DEFAULT_TTL) -> bool:
        """
        Cache optimized careers list.

        Args:
            offset: Pagination offset
            limit: Pagination limit
            published_only: Whether this is for published careers only
            careers: List of CareerReadOptimized instances
            ttl: Time to live in seconds

        Returns:
            bool: True if cached successfully
        """
        try:
            prefix = self.CAREERS_PUBLISHED_PREFIX if published_only else self.CAREERS_OPTIMIZED_PREFIX
            key = self._build_key(prefix, f"{offset}:{limit}")
            serialized = self._serialize_model(careers)

            result = self.redis.redis_client.setex(key, ttl, serialized)

            logger.info(f"Cached optimized careers (offset={offset}, limit={limit}, published={published_only})")
            return bool(result)
        except Exception as e:
            logger.error(f"Error caching optimized careers: {e}")
            return False

    def get_cached_careers_optimized(self, offset: int, limit: int, published_only: bool) -> Optional[List[CareerReadOptimized]]:
        """
        Get cached optimized careers list.

        Args:
            offset: Pagination offset
            limit: Pagination limit
            published_only: Whether to get published careers only

        Returns:
            List of CareerReadOptimized instances or None if not cached
        """
        try:
            prefix = self.CAREERS_PUBLISHED_PREFIX if published_only else self.CAREERS_OPTIMIZED_PREFIX
            key = self._build_key(prefix, f"{offset}:{limit}")
            data = self.redis.redis_client.get(key)

            if data:
                logger.info(f"Cache HIT for optimized careers (offset={offset}, limit={limit}, published={published_only})")
                return self._deserialize_model(data, CareerReadOptimized)

            logger.info(f"Cache MISS for optimized careers (offset={offset}, limit={limit}, published={published_only})")
            return None
        except Exception as e:
            logger.error(f"Error getting cached optimized careers: {e}")
            return None

    def cache_simple_careers(self, cache_key: str, careers: List[CareerSimple], ttl: int = DEFAULT_TTL) -> bool:
        """
        Cache simple careers (for random, by area, etc.).

        Args:
            cache_key: Unique cache key (e.g., "random:4", "area:it:4")
            careers: List of CareerSimple instances
            ttl: Time to live in seconds

        Returns:
            bool: True if cached successfully
        """
        try:
            key = self._build_key(self.CAREERS_SIMPLE_PREFIX, cache_key)
            serialized = self._serialize_model(careers)

            result = self.redis.redis_client.setex(key, ttl, serialized)

            logger.info(f"Cached simple careers with key '{cache_key}' ({len(careers)} items)")
            return bool(result)
        except Exception as e:
            logger.error(f"Error caching simple careers: {e}")
            return False

    def get_cached_simple_careers(self, cache_key: str) -> Optional[List[CareerSimple]]:
        """
        Get cached simple careers.

        Args:
            cache_key: Unique cache key

        Returns:
            List of CareerSimple instances or None if not cached
        """
        try:
            key = self._build_key(self.CAREERS_SIMPLE_PREFIX, cache_key)
            data = self.redis.redis_client.get(key)

            if data:
                logger.info(f"Cache HIT for simple careers '{cache_key}'")
                return self._deserialize_model(data, CareerSimple)

            logger.info(f"Cache MISS for simple careers '{cache_key}'")
            return None
        except Exception as e:
            logger.error(f"Error getting cached simple careers: {e}")
            return None

    def cache_generic(self, prefix: str, key: str, data: Any, ttl: int = DEFAULT_TTL) -> bool:
        """
        Generic method to cache any data with a prefix and key.

        Args:
            prefix: Cache prefix (e.g., CAREERS_BY_AREA_PREFIX)
            key: Unique identifier (e.g., "it:0:10")
            data: Data to cache (model or list of models)
            ttl: Time to live in seconds

        Returns:
            bool: True if cached successfully
        """
        try:
            cache_key = self._build_key(prefix, key)
            serialized = self._serialize_model(data)
            result = self.redis.redis_client.setex(cache_key, ttl, serialized)
            logger.info(f"Cached {prefix}{key} with TTL {ttl}s")
            return bool(result)
        except Exception as e:
            logger.error(f"Error caching {prefix}{key}: {e}")
            return False

    def get_cached_generic(self, prefix: str, key: str, model_class: type) -> Any:
        """
        Generic method to get cached data.

        Args:
            prefix: Cache prefix
            key: Unique identifier
            model_class: Model class for deserialization

        Returns:
            Deserialized data or None if not cached
        """
        try:
            cache_key = self._build_key(prefix, key)
            data = self.redis.redis_client.get(cache_key)

            if data:
                logger.info(f"Cache HIT for {prefix}{key}")
                return self._deserialize_model(data, model_class)

            logger.info(f"Cache MISS for {prefix}{key}")
            return None
        except Exception as e:
            logger.error(f"Error getting cached {prefix}{key}: {e}")
            return None

    # ==================== Cache Invalidation Methods ====================

    def invalidate_career(self, career_id: int) -> bool:
        """
        Invalidate cache for a specific career.

        Args:
            career_id: Career ID to invalidate

        Returns:
            bool: True if invalidated successfully
        """
        try:
            key = self._build_key(self.CAREER_PREFIX, str(career_id))
            result = self.redis.redis_client.delete(key)

            logger.info(f"Invalidated cache for career {career_id}")
            return result > 0
        except Exception as e:
            logger.error(f"Error invalidating career {career_id}: {e}")
            return False

    def invalidate_all_careers(self) -> bool:
        """
        Invalidate all career-related caches.
        This should be called when a career is created, updated, or deleted.

        Returns:
            bool: True if invalidated successfully
        """
        try:
            # Get all career-related keys
            patterns = [
                f"{self.CAREER_PREFIX}*",
                f"{self.CAREERS_LIST_PREFIX}*",
                f"{self.CAREERS_OPTIMIZED_PREFIX}*",
                f"{self.CAREERS_PUBLISHED_PREFIX}*",
                f"{self.CAREERS_SIMPLE_PREFIX}*",
                f"{self.CAREERS_DROPDOWN_PREFIX}*",
                f"{self.CAREERS_BY_AREA_PREFIX}*",
                f"{self.CAREERS_BY_TYPE_PREFIX}*",
            ]

            deleted_count = 0
            for pattern in patterns:
                keys = self.redis.redis_client.keys(pattern)
                if keys:
                    deleted_count += self.redis.redis_client.delete(*keys)

            logger.info(f"Invalidated all career caches ({deleted_count} keys deleted)")
            return True
        except Exception as e:
            logger.error(f"Error invalidating all career caches: {e}")
            return False

    # ==================== Warmup Methods ====================

    def warmup_published_careers(self, session: Session, career_service) -> bool:
        """
        Pre-cache published careers on application startup.

        Args:
            session: Database session
            career_service: CareerService instance

        Returns:
            bool: True if warmup successful
        """
        try:
            logger.info("Starting career cache warmup...")

            # Cache first page of optimized published careers (most commonly accessed)
            careers = career_service.get_careers_optimized(session, offset=0, limit=10)
            published_careers = [career for career in careers if career.published]

            if published_careers:
                self.cache_careers_optimized(
                    offset=0,
                    limit=10,
                    published_only=True,
                    careers=published_careers,
                    ttl=7200  # 2 hours for warmup cache
                )

                # Cache individual careers
                for career in published_careers:
                    self.cache_career_optimized(career.careerId, career, ttl=7200)

                logger.info(f"Career cache warmup completed: {len(published_careers)} careers cached")
                return True
            else:
                logger.warning("No published careers found for warmup")
                return False

        except Exception as e:
            logger.error(f"Error during career cache warmup: {e}")
            return False

    # ==================== Health Check ====================

    def health_check(self) -> Dict[str, Any]:
        """
        Check cache service health.

        Returns:
            Dict with health status information
        """
        try:
            # Test Redis connection
            ping_result = self.redis.redis_client.ping()

            # Get cache stats
            info = self.redis.redis_client.info('stats')

            return {
                "status": "healthy" if ping_result else "unhealthy",
                "redis_connected": ping_result,
                "total_keys": self.redis.redis_client.dbsize(),
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0),
            }
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
