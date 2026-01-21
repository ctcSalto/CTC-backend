# API de Google Analytics 4 - Documentación para Frontend

Esta documentación describe todos los endpoints disponibles de Google Analytics 4 para su integración en el frontend.

**URL Base (Desarrollo):** `https://backend-backend-ctc-develop.vtu0xl.easypanel.host`
**URL Base (Producción):** `[TU_URL_DE_PRODUCCION]`

---

## 📊 Endpoints Disponibles

### 1. Health Check
Verifica que el servicio de Google Analytics esté correctamente configurado.

**Endpoint:** `GET /api/analytics/health`

**Ejemplo de Request:**
```javascript
fetch('https://backend-backend-ctc-develop.vtu0xl.easypanel.host/api/analytics/health')
  .then(response => response.json())
  .then(data => console.log(data));
```

**Respuesta Exitosa:**
```json
{
  "status": "success",
  "configured": true,
  "property_id": "properties/507129143",
  "message": "Google Analytics 4 configurado correctamente"
}
```

**Respuesta de Error:**
```json
{
  "status": "error",
  "configured": false,
  "issues": [
    "GOOGLE_APPLICATION_CREDENTIALS_JSON no está configurado"
  ]
}
```

---

### 2. Métricas Básicas
Obtiene las métricas principales de tu sitio web.

**Endpoint:** `GET /api/analytics`

**Parámetros (Query String):**
| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `days_ago` | `number` | No | `7` | Días hacia atrás desde hoy (1-365) |
| `start_date` | `string` | No | - | Fecha inicio (YYYY-MM-DD) |
| `end_date` | `string` | No | - | Fecha fin (YYYY-MM-DD) |

**Ejemplo de Request:**
```javascript
// Últimos 7 días (por defecto)
fetch('https://backend-backend-ctc-develop.vtu0xl.easypanel.host/api/analytics')
  .then(response => response.json())
  .then(data => console.log(data));

// Últimos 30 días
fetch('https://backend-backend-ctc-develop.vtu0xl.easypanel.host/api/analytics?days_ago=30')
  .then(response => response.json())
  .then(data => console.log(data));

// Rango personalizado
fetch('https://backend-backend-ctc-develop.vtu0xl.easypanel.host/api/analytics?start_date=2024-01-01&end_date=2024-01-31')
  .then(response => response.json())
  .then(data => console.log(data));
```

**Respuesta:**
```json
{
  "status": "success",
  "data": {
    "sessions": 1250,
    "active_users": 980,
    "page_views": 4500,
    "bounce_rate": 45.3,
    "avg_session_duration": 180.5,
    "sessions_per_user": 1.27,
    "date_range": {
      "start_date": "2024-01-15",
      "end_date": "2024-01-22"
    }
  }
}
```

**Campos de la respuesta:**
- `sessions`: Número total de sesiones
- `active_users`: Usuarios activos únicos
- `page_views`: Total de páginas vistas
- `bounce_rate`: Tasa de rebote en porcentaje (0-100)
- `avg_session_duration`: Duración promedio de sesión en segundos
- `sessions_per_user`: Promedio de sesiones por usuario
- `date_range`: Período consultado

---

### 3. Fuentes de Tráfico
Obtiene las principales fuentes de tráfico (de dónde vienen tus visitantes).

**Endpoint:** `GET /api/analytics/traffic-sources`

**Parámetros (Query String):**
| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `days_ago` | `number` | No | `7` | Días hacia atrás desde hoy (1-365) |
| `start_date` | `string` | No | - | Fecha inicio (YYYY-MM-DD) |
| `end_date` | `string` | No | - | Fecha fin (YYYY-MM-DD) |
| `limit` | `number` | No | `10` | Número máximo de resultados (1-50) |

**Ejemplo de Request:**
```javascript
// Top 10 fuentes de los últimos 30 días
fetch('https://backend-backend-ctc-develop.vtu0xl.easypanel.host/api/analytics/traffic-sources?days_ago=30&limit=10')
  .then(response => response.json())
  .then(data => console.log(data));
```

