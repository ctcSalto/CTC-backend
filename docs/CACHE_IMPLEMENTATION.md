# Redis Cache Implementation for Careers

## Descripción General

Se implementó un sistema de caché Redis para mejorar el rendimiento de los endpoints de carreras, especialmente para dispositivos móviles que experimentaban problemas de timeout y lentitud.

## Arquitectura

### Patrón Implementado: Cache-Aside (Lazy Loading)

El patrón cache-aside funciona de la siguiente manera:

1. **GET Endpoints (Lectura)**:
   - La aplicación primero intenta leer del cache Redis
   - Si existe (cache HIT), retorna inmediatamente
   - Si no existe (cache MISS), consulta la base de datos
   - Después de obtener de la BD, actualiza el cache para futuros requests

2. **POST/PUT/DELETE Endpoints (Escritura)**:
   - La aplicación modifica la base de datos primero
   - Después de modificar, invalida todo el cache relacionado
   - El próximo GET reconstruirá el cache con datos frescos

## Estructura de Archivos

```
database/services/cache/
├── __init__.py              # Exports del módulo
└── cache_service.py         # CacheService principal
```

## CacheService

Ubicación: `database/services/cache/cache_service.py`

### Características

- Serialización/deserialización automática de modelos Pydantic
- Manejo de múltiples tipos de cache (individual, listas, optimizados)
- TTL (Time To Live) configurable
- Warmup automático en startup
- Invalidación granular y total
- Health check integrado

### Prefijos de Cache

```python
CAREER_PREFIX = "career:"                    # career:123
CAREERS_LIST_PREFIX = "careers:list:"        # careers:list:0:10
CAREERS_OPTIMIZED_PREFIX = "careers:optimized:"  # careers:optimized:0:10
CAREERS_PUBLISHED_PREFIX = "careers:published:"  # careers:published:0:10
CAREERS_SIMPLE_PREFIX = "careers:simple:"    # careers:simple:random:4
```

### Métodos Principales

#### Cache de Lectura

```python
# Cachear una carrera individual
cache_career_optimized(career_id: int, career_data: CareerReadOptimized, ttl: int = 3600)

# Obtener carrera del cache
get_cached_career_optimized(career_id: int) -> Optional[CareerReadOptimized]

# Cachear lista optimizada de carreras
cache_careers_optimized(offset: int, limit: int, published_only: bool, careers: List[CareerReadOptimized], ttl: int = 3600)

# Obtener lista optimizada del cache
get_cached_careers_optimized(offset: int, limit: int, published_only: bool) -> Optional[List[CareerReadOptimized]]
```

#### Invalidación

```python
# Invalidar una carrera específica
invalidate_career(career_id: int) -> bool

# Invalidar todos los caches de carreras
invalidate_all_careers() -> bool
```

#### Warmup

```python
# Precargar cache en startup
warmup_published_careers(session: Session, career_service) -> bool
```

## Integración con FastAPI

### 1. Startup (main.py)

El cache se precarga automáticamente al iniciar la aplicación:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... código de inicio ...

    # Cache warmup for careers
    print("🔄 [STARTUP] Iniciando precarga de cache para carreras...")
    services = get_services()
    with get_db_session() as session:
        warmup_result = services.cacheService.warmup_published_careers(
            session=session,
            career_service=services.careerService
        )
```

**Carreras precargadas**:
- Primera página de carreras optimizadas publicadas (offset=0, limit=10)
- Cada carrera individual de esa página
- TTL de 2 horas (7200 segundos)

### 2. GET Endpoints (routes/career.py)

#### Ejemplo: `/careers-optimized`

```python
@router.get("/careers-optimized", response_model=List[CareerReadOptimized])
async def get_careers_optimized(...):
    # 1. Intentar obtener del cache
    cached_careers = services.cacheService.get_cached_careers_optimized(
        offset=offset,
        limit=limit,
        published_only=True
    )

    if cached_careers is not None:
        show(f"[CACHE HIT] Careers optimized (offset={offset}, limit={limit})")
        return cached_careers

    # 2. Cache miss - consultar BD
    show(f"[CACHE MISS] Careers optimized (offset={offset}, limit={limit}) - querying DB")
    careers = services.careerService.get_careers_optimized(session, offset, limit)
    published_careers = [career for career in careers if career.published]

    # 3. Actualizar cache
    services.cacheService.cache_careers_optimized(
        offset=offset,
        limit=limit,
        published_only=True,
        careers=published_careers
    )

    return published_careers
