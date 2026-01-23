# Google Analytics 4 Service

Servicio para obtener métricas de Google Analytics 4 en tu backend FastAPI.

## Configuración Rápida

### Desarrollo (Archivo JSON)

1. Coloca tu archivo de credenciales en `./credentials/ga4-service-account.json`

2. Configura tu `.env`:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=./credentials/ga4-service-account.json
   GA4_PROPERTY_ID=properties/123456789
   ```

### Producción (JSON como String) ⭐ Recomendado

1. Copia **TODO** el contenido de tu archivo JSON de credenciales

2. Configura tu `.env` o variables de entorno:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account","project_id":"...",...}'
   GA4_PROPERTY_ID=properties/123456789
   ```

## Uso

```python
from external_services.google.analytics import analytics_service

# Obtener métricas básicas de los últimos 7 días
metrics = analytics_service.get_basic_metrics(days_ago=7)

# Obtener métricas de un período específico
metrics = analytics_service.get_basic_metrics(
    start_date="2024-01-01",
    end_date="2024-01-31"
)

# Obtener fuentes de tráfico
sources = analytics_service.get_traffic_sources(days_ago=30, limit=10)

# Obtener páginas más visitadas
pages = analytics_service.get_top_pages(days_ago=7, limit=10)

# Obtener reporte completo
report = analytics_service.get_complete_report(days_ago=7)
```

## Variables de Entorno

### Opción 1: Archivo JSON (Desarrollo)
```env
GOOGLE_APPLICATION_CREDENTIALS=./credentials/ga4-service-account.json
GA4_PROPERTY_ID=properties/123456789
```

### Opción 2: JSON String (Producción)
```env
GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account",...}'
GA4_PROPERTY_ID=properties/123456789
```

**El servicio intentará usar `GOOGLE_APPLICATION_CREDENTIALS_JSON` primero, si no lo encuentra, usará `GOOGLE_APPLICATION_CREDENTIALS`.**

## Documentación Completa

Para instrucciones detalladas, consulta: [docs/GOOGLE_ANALYTICS_SETUP.md](../../../docs/GOOGLE_ANALYTICS_SETUP.md)

## Endpoints Disponibles

Todos los endpoints están en `/api/analytics`:

- `GET /api/analytics` - Métricas básicas
- `GET /api/analytics/traffic-sources` - Fuentes de tráfico
- `GET /api/analytics/top-pages` - Páginas más visitadas
- `GET /api/analytics/devices` - Desglose por dispositivo
- `GET /api/analytics/complete-report` - Reporte completo
- `GET /api/analytics/health` - Verificar configuración

## Métricas Disponibles

- **sessions**: Sesiones totales
- **active_users**: Usuarios activos únicos
- **page_views**: Páginas vistas
- **bounce_rate**: Tasa de rebote (%)
- **avg_session_duration**: Duración promedio de sesión (segundos)
- **sessions_per_user**: Promedio de sesiones por usuario

## Troubleshooting

### Error: "No se encontraron credenciales"

Verifica que configuraste una de estas variables:
- `GOOGLE_APPLICATION_CREDENTIALS_JSON` (recomendado para producción)
- `GOOGLE_APPLICATION_CREDENTIALS` (recomendado para desarrollo)

### Error: "GA4_PROPERTY_ID no está configurado"

Configura tu Property ID en formato: `properties/123456789`

Lo encuentras en: Google Analytics > Admin > Property Settings

### Error: "Permission Denied"

1. Ve a Google Analytics > Admin > Property Access
2. Agrega el email de tu cuenta de servicio
3. Dale rol de "Visor"
4. Espera unos minutos para que se propaguen los permisos