**Respuesta:**
```json
{
  "status": "success",
  "data": [
    {
      "source": "google",
      "medium": "organic",
      "sessions": 850,
      "users": 720
    },
    {
      "source": "facebook",
      "medium": "social",
      "sessions": 200,
      "users": 180
    },
    {
      "source": "direct",
      "medium": "(none)",
      "sessions": 150,
      "users": 130
    }
  ],
  "count": 3
}
```

**Tipos de medium comunes:**
- `organic`: Búsqueda orgánica (Google, Bing, etc.)
- `social`: Redes sociales
- `referral`: Enlaces desde otros sitios
- `(none)`: Tráfico directo
- `cpc`: Publicidad de pago por clic
- `email`: Campañas de email

---

### 4. Páginas Más Visitadas
Obtiene las páginas con más visitas de tu sitio.

**Endpoint:** `GET /api/analytics/top-pages`

**Parámetros (Query String):**
| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `days_ago` | `number` | No | `7` | Días hacia atrás desde hoy (1-365) |
| `start_date` | `string` | No | - | Fecha inicio (YYYY-MM-DD) |
| `end_date` | `string` | No | - | Fecha fin (YYYY-MM-DD) |
| `limit` | `number` | No | `10` | Número máximo de resultados (1-50) |

**Ejemplo de Request:**
```javascript
// Top 10 páginas de los últimos 7 días
fetch('https://backend-backend-ctc-develop.vtu0xl.easypanel.host/api/analytics/top-pages?days_ago=7&limit=10')
  .then(response => response.json())
  .then(data => console.log(data));
```

**Respuesta:**
```json
{
  "status": "success",
  "data": [
    {
      "page_title": "Inicio",
      "page_path": "/",
      "page_views": 1500,
      "users": 900,
      "avg_session_duration": 200.5
    },
    {
      "page_title": "Carreras",
      "page_path": "/carreras",
      "page_views": 850,
      "users": 650,
      "avg_session_duration": 180.2
    },
    {
      "page_title": "Contacto",
      "page_path": "/contacto",
      "page_views": 420,
      "users": 380,
      "avg_session_duration": 95.3
    }
  ],
  "count": 3
}
```

---

### 5. Desglose por Dispositivo
Obtiene estadísticas agrupadas por tipo de dispositivo (móvil, escritorio, tablet).

**Endpoint:** `GET /api/analytics/devices`

**Parámetros (Query String):**
| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `days_ago` | `number` | No | `7` | Días hacia atrás desde hoy (1-365) |
| `start_date` | `string` | No | - | Fecha inicio (YYYY-MM-DD) |
| `end_date` | `string` | No | - | Fecha fin (YYYY-MM-DD) |

**Ejemplo de Request:**
```javascript
fetch('https://backend-backend-ctc-develop.vtu0xl.easypanel.host/api/analytics/devices?days_ago=30')
  .then(response => response.json())
  .then(data => console.log(data));
```

**Respuesta:**
```json
{
  "status": "success",
  "data": [
    {
      "device_category": "mobile",
      "sessions": 650,
      "users": 550,
      "bounce_rate": 48.5
    },
    {
      "device_category": "desktop",
      "sessions": 500,
      "users": 380,
      "bounce_rate": 40.2
    },
    {
      "device_category": "tablet",
      "sessions": 100,
      "users": 50,
      "bounce_rate": 52.1
    }
  ],
  "count": 3
}
```

**Categorías de dispositivo:**
- `mobile`: Dispositivos móviles
- `desktop`: Computadoras de escritorio
- `tablet`: Tabletas

---

### 6. Reporte Completo
Obtiene todas las métricas en una sola petición (recomendado para dashboards).

**Endpoint:** `GET /api/analytics/complete-report`

**Parámetros (Query String):**
| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `days_ago` | `number` | No | `7` | Días hacia atrás desde hoy (1-365) |
| `start_date` | `string` | No | - | Fecha inicio (YYYY-MM-DD) |
| `end_date` | `string` | No | - | Fecha fin (YYYY-MM-DD) |

