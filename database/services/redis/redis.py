import redis
import json
import logging
from typing import Optional, Any
from datetime import datetime, timedelta, timezone
from sqlmodel import Session
import os

logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self, session: Session = None):
        # Configuración Redis - ajusta según tu deployment
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD", None),
            db=0,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        # Test de conexión
        try:
            self.redis_client.ping()
            logger.info("Conexión a Redis establecida correctamente")
            print("DEBUG RedisService: Conexión a Redis OK")
        except redis.ConnectionError as e:
            logger.error(f"Error conectando a Redis: {e}")
            print(f"DEBUG RedisService: Error conectando a Redis: {e}")
            raise

    def _serialize_value(self, value: Any) -> str:
        """Convierte cualquier valor a string, serializando JSON si es necesario"""
        if isinstance(value, str):
            return value
        else:
            return json.dumps(value, ensure_ascii=False)

    def _deserialize_value(self, value_str: str) -> Any:
        """Intenta deserializar JSON, si falla retorna el string original"""
        try:
            return json.loads(value_str)
        except (json.JSONDecodeError, TypeError):
            return value_str

    def set(self, key: str, value: Any, expires_at: Optional[datetime] = None, session: Session = None) -> bool:
        """
        Guarda un valor en cache con auto-serialización
        VERSIÓN SIMPLE - Siempre funciona con timezones
        """
        try:
            print(f"DEBUG RedisService.set: key={key}, value={value}, expires_at={expires_at}")
            
            # Verificar conexión
            self.redis_client.ping()
            
            # Serializar valor
            serialized_value = self._serialize_value(value)
            print(f"DEBUG RedisService.set: serialized_value={serialized_value}")
            
            if expires_at:
                # MÉTODO SIMPLE: Convertir ambos a timestamp y trabajar con números
                import time
                
                # Obtener timestamp actual
                now_timestamp = time.time()
                
                # Obtener timestamp del expires_at
                if hasattr(expires_at, 'timestamp'):
                    # Si es un datetime object
                    expires_timestamp = expires_at.timestamp()
                else:
                    # Fallback - convertir a timestamp manualmente
                    import calendar
                    expires_timestamp = calendar.timegm(expires_at.timetuple())
                
                # Calcular TTL en segundos
                ttl = int(expires_timestamp - now_timestamp)
                
                print(f"DEBUG RedisService.set: now_timestamp={now_timestamp}")
                print(f"DEBUG RedisService.set: expires_timestamp={expires_timestamp}")  
                print(f"DEBUG RedisService.set: TTL calculado: {ttl} segundos")
                
                if ttl <= 0:
                    print(f"DEBUG RedisService.set: TTL negativo ({ttl}), abortando")
                    return False
                
                # Guardar con expiración
                result = self.redis_client.setex(key, ttl, serialized_value)
                print(f"DEBUG RedisService.set: setex result={result}")
            else:
                # Guardar sin expiración
                result = self.redis_client.set(key, serialized_value)
                print(f"DEBUG RedisService.set: set result={result}")
            
            # Verificar que se guardó
            verification = self.redis_client.get(key)
            print(f"DEBUG RedisService.set: Verificación - key existe: {verification is not None}")
            
            return bool(result)
            
        except Exception as e:
            print(f"DEBUG RedisService.set: Error: {e}")
            import traceback
            print(f"DEBUG RedisService.set: Traceback: {traceback.format_exc()}")
            return False
    
    def get(self, key: str, session: Session = None) -> Optional[Any]:
        """
        Recupera un valor del cache con auto-deserialización
        
        Args:
            key: Clave del cache
            session: Session de BD (no usado, para compatibilidad)
            
        Returns:
            Any: El valor deserializado o None si no existe/expiró
        """
        try:
            print(f"DEBUG RedisService.get: Buscando key={key}")
            
            # Verificar conexión
            self.redis_client.ping()
            
            value = self.redis_client.get(key)
            print(f"DEBUG RedisService.get: Raw value={value}")
            
            if value is not None:
                deserialized = self._deserialize_value(value)
                print(f"DEBUG RedisService.get: Deserialized value={deserialized}")
                return deserialized
            
            print(f"DEBUG RedisService.get: Key {key} no encontrada")
            return None
            
        except redis.RedisError as e:
            logger.error(f"Redis error recuperando cache: {e}")
            print(f"DEBUG RedisService.get: Redis error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado recuperando cache: {e}")
            print(f"DEBUG RedisService.get: Error inesperado: {e}")
            return None

    def delete(self, key: str, session: Session = None) -> bool:
        """
        Elimina una clave del cache
        
        Args:
            key: Clave a eliminar
            session: Session de BD (no usado, para compatibilidad)
            
        Returns:
            bool: True si se eliminó exitosamente
        """
        try:
            print(f"DEBUG RedisService.delete: Eliminando key={key}")
            
            # Verificar conexión
            self.redis_client.ping()
            
            result = self.redis_client.delete(key)
            print(f"DEBUG RedisService.delete: Delete result={result}")
            
            logger.debug(f"Cache delete - key: {key}, deleted: {result > 0}")
            return result > 0
            
        except redis.RedisError as e:
            logger.error(f"Redis error eliminando cache: {e}")
            print(f"DEBUG RedisService.delete: Redis error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado eliminando cache: {e}")
            print(f"DEBUG RedisService.delete: Error inesperado: {e}")
            return False

    def exists(self, key: str, session: Session = None) -> bool:
        """
        Verifica si una clave existe en el cache y no ha expirado
        
        Args:
            key: Clave a verificar
            session: Session de BD (no usado, para compatibilidad)
            
        Returns:
            bool: True si la clave existe y no ha expirado
        """
        try:
            print(f"DEBUG RedisService.exists: Verificando key={key}")
            
            # Verificar conexión
            self.redis_client.ping()
            
            exists = bool(self.redis_client.exists(key))
            print(f"DEBUG RedisService.exists: Key {key} exists={exists}")
            
            logger.debug(f"Cache exists - key: {key}, exists: {exists}")
            return exists
            
        except redis.RedisError as e:
            logger.error(f"Redis error verificando cache: {e}")
            print(f"DEBUG RedisService.exists: Redis error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado verificando cache: {e}")
            print(f"DEBUG RedisService.exists: Error inesperado: {e}")
            return False

    def set_blacklist_token(self, jti: str, expires_at: datetime, session: Session = None) -> bool:
        """Método específico para blacklist de tokens"""
        blacklist_key = f"blacklist_{jti}"
        print(f"DEBUG RedisService.set_blacklist_token: jti={jti}, key={blacklist_key}")
        return self.set(blacklist_key, "revoked", expires_at, session)

    def is_token_blacklisted(self, jti: str, session: Session = None) -> bool:
        """Método específico para verificar blacklist de tokens"""
        blacklist_key = f"blacklist_{jti}"
        print(f"DEBUG RedisService.is_token_blacklisted: jti={jti}, key={blacklist_key}")
        return self.exists(blacklist_key, session)

    def cleanup_expired(self):
        """Redis maneja expiración automáticamente, este método es no-op"""
        logger.info("Redis maneja la expiración automáticamente")
        print("DEBUG RedisService.cleanup_expired: No-op - Redis maneja expiración automática")

    # Test de conectividad
    def test_connection(self) -> bool:
        """Test manual de conexión"""
        try:
            result = self.redis_client.ping()
            print(f"DEBUG RedisService.test_connection: Ping result={result}")
            return result
        except Exception as e:
            print(f"DEBUG RedisService.test_connection: Error={e}")
            return False

    # Métodos legacy para backward compatibility
    def insert_data(self, key: str, value: str, expires_at: Optional[datetime], session: Session = None) -> bool:
        """Método legacy - usar set() en su lugar"""
        return self.set(key, value, expires_at, session)

    def retrieve_data(self, key: str, session: Session = None) -> Optional[str]:
        """Método legacy - usar get() en su lugar"""
        result = self.get(key, session)
        return str(result) if result is not None else None