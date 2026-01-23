# Google Analytics 4 - Nuevos Endpoints de Dashboard

## 📋 Resumen

Se han creado **7 nuevos endpoints** específicos para el dashboard de frontend, además de los 6 endpoints originales.

**Base URL:** `https://backend-backend-ctc-develop.vtu0xl.easypanel.host`

---

## 🆕 Endpoints Nuevos (Dashboard)

### 1. Dashboard Overview
**Endpoint:** `GET /api/analytics/dashboard/overview`

Métricas generales del sitio para cards de resumen.

#### Parámetros
```
?days_ago=30              # Últimos X días (default: 30)
?start_date=2024-01-01    # Fecha inicio (YYYY-MM-DD)
?end_date=2024-01-31      # Fecha fin (YYYY-MM-DD)
```

#### Respuesta
```json
{
  "status": "success",
  "data": {
    "totalSessions": 1250,
    "newUsers": 450,
    "returningUsers": 530,
    "avgSessionDuration": 185.5,
    "trafficSources": [
      {
        "source": "google",
        "medium": "organic",
        "sessions": 850
      },
      {
        "source": "facebook",
        "medium": "social",
        "sessions": 200
      }
    ]
  }
}
```

#### Ejemplo React
```jsx
const [overview, setOverview] = useState(null);

useEffect(() => {
  fetch('/api/analytics/dashboard/overview?days_ago=30')
    .then(res => res.json())
    .then(result => setOverview(result.data));
}, []);

// Uso en componente
<MetricCard title="Sesiones" value={overview.totalSessions} />
<MetricCard title="Usuarios Nuevos" value={overview.newUsers} />
<MetricCard title="Usuarios Recurrentes" value={overview.returningUsers} />
```

---

### 2. Dashboard Cursos
**Endpoint:** `GET /api/analytics/dashboard/courses`

Páginas de cursos más visitadas (filtrado automático por `/cursos/`).

#### Parámetros
```
?days_ago=30     # Últimos X días (default: 30)
?limit=20        # Número de resultados (default: 20)
```

#### Respuesta
```json
{
  "status": "success",
  "data": [
    {
      "rank": 1,
      "pageTitle": "Curso de Python Avanzado",
      "pagePath": "/cursos/python-avanzado",
      "slug": "python-avanzado",
      "pageViews": 1500,
      "users": 850,
      "avgSessionDuration": 320.5,
      "avgEngagementTime": 285.3
    },
    {
      "rank": 2,
      "pageTitle": "Introducción a JavaScript",
      "pagePath": "/cursos/javascript-intro",
      "slug": "javascript-intro",
      "pageViews": 1200,
      "users": 720,
      "avgSessionDuration": 280.0,
      "avgEngagementTime": 250.8
    }
  ],
  "count": 2
}
```

#### Ejemplo React
```jsx
const [courses, setCourses] = useState([]);

useEffect(() => {
  fetch('/api/analytics/dashboard/courses?days_ago=30&limit=20')
    .then(res => res.json())
    .then(result => setCourses(result.data));
}, []);

// Renderizar tabla
<table>
  <thead>
    <tr>
      <th>Ranking</th>
      <th>Curso</th>
      <th>Vistas</th>
      <th>Usuarios</th>
    </tr>
  </thead>
  <tbody>
    {courses.map(course => (
      <tr key={course.slug}>
        <td>{course.rank}</td>
        <td>{course.pageTitle}</td>
        <td>{course.pageViews.toLocaleString()}</td>
        <td>{course.users.toLocaleString()}</td>
      </tr>
    ))}
  </tbody>
</table>
```

---

### 3. Dashboard Noticias
**Endpoint:** `GET /api/analytics/dashboard/news`

Páginas de noticias más visitadas (filtrado automático por `/noticias/`).

#### Parámetros
```
?days_ago=30     # Últimos X días (default: 30)
?limit=20        # Número de resultados (default: 20)
```