```

#### Ejemplo: `/career-optimized/{career_id}`

```python
@router.get("/career-optimized/{career_id}", response_model=CareerReadOptimized)
async def get_careers_by_id(...):
    # 1. Intentar obtener del cache
    cached_career = services.cacheService.get_cached_career_optimized(career_id)

    if cached_career is not None and cached_career.published:
        show(f"[CACHE HIT] Career {career_id}")
        return cached_career

    # 2. Cache miss - consultar BD
    show(f"[CACHE MISS] Career {career_id} - querying DB")
    career = services.careerService.get_public_career_optimized_by_id(session, career_id)

    # 3. Actualizar cache
    services.cacheService.cache_career_optimized(career_id, career)

    return career
```

### 3. POST/PUT/DELETE Endpoints

Todos los endpoints que modifican datos invalidan el cache completo:

```python
@router.post("/create", response_model=CareerRead)
async def create_career(...):
    # ... crear carrera en BD ...
    new_career = services.careerService.create_career(career_data, session)

    # Invalidar todo el cache de carreras
    services.cacheService.invalidate_all_careers()
    show(f"[CACHE] Invalidated all career caches after creating career {new_career.careerId}")

    return new_career
```

**Endpoints que invalidan cache**:
- `POST /careers/create` - Crear carrera
- `PUT /careers/{career_id}` - Actualizar carrera
- `PUT /careers/image/{career_id}` - Actualizar imagen
- `PATCH /careers/{career_id}/publish` - Publicar carrera
- `PATCH /careers/{career_id}/unpublish` - Despublicar carrera
- `DELETE /careers/{career_id}` - Eliminar carrera

## Endpoints con Cache Implementado

### Endpoints Públicos (GET)

1. **`GET /careers/careers-optimized`**
   - Cache key: `careers:published:0:10` (ejemplo)
   - TTL: 3600s (1 hora)
   - Retorna carreras publicadas optimizadas

2. **`GET /careers/career-optimized/{career_id}`**
   - Cache key: `career:123` (ejemplo)
   - TTL: 3600s (1 hora)
   - Retorna carrera individual publicada

### Endpoints Admin (GET)

3. **`GET /careers/admin/careers-optimized`**
   - Cache key: `careers:optimized:0:10` (ejemplo)
   - TTL: 3600s (1 hora)
   - Retorna todas las carreras (incluidas no publicadas)

## Configuración

### Variables de Entorno

El cache utiliza las variables Redis existentes:

```bash
REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password
```

### TTL por Defecto

- **Cache normal**: 3600 segundos (1 hora)
- **Cache warmup**: 7200 segundos (2 horas)

Puedes modificar el TTL en cada llamada:

```python
services.cacheService.cache_career_optimized(
    career_id=123,
    career_data=career,
    ttl=7200  # 2 horas
)
```

## Logging y Monitoreo

### Logs de Cache

Todos los eventos de cache se registran:

```python
show(f"[CACHE HIT] Careers optimized (offset={offset}, limit={limit})")
show(f"[CACHE MISS] Career {career_id} - querying DB")
show(f"[CACHE] Invalidated all career caches after creating career {career_id}")
```

### Health Check

Endpoint para verificar salud del cache:

```python
health_info = services.cacheService.health_check()
# {
#     "status": "healthy",
#     "redis_connected": True,
#     "total_keys": 42,
#     "keyspace_hits": 1523,
#     "keyspace_misses": 87
# }
```

## Beneficios

### Performance

1. **Reducción de latencia**: Las consultas cacheadas responden en <10ms vs >100ms de BD
2. **Menos carga en PostgreSQL**: Reduce queries complejas con JOINs y relaciones
3. **Mejor experiencia móvil**: Dispositivos móviles con conexiones lentas se benefician enormemente

### Escalabilidad

1. **Horizontal**: Redis puede distribuirse en múltiples nodos
2. **Vertical**: Reduce necesidad de hardware en servidor de BD
3. **Concurrencia**: Redis maneja miles de requests concurrentes eficientemente

### Disponibilidad

1. **Fallback automático**: Si Redis falla, la app sigue funcionando consultando BD
2. **No crítico en startup**: Si el warmup falla, no impide que la app inicie
3. **Reconexión automática**: RedisService maneja reconexiones automáticamente

## Próximos Pasos (Expansión)

Si el cache de carreras resuelve los problemas de performance, aplicar el mismo patrón a:

### 1. Testimonios

```python
# En database/services/cache/cache_service.py
TESTIMONY_PREFIX = "testimony:"
TESTIMONIES_LIST_PREFIX = "testimonies:list:"

def cache_testimony(testimony_id: int, testimony_data: TestimonyRead, ttl: int = 3600)
def get_cached_testimony(testimony_id: int) -> Optional[TestimonyRead]
def invalidate_all_testimonies() -> bool
```

### 2. Noticias

```python
# En database/services/cache/cache_service.py
NEWS_PREFIX = "news:"
NEWS_LIST_PREFIX = "news:list:"

