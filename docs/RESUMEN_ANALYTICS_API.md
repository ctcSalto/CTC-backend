# Google Analytics 4 API - Resumen Ejecutivo

## 🚀 Quick Start

**URL Base:** `https://backend-backend-ctc-develop.vtu0xl.easypanel.host`

### Endpoints Principales

| Endpoint | Descripción | Uso Recomendado |
|----------|-------------|-----------------|
| `GET /api/analytics` | Métricas básicas | Cards de resumen |
| `GET /api/analytics/traffic-sources` | Fuentes de tráfico | Gráfico de pastel |
| `GET /api/analytics/top-pages` | Páginas más visitadas | Tabla/ranking |
| `GET /api/analytics/devices` | Desglose por dispositivo | Gráfico de barras |
| `GET /api/analytics/complete-report` | Todo junto | Dashboard completo |

### Ejemplo Rápido

```javascript
// Obtener todo para un dashboard (últimos 30 días)
const response = await fetch(
  'https://backend-backend-ctc-develop.vtu0xl.easypanel.host/api/analytics/complete-report?days_ago=30'
);
const { data } = await response.json();

// data.overview = métricas generales
// data.traffic_sources = top fuentes
// data.top_pages = páginas populares
// data.devices = mobile/desktop/tablet
```

---

## 📊 Parámetros Comunes

Todos los endpoints aceptan estos parámetros opcionales:

```
?days_ago=30              # Últimos X días (default: 7)
?start_date=2024-01-01    # Fecha inicio (YYYY-MM-DD)
?end_date=2024-01-31      # Fecha fin (YYYY-MM-DD)
?limit=10                 # Límite de resultados (solo algunos endpoints)
```

---

## 💡 Ejemplos de UI

### 1. Cards de Resumen
```javascript
// GET /api/analytics?days_ago=30
{
  "sessions": 1250,           // → "1,250 Sesiones"
  "active_users": 980,        // → "980 Usuarios"
  "page_views": 4500,         // → "4,500 Páginas Vistas"
  "bounce_rate": 45.3         // → "45.3% Tasa de Rebote"
}
```

### 2. Gráfico de Pastel (Fuentes)
```javascript
// GET /api/analytics/traffic-sources?limit=5
[
  { "source": "google", "medium": "organic", "sessions": 850 },
  { "source": "facebook", "medium": "social", "sessions": 200 },
  { "source": "direct", "medium": "(none)", "sessions": 150 }
]
// Mostrar: "google (organic): 850 sesiones"
```

### 3. Tabla de Páginas
```javascript
// GET /api/analytics/top-pages?limit=10
[
  {
    "page_title": "Inicio",
    "page_path": "/",
    "page_views": 1500,
    "users": 900
  }
]
```

---

## ⚡ Tips para Frontend

1. **Usa `/complete-report`** si necesitas múltiples métricas (1 request en vez de 4)
2. **Cachea por 10 minutos** (los datos de GA4 no cambian cada segundo)
3. **Muestra loading states** (puede tardar 2-3 segundos)
4. **Maneja casos de "sin datos"** (cuando las métricas son 0)
5. **Valida fechas** antes de enviar (YYYY-MM-DD)

---

## 🎨 Componente React de Ejemplo

```jsx
import { useState, useEffect } from 'react';

function AnalyticsDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/analytics/complete-report?days_ago=30')
      .then(res => res.json())
      .then(result => {
        setData(result.data);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Cargando...</div>;

  return (
    <div className="dashboard">
      {/* Métricas principales */}
      <div className="metrics">
        <MetricCard
          title="Sesiones"
          value={data.overview.sessions}
        />
        <MetricCard
          title="Usuarios"
          value={data.overview.active_users}
        />
        <MetricCard
          title="Páginas Vistas"
          value={data.overview.page_views}
        />
        <MetricCard
          title="Tasa de Rebote"
          value={`${data.overview.bounce_rate}%`}
        />
      </div>

      {/* Gráficos */}
      <div className="charts">
        <PieChart
          title="Fuentes de Tráfico"
          data={data.traffic_sources}
        />
        <BarChart
          title="Dispositivos"
          data={data.devices}
        />
      </div>

      {/* Tabla */}
      <PagesTable data={data.top_pages} />
    </div>
  );
}
```

---

## 📝 Checklist de Integración

- [ ] Probar endpoint de health check
- [ ] Implementar loading states
- [ ] Manejar errores (sin conexión, timeout, etc.)
- [ ] Cachear respuestas (10 min recomendado)
- [ ] Validar parámetros de fecha
- [ ] Mostrar mensaje cuando no hay datos
- [ ] Implementar selector de período (7/30/90 días)
- [ ] Formatear números (1,250 en vez de 1250)
- [ ] Agregar tooltips explicativos

---

## 🔗 Recursos

- **Documentación completa:** Ver `API_GOOGLE_ANALYTICS_FRONTEND.md`
- **API Docs interactiva:** `/docs` o `/docs-scalar`
- **Health check:** `/api/analytics/health`