#### Respuesta
```json
{
  "status": "success",
  "data": [
    {
      "rank": 1,
      "pageTitle": "Nueva convocatoria de becas 2024",
      "pagePath": "/noticias/becas-2024",
      "slug": "becas-2024",
      "pageViews": 2500,
      "users": 1800,
      "avgSessionDuration": 120.5,
      "avgEngagementTime": 95.3
    }
  ],
  "count": 1
}
```

#### Uso idéntico al endpoint de cursos

---

### 4. Tráfico por Ubicación Geográfica
**Endpoint:** `GET /api/analytics/geographic/locations`

Ranking de tráfico por ciudad y país.

#### Parámetros
```
?days_ago=30     # Últimos X días (default: 30)
?limit=20        # Número de resultados (default: 20)
```

#### Respuesta
```json
{
  "status": "success",
  "data": [
    {
      "rank": 1,
      "city": "Santiago",
      "country": "Chile",
      "sessions": 850,
      "users": 620,
      "pageViews": 3200
    },
    {
      "rank": 2,
      "city": "Valparaíso",
      "country": "Chile",
      "sessions": 320,
      "users": 250,
      "pageViews": 1100
    }
  ],
  "count": 2
}
```

#### Ejemplo para Mapa
```jsx
const [locations, setLocations] = useState([]);

useEffect(() => {
  fetch('/api/analytics/geographic/locations?days_ago=30&limit=50')
    .then(res => res.json())
    .then(result => setLocations(result.data));
}, []);

// Usar con biblioteca de mapas (ej: react-leaflet)
<Map>
  {locations.map(loc => (
    <Marker
      key={`${loc.city}-${loc.country}`}
      position={getCoordinates(loc.city, loc.country)}
      popup={`${loc.city}, ${loc.country}: ${loc.sessions} sesiones`}
    />
  ))}
</Map>
```

---

### 5. Tráfico Local vs Externo
**Endpoint:** `GET /api/analytics/geographic/local-vs-external`

Desglose de tráfico desde un país específico vs resto del mundo.

#### Parámetros
```
?country=Chile   # País a considerar local (default: Chile)
?days_ago=30     # Últimos X días (default: 30)
```

#### Respuesta
```json
{
  "status": "success",
  "data": {
    "local": {
      "country": "Chile",
      "sessions": 1200,
      "users": 850,
      "percentage": 75.5
    },
    "external": {
      "sessions": 390,
      "users": 280,
      "percentage": 24.5
    },
    "total": {
      "sessions": 1590,
      "users": 1130
    }
  }
}
```

#### Ejemplo para Gráfico de Dona
```jsx
const [traffic, setTraffic] = useState(null);

useEffect(() => {
  fetch('/api/analytics/geographic/local-vs-external?country=Chile&days_ago=30')
    .then(res => res.json())
    .then(result => setTraffic(result.data));
}, []);

// Usar con Chart.js o similar
const chartData = {
  labels: ['Local (Chile)', 'Externo'],
  datasets: [{
    data: [traffic.local.sessions, traffic.external.sessions],
    backgroundColor: ['#36A2EB', '#FF6384']
  }]
};
```

---

### 6. Datos Históricos
**Endpoint:** `GET /api/analytics/historical`

Datos día por día de cualquier métrica.

#### Parámetros
```
?metric=sessions              # Métrica a consultar (ver lista abajo)
?days_ago=90                  # Últimos X días (default: 90)
?start_date=2024-01-01        # Fecha inicio
?end_date=2024-03-31          # Fecha fin
```

#### Métricas Disponibles
- `sessions` - Sesiones
- `activeUsers` - Usuarios activos
- `newUsers` - Usuarios nuevos
- `totalUsers` - Total usuarios
- `screenPageViews` - Páginas vistas
- `bounceRate` - Tasa de rebote
- `averageSessionDuration` - Duración promedio de sesión
- `averageEngagementTime` - Tiempo de engagement promedio

#### Respuesta
```json
{
  "status": "success",
  "data": [
    {
      "date": "2024-01-01",
      "value": 150,
      "metric": "sessions"
    },
    {
      "date": "2024-01-02",
      "value": 180,
      "metric": "sessions"
    }
  ],
  "count": 90,
  "metric": "sessions"
}
```

