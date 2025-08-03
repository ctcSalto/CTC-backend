from sqlmodel import Session, text
from typing import Optional, Any
from sqlalchemy.exc import IntegrityError, NoResultFound
from datetime import datetime
import json

class CacheService:
    def __init__(self, session: Session):
        self._init_cache_if_needed(session)

    def _init_cache_if_needed(self, session: Session):
        try:
            # Verificar si la tabla existe
            table_exists = session.exec(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'cache_store'
                );
            """)).first()
            
            if not table_exists[0]:  # Si no existe, crear todo
                self._create_cache_infrastructure(session)
                
        except Exception as e:
            print(f"Error verificando/creando cache: {e}")

    def _create_cache_infrastructure(self, session: Session):
        # Crear extensión
        session.exec(text("CREATE EXTENSION IF NOT EXISTS pg_cron;"))
        
        # Crear tabla UNLOGGED
        session.exec(text("""
            CREATE UNLOGGED TABLE cache_store (
                key TEXT PRIMARY KEY, 
                value TEXT, 
                expires_at TIMESTAMP
            );
        """))
        
        # Crear índices para performance
        session.exec(text("""
            CREATE INDEX IF NOT EXISTS idx_cache_expires 
            ON cache_store (expires_at) WHERE expires_at IS NOT NULL;
        """))
        
        # Verificar y crear cron job
        existing_cron = session.exec(text("""
            SELECT 1 FROM cron.job 
            WHERE jobname = 'clear_cache_store'
        """)).first()
        
        if not existing_cron:
            session.exec(text("""
                SELECT cron.schedule(
                    'clear_cache_store', 
                    '0 * * * *', 
                    $$ DELETE FROM cache_store WHERE expires_at IS NOT NULL AND expires_at <= NOW(); $$
                );
            """))
        
        print("Cache infrastructure creada exitosamente")

    def _serialize_value(self, value: Any) -> str:
        """Convierte cualquier valor a string, serializando JSON si es necesario"""
        if isinstance(value, str):
            return value
        else:
            # Dict, list, int, float, bool, etc. -> JSON
            return json.dumps(value, ensure_ascii=False)

    def _deserialize_value(self, value_str: str) -> Any:
        """Intenta deserializar JSON, si falla retorna el string original"""
        try:
            return json.loads(value_str)
        except (json.JSONDecodeError, TypeError):
            # Si no es JSON válido, retornar como string
            return value_str

    def set(self, key: str, value: Any, expires_at: Optional[datetime], session: Session) -> bool:
        """
        Guarda un valor en cache con auto-serialización
        
        Args:
            key: Clave del cache
            value: Cualquier valor (str, dict, list, int, etc.)
            expires_at: Fecha de expiración (None para permanente)
            session: Sesión de BD
        
        Returns:
            bool: True si se guardó exitosamente
        """
        try:
            print(f"DEBUG CacheService.set: Intentando guardar - key: {key}, value: {value}, expires_at: {expires_at}")
            print(f"DEBUG CacheService.set: Session ID: {id(session)}")
            
            serialized_value = self._serialize_value(value)
            
            result = session.execute(
                text("INSERT INTO cache_store (key, value, expires_at) VALUES (:key, :value, :expires_at) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, expires_at = EXCLUDED.expires_at"),
                {"key": key, "value": serialized_value, "expires_at": expires_at}
            )
            
            print(f"DEBUG CacheService.set: Query ejecutada, rowcount: {result.rowcount}")
            
            print(f"DEBUG CacheService.set: Guardado exitosamente - key: {key}")
            return True
        except Exception as e:
            print(f"DEBUG CacheService.set: Error guardando en cache: {e}")
            import traceback
            traceback.print_exc()
            raise ValueError(f"Error al guardar en cache: {e}")

    def get(self, key: str, session: Session) -> Optional[Any]:
        """
        Recupera un valor del cache con auto-deserialización
        
        Args:
            key: Clave del cache
            session: Sesión de BD
            
        Returns:
            Any: El valor deserializado o None si no existe/expiró
        """
        try:
            # ✅ Cambiar session.exec() por session.execute()
            result = session.execute(
                text("SELECT value FROM cache_store WHERE key = :key AND (expires_at IS NULL OR expires_at > NOW())"),
                {"key": key}
            ).first()
            
            if result:
                return self._deserialize_value(result[0])
            return None
            
        except Exception as e:
            print(f"Error recuperando del cache: {e}")
            return None

    def delete(self, key: str, session: Session) -> bool:
        """
        Elimina una clave del cache
        
        Args:
            key: Clave a eliminar
            session: Sesión de BD
            
        Returns:
            bool: True si se eliminó exitosamente
        """
        try:
            # ✅ Cambiar session.exec() por session.execute()
            result = session.execute(
                text("DELETE FROM cache_store WHERE key = :key"),
                {"key": key}
            )
            print(f"DEBUG CacheService.delete: Eliminado exitosamente - key: {key}")
            return result.rowcount > 0
        except Exception as e:
            print(f"Error eliminando del cache: {e}")
            return False

    def exists(self, key: str, session: Session) -> bool:
        """
        Verifica si una clave existe en el cache y no ha expirado
        
        Args:
            key: Clave a verificar
            session: Sesión de BD
            
        Returns:
            bool: True si la clave existe y no ha expirado
        """
        try:
            print(f"DEBUG CacheService.exists: Verificando key: {key}")
            print(f"DEBUG CacheService.exists: Session ID: {id(session)}")
            
            # Primero, verificar si la clave existe sin importar expiración
            result_any = session.execute(
                text("SELECT value, expires_at FROM cache_store WHERE key = :key"),
                {"key": key}
            ).first()
            
            if result_any:
                print(f"DEBUG CacheService.exists: Registro encontrado - value: {result_any[0]}, expires_at: {result_any[1]}")
            else:
                print(f"DEBUG CacheService.exists: NO se encontró registro para key: {key}")
                
            # ✅ CAMBIO PRINCIPAL: Usar UTC en la comparación
            result = session.execute(
                text("""
                    SELECT 1 FROM cache_store 
                    WHERE key = :key 
                    AND (expires_at IS NULL OR expires_at > NOW() AT TIME ZONE 'UTC')
                """),
                {"key": key}
            ).first()
            
            exists = result is not None
            print(f"DEBUG CacheService.exists: key: {key}, exists (no expirado): {exists}")
            
            # ✅ DEBUG ADICIONAL: Verificar la comparación de tiempos
            if result_any and result_any[1] is not None:  # Si tiene expires_at
                debug_result = session.execute(
                    text("""
                        SELECT 
                            expires_at,
                            NOW() AT TIME ZONE 'UTC' as now_utc,
                            NOW() as now_local,
                            expires_at > NOW() AT TIME ZONE 'UTC' as is_valid_utc,
                            expires_at > NOW() as is_valid_local
                        FROM cache_store 
                        WHERE key = :key
                    """),
                    {"key": key}
                ).first()
                
                if debug_result:
                    print(f"DEBUG timezone comparison:")
                    print(f"  expires_at: {debug_result[0]}")
                    print(f"  now_utc: {debug_result[1]}")
                    print(f"  now_local: {debug_result[2]}")
                    print(f"  is_valid_utc: {debug_result[3]}")
                    print(f"  is_valid_local: {debug_result[4]}")
            
            # Debugging adicional: mostrar todos los registros de blacklist
            all_blacklist = session.execute(
                text("SELECT key, value, expires_at FROM cache_store WHERE key LIKE 'blacklist_%'")
            ).fetchall()
            print(f"DEBUG CacheService.exists: Todos los blacklist en BD: {len(all_blacklist)} registros")
            for record in all_blacklist:
                print(f"  - {record[0]}: value={record[1]}, expires_at={record[2]}")
                
            return exists
            
        except Exception as e:
            print(f"DEBUG CacheService.exists: Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    # Métodos legacy para backward compatibility
    def insert_data(self, key: str, value: str, expires_at: Optional[datetime], session: Session) -> bool:
        """Método legacy - usar set() en su lugar"""
        return self.set(key, value, expires_at, session)

    def retrieve_data(self, key: str, session: Session) -> Optional[str]:
        """Método legacy - usar get() en su lugar"""
        result = self.get(key, session)
        return str(result) if result is not None else None