def cache_news(news_id: int, news_data: NewsRead, ttl: int = 3600)
def get_cached_news(news_id: int) -> Optional[NewsRead]
def invalidate_all_news() -> bool
```

### 3. Usuarios (solo lectura)

```python
# En database/services/cache/cache_service.py
USER_PREFIX = "user:"

def cache_user(user_id: int, user_data: UserRead, ttl: int = 1800)  # 30 min
def get_cached_user(user_id: int) -> Optional[UserRead]
def invalidate_user(user_id: int) -> bool
```

## Testing

### Test Manual

1. **Verificar startup warmup**:
   ```bash
   # Iniciar servidor y verificar logs
   python main.py
   # Buscar: "✅ [STARTUP] Cache de carreras precargado exitosamente"
   ```

2. **Test de GET endpoint**:
   ```bash
   # Primera llamada (cache MISS)
   curl http://localhost:8000/careers/careers-optimized?offset=0&limit=10
   # Verificar log: "[CACHE MISS] Careers optimized (offset=0, limit=10) - querying DB"

   # Segunda llamada (cache HIT)
   curl http://localhost:8000/careers/careers-optimized?offset=0&limit=10
   # Verificar log: "[CACHE HIT] Careers optimized (offset=0, limit=10)"
   ```

3. **Test de invalidación**:
   ```bash
   # Crear una carrera nueva (requiere autenticación admin)
   curl -X POST http://localhost:8000/careers/create -H "Content-Type: multipart/form-data" ...
   # Verificar log: "[CACHE] Invalidated all career caches after creating career {id}"

   # Próxima llamada GET será cache MISS
   curl http://localhost:8000/careers/careers-optimized?offset=0&limit=10
   # Verificar log: "[CACHE MISS] Careers optimized (offset=0, limit=10) - querying DB"
   ```

4. **Verificar Redis directamente**:
   ```bash
   # Conectar a Redis CLI
   redis-cli -h your-redis-host -p 6379 -a your-password

   # Ver todas las keys de carreras
   KEYS career:*
   KEYS careers:*

   # Ver contenido de una key
   GET career:1
   GET careers:published:0:10

   # Ver TTL de una key
   TTL career:1
   ```

### Métricas a Monitorear

1. **Hit Rate**: `keyspace_hits / (keyspace_hits + keyspace_misses)`
   - Objetivo: >80% después de warmup

2. **Latencia P50/P95/P99**: Comparar antes/después de cache
   - Objetivo: Reducción de >50% en P95

3. **Throughput**: Requests por segundo
   - Objetivo: Incremento de >100%

## Troubleshooting

### Problema: Cache no se actualiza después de modificar carrera

**Causa**: `invalidate_all_careers()` no se ejecutó o falló

**Solución**:
```python
# Verificar logs después de POST/PUT/DELETE
# Debe aparecer: "[CACHE] Invalidated all career caches after..."

# Si no aparece, verificar que el endpoint llama a invalidate_all_careers()
services.cacheService.invalidate_all_careers()
```

### Problema: Redis no conecta en startup

**Causa**: Credenciales incorrectas o Redis no disponible

**Solución**:
```python
# El warmup tiene try/except que no detiene el startup
# La app seguirá funcionando sin cache

# Verificar variables de entorno
echo $REDIS_HOST
echo $REDIS_PORT
echo $REDIS_PASSWORD

# Testear conexión manualmente
python -c "from database.database import get_services; get_services().redisService.test_connection()"
```

### Problema: Datos incorrectos en cache

**Causa**: Serialización/deserialización incorrecta

**Solución**:
```python
# Limpiar todo el cache manualmente
redis-cli -h your-host -p 6379 -a your-password FLUSHDB

# O invalidar solo careers
from database.database import get_services
services = get_services()
services.cacheService.invalidate_all_careers()
```

## Consideraciones de Producción

1. **Persistencia**: Redis puede configurarse con RDB o AOF para persistencia
2. **Replicación**: Usar Redis Sentinel o Cluster para alta disponibilidad
3. **Memoria**: Monitorear uso de memoria y configurar `maxmemory-policy`
4. **Seguridad**: Usar passwords fuertes y TLS para conexiones
5. **Monitoreo**: Integrar con Prometheus/Grafana para métricas en tiempo real

## Conclusión

El sistema de cache Redis implementado proporciona:

- Mejora significativa en performance para endpoints de carreras
- Patrón escalable y replicable para otras entidades
- Fallback automático a BD en caso de problemas
- Logging completo para debugging y monitoreo
- Configuración flexible de TTL y estrategias de invalidación

El próximo paso es testear en producción con tráfico real y expandir a otras entidades según sea necesario.