#### Ejemplo para Gráfico de Líneas
```jsx
const [historical, setHistorical] = useState([]);

useEffect(() => {
  fetch('/api/analytics/historical?metric=sessions&days_ago=90')
    .then(res => res.json())
    .then(result => setHistorical(result.data));
}, []);

// Preparar datos para Chart.js
const chartData = {
  labels: historical.map(d => d.date),
  datasets: [{
    label: 'Sesiones',
    data: historical.map(d => d.value),
    borderColor: 'rgb(75, 192, 192)',
    tension: 0.1
  }]
};
```

---

## 📊 Endpoints Originales (Siguen Disponibles)

Estos endpoints ya existían y siguen funcionando normalmente:

### 1. Métricas Básicas
`GET /api/analytics?days_ago=30`

### 2. Fuentes de Tráfico
`GET /api/analytics/traffic-sources?days_ago=30&limit=10`

### 3. Páginas Más Visitadas
`GET /api/analytics/top-pages?days_ago=30&limit=10`

### 4. Desglose por Dispositivo
`GET /api/analytics/devices?days_ago=30`

### 5. Reporte Completo
`GET /api/analytics/complete-report?days_ago=30`

### 6. Health Check
`GET /api/analytics/health`

---

## 🎯 Ejemplo de Dashboard Completo

```jsx
import { useState, useEffect } from 'react';

function AnalyticsDashboard() {
  const [overview, setOverview] = useState(null);
  const [courses, setCourses] = useState([]);
  const [news, setNews] = useState([]);
  const [locations, setLocations] = useState([]);
  const [localVsExternal, setLocalVsExternal] = useState(null);
  const [historical, setHistorical] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [
          overviewRes,
          coursesRes,
          newsRes,
          locationsRes,
          trafficRes,
          historicalRes
        ] = await Promise.all([
          fetch('/api/analytics/dashboard/overview?days_ago=30'),
          fetch('/api/analytics/dashboard/courses?days_ago=30&limit=10'),
          fetch('/api/analytics/dashboard/news?days_ago=30&limit=10'),
          fetch('/api/analytics/geographic/locations?days_ago=30&limit=20'),
          fetch('/api/analytics/geographic/local-vs-external?country=Chile&days_ago=30'),
          fetch('/api/analytics/historical?metric=sessions&days_ago=90')
        ]);

        const [
          overviewData,
          coursesData,
          newsData,
          locationsData,
          trafficData,
          historicalData
        ] = await Promise.all([
          overviewRes.json(),
          coursesRes.json(),
          newsRes.json(),
          locationsRes.json(),
          trafficRes.json(),
          historicalRes.json()
        ]);

        setOverview(overviewData.data);
        setCourses(coursesData.data);
        setNews(newsData.data);
        setLocations(locationsData.data);
        setLocalVsExternal(trafficData.data);
        setHistorical(historicalData.data);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching analytics:', error);
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) return <div>Cargando datos...</div>;

  return (
    <div className="analytics-dashboard">
      {/* Cards de Métricas Principales */}
      <div className="metrics-grid">
        <MetricCard
          title="Sesiones Totales"
          value={overview.totalSessions.toLocaleString()}
        />
        <MetricCard
          title="Usuarios Nuevos"
          value={overview.newUsers.toLocaleString()}
        />
        <MetricCard
          title="Usuarios Recurrentes"
          value={overview.returningUsers.toLocaleString()}
        />
        <MetricCard
          title="Duración Promedio"
          value={`${Math.round(overview.avgSessionDuration)}s`}
        />
      </div>

      {/* Gráfico de Tendencia Histórica */}
      <div className="chart-container">
        <h2>Tendencia de Sesiones (90 días)</h2>
        <LineChart data={historical} />
      </div>

      {/* Tráfico Local vs Externo */}
      <div className="chart-container">
        <h2>Tráfico por Origen</h2>
        <DonutChart data={localVsExternal} />
      </div>

      {/* Top Cursos */}
      <div className="table-container">
        <h2>Cursos Más Visitados</h2>
        <CoursesTable data={courses} />
      </div>

      {/* Top Noticias */}
      <div className="table-container">
        <h2>Noticias Más Visitadas</h2>
        <NewsTable data={news} />
      </div>

      {/* Mapa de Ubicaciones */}
      <div className="map-container">
        <h2>Tráfico por Ubicación</h2>
        <LocationsMap data={locations} />
      </div>

      {/* Fuentes de Tráfico */}
      <div className="chart-container">
        <h2>Top Fuentes de Tráfico</h2>
        <PieChart data={overview.trafficSources} />
      </div>
    </div>
  );
}

export default AnalyticsDashboard;
```