**Ejemplo de Request:**
```javascript
fetch('https://backend-backend-ctc-develop.vtu0xl.easypanel.host/api/analytics/complete-report?days_ago=30')
  .then(response => response.json())
  .then(data => console.log(data));
```

**Respuesta:**
```json
{
  "status": "success",
  "data": {
    "overview": {
      "sessions": 1250,
      "active_users": 980,
      "page_views": 4500,
      "bounce_rate": 45.3,
      "avg_session_duration": 180.5,
      "sessions_per_user": 1.27,
      "date_range": {
        "start_date": "2024-01-15",
        "end_date": "2024-02-15"
      }
    },
    "traffic_sources": [
      {
        "source": "google",
        "medium": "organic",
        "sessions": 850,
        "users": 720
      }
    ],
    "top_pages": [
      {
        "page_title": "Inicio",
        "page_path": "/",
        "page_views": 1500,
        "users": 900,
        "avg_session_duration": 200.5
      }
    ],
    "devices": [
      {
        "device_category": "mobile",
        "sessions": 650,
        "users": 550,
        "bounce_rate": 48.5
      }
    ]
  }
}
```

---

## 🔧 Ejemplos de Integración

### React/Next.js

```javascript
// hooks/useAnalytics.js
import { useState, useEffect } from 'react';

const API_BASE = 'https://backend-backend-ctc-develop.vtu0xl.easypanel.host';

export function useAnalytics(daysAgo = 7) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/analytics/complete-report?days_ago=${daysAgo}`)
      .then(response => response.json())
      .then(result => {
        setData(result.data);
        setLoading(false);
      })
      .catch(err => {
        setError(err);
        setLoading(false);
      });
  }, [daysAgo]);

  return { data, loading, error };
}

// Componente de uso
function Dashboard() {
  const { data, loading, error } = useAnalytics(30);

  if (loading) return <div>Cargando...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      <h1>Dashboard de Analytics</h1>
      <div>
        <h2>Resumen General</h2>
        <p>Sesiones: {data.overview.sessions}</p>
        <p>Usuarios: {data.overview.active_users}</p>
        <p>Páginas vistas: {data.overview.page_views}</p>
      </div>
    </div>
  );
}
```

### Vanilla JavaScript

```javascript
// Obtener métricas básicas
async function getBasicMetrics(daysAgo = 7) {
  try {
    const response = await fetch(
      `https://backend-backend-ctc-develop.vtu0xl.easypanel.host/api/analytics?days_ago=${daysAgo}`
    );
    const result = await response.json();

    if (result.status === 'success') {
      return result.data;
    } else {
      throw new Error('Error obteniendo métricas');
    }
  } catch (error) {
    console.error('Error:', error);
    return null;
  }
}

// Uso
getBasicMetrics(30).then(data => {
  console.log('Sesiones:', data.sessions);
  console.log('Usuarios:', data.active_users);
  console.log('Páginas vistas:', data.page_views);
});
```

### Vue.js

```javascript
// store/analytics.js
import { ref } from 'vue';

export const useAnalyticsStore = () => {
  const metrics = ref(null);
  const loading = ref(false);
  const error = ref(null);

  const fetchMetrics = async (daysAgo = 7) => {
    loading.value = true;
    error.value = null;

    try {
      const response = await fetch(
        `https://backend-backend-ctc-develop.vtu0xl.easypanel.host/api/analytics?days_ago=${daysAgo}`
      );
      const result = await response.json();
      metrics.value = result.data;
    } catch (err) {
      error.value = err.message;
    } finally {
      loading.value = false;
    }
  };

  return { metrics, loading, error, fetchMetrics };
};
```

---

## 📈 Casos de Uso Comunes

### 1. Dashboard Principal
```javascript
// Obtener reporte completo de los últimos 30 días
fetch('/api/analytics/complete-report?days_ago=30')
  .then(response => response.json())
  .then(data => {
    // Mostrar todas las métricas en el dashboard
    renderDashboard(data.data);
  });