---

## 🔧 Tips de Implementación

### 1. Caché de Datos
Los datos de GA4 no cambian cada segundo. Implementa caché en el frontend:

```jsx
// Con React Query
const { data: overview } = useQuery(
  ['analytics-overview', daysAgo],
  () => fetch(`/api/analytics/dashboard/overview?days_ago=${daysAgo}`).then(r => r.json()),
  {
    staleTime: 10 * 60 * 1000, // 10 minutos
    cacheTime: 30 * 60 * 1000, // 30 minutos
  }
);
```

### 2. Loading States
Las consultas pueden tardar 2-3 segundos. Muestra skeletons:

```jsx
{loading ? (
  <Skeleton height={200} />
) : (
  <Chart data={historical} />
)}
```

### 3. Error Handling
Maneja errores de red y sin datos:

```jsx
try {
  const res = await fetch('/api/analytics/dashboard/overview');
  if (!res.ok) throw new Error('Error al obtener datos');
  const data = await res.json();

  if (data.data.totalSessions === 0) {
    showWarning('No hay datos para este período');
  }
} catch (error) {
  showError('No se pudieron cargar las analíticas');
}
```

### 4. Selector de Período
Permite al usuario cambiar el rango de fechas:

```jsx
const [period, setPeriod] = useState(30);

<select value={period} onChange={(e) => setPeriod(e.target.value)}>
  <option value={7}>Últimos 7 días</option>
  <option value={30}>Últimos 30 días</option>
  <option value={90}>Últimos 90 días</option>
</select>
```

### 5. Formato de Números
```jsx
// Números grandes con comas
const formatNumber = (num) => num.toLocaleString('es-CL');

// Duración en formato legible
const formatDuration = (seconds) => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
};

// Porcentajes
const formatPercent = (num) => `${num.toFixed(1)}%`;
```

---

## 📝 Checklist de Integración

- [ ] Implementar dashboard overview con cards de métricas
- [ ] Crear tabla de cursos más visitados
- [ ] Crear tabla de noticias más visitadas
- [ ] Implementar gráfico de líneas con datos históricos
- [ ] Implementar gráfico de dona para tráfico local/externo
- [ ] Implementar mapa de ubicaciones geográficas
- [ ] Agregar selector de período (7/30/90 días)
- [ ] Implementar loading states y skeletons
- [ ] Manejar errores y casos sin datos
- [ ] Implementar caché de datos (10 min recomendado)
- [ ] Formatear números con separadores de miles
- [ ] Agregar tooltips explicativos a las métricas
- [ ] Hacer responsive para móviles
- [ ] Optimizar rendimiento (lazy loading, code splitting)

---

## 🚀 Próximos Pasos

### Opcional: Almacenamiento de Snapshots
Si necesitas análisis de tendencias a largo plazo (más de 14 meses):

1. Crear endpoint para guardar snapshots mensuales en PostgreSQL
2. Endpoint para consultar snapshots históricos
3. Combinar datos recientes de GA4 con snapshots antiguos

### Opcional: Filtros Personalizados
Agregar más filtros si es necesario:
- Filtrado por rango de fechas personalizado
- Filtrado por categorías específicas
- Comparación entre períodos
- Exportación a CSV/Excel

---

## 📞 Soporte

Para dudas o problemas:
1. Revisar `/docs` o `/docs-scalar` en el servidor
2. Verificar health check: `/api/analytics/health`
3. Consultar logs del servidor para errores específicos

**Documentación completa:** Ver también `API_GOOGLE_ANALYTICS_FRONTEND.md` y `RESUMEN_ANALYTICS_API.md`