```

### 2. Gráfico de Fuentes de Tráfico
```javascript
// Obtener top 5 fuentes para un gráfico de pastel
fetch('/api/analytics/traffic-sources?days_ago=30&limit=5')
  .then(response => response.json())
  .then(data => {
    const chartData = data.data.map(source => ({
      name: `${source.source} (${source.medium})`,
      value: source.sessions
    }));
    renderPieChart(chartData);
  });
```

### 3. Tabla de Páginas Populares
```javascript
// Obtener top 10 páginas para una tabla
fetch('/api/analytics/top-pages?days_ago=7&limit=10')
  .then(response => response.json())
  .then(data => {
    const tableData = data.data.map(page => ({
      título: page.page_title,
      ruta: page.page_path,
      vistas: page.page_views,
      usuarios: page.users
    }));
    renderTable(tableData);
  });
```

### 4. Comparación de Períodos
```javascript
// Comparar último mes vs mes anterior
Promise.all([
  fetch('/api/analytics?start_date=2024-01-01&end_date=2024-01-31').then(r => r.json()),
  fetch('/api/analytics?start_date=2023-12-01&end_date=2023-12-31').then(r => r.json())
]).then(([currentMonth, previousMonth]) => {
  const growth = ((currentMonth.data.sessions - previousMonth.data.sessions) / previousMonth.data.sessions) * 100;
  console.log(`Crecimiento: ${growth.toFixed(2)}%`);
});
```

---

## ⚠️ Manejo de Errores

Todos los endpoints pueden retornar errores. Siempre verifica el campo `status`:

```javascript
fetch('/api/analytics')
  .then(response => response.json())
  .then(result => {
    if (result.status === 'success') {
      // Procesar datos exitosos
      console.log(result.data);
    } else {
      // Manejar error
      console.error('Error:', result.detail || result.issues);
    }
  })
  .catch(error => {
    // Error de red o servidor
    console.error('Error de conexión:', error);
  });
```

**Códigos de Estado HTTP:**
- `200`: Éxito
- `400`: Error en parámetros (fecha inválida, etc.)
- `503`: Servicio no configurado
- `500`: Error interno del servidor

---

## 💡 Mejores Prácticas

1. **Cachear las respuestas**: Los datos de Analytics no cambian cada segundo. Implementa caché de al menos 5-10 minutos.

2. **Usar el reporte completo para dashboards**: En vez de hacer 4 peticiones separadas, usa `/complete-report`.

3. **Implementar loading states**: Las peticiones a Analytics pueden tardar 2-3 segundos.

4. **Validar fechas**: Si usas rangos personalizados, valida que `start_date < end_date`.

5. **Limitar el rango de fechas**: No consultes más de 1 año de datos de una vez para evitar timeouts.

6. **Mostrar feedback de "sin datos"**: Si las métricas son 0, muestra un mensaje apropiado al usuario.

---

## 🔍 Preguntas Frecuentes

**Q: ¿Con qué frecuencia se actualizan los datos?**
A: Los datos de Google Analytics 4 tienen un delay de 24-48 horas. Los datos de "hoy" pueden estar incompletos.

**Q: ¿Puedo consultar datos en tiempo real?**
A: No, estos endpoints usan la API de reportes históricos. Para tiempo real necesitarías la Realtime Reporting API.

**Q: ¿Hay límite de peticiones?**
A: Google Analytics tiene un límite de 10 peticiones por segundo y 10,000 peticiones por día por proyecto.

**Q: ¿Qué zona horaria usan las fechas?**
A: Las fechas se interpretan en la zona horaria configurada en tu propiedad de GA4.

---

## 📞 Contacto y Soporte

Si necesitas ayuda con la integración o tienes preguntas, contacta al equipo de backend.

**Endpoints de documentación interactiva:**
- Swagger UI: `https://backend-backend-ctc-develop.vtu0xl.easypanel.host/docs`
- Scalar UI: `https://backend-backend-ctc-develop.vtu0xl.easypanel.host/docs-scalar`
