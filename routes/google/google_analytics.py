"""
Endpoints para Google Analytics 4
"""
from fastapi import APIRouter, HTTPException, status, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from sqlmodel import Session

from external_services.google.analytics import analytics_service
from database.database import get_session, get_services
from database.models.user import UserRead
from database.services.auth.dependencies import require_admin_role

router = APIRouter(
    prefix="/api/analytics",
    tags=["Google Analytics 4"]
)


# ========== Helper Functions ==========

def check_service_available():
    """
    Verifica que el servicio de Google Analytics esté disponible

    Raises:
        HTTPException: Si el servicio no está configurado o disponible
    """
    if analytics_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de Google Analytics no está disponible. Verifica la configuración de credenciales."
        )


def _get_analytics_cache():
    """Obtiene el servicio de cache de analytics. Retorna None si no está disponible."""
    try:
        services = get_services()
        return services.analyticsCacheService
    except Exception:
        return None


# ========== Schemas ==========

class AnalyticsDateRangeRequest(BaseModel):
    """Schema para consultas con rango de fechas"""
    start_date: Optional[str] = Field(
        None,
        description="Fecha de inicio en formato YYYY-MM-DD. Si no se provee, usa days_ago",
        example="2024-01-01"
    )
    end_date: Optional[str] = Field(
        None,
        description="Fecha de fin en formato YYYY-MM-DD. Si no se provee, usa hoy",
        example="2024-01-31"
    )
    days_ago: int = Field(
        7,
        ge=1,
        le=365,
        description="Días hacia atrás desde hoy (si no se proveen fechas específicas)",
        example=7
    )


# ========== Endpoints ==========

@router.get("/")
async def get_analytics_overview(
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    days_ago: int = Query(7, ge=1, le=365, description="Días hacia atrás"),
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Obtiene métricas básicas de Google Analytics 4

    Retorna:
    - Sesiones totales
    - Usuarios activos
    - Páginas vistas
    - Tasa de rebote (bounce rate)
    - Duración promedio de sesión
    - Sesiones por usuario

    Por defecto obtiene datos de los últimos 7 días.
    """
    check_service_available()

    try:
        # Validar formato de fechas si se proporcionan
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date debe estar en formato YYYY-MM-DD"
                )

        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date debe estar en formato YYYY-MM-DD"
                )

        # Try cache first
        cache = _get_analytics_cache()
        if cache:
            cache_key = cache.build_cache_key("basic_metrics", days_ago=days_ago, start_date=start_date, end_date=end_date)
            cached = cache.get_data(cache_key)
            if cached is not None:
                return {"status": "success", "data": cached, "source": "cache"}

        metrics = analytics_service.get_basic_metrics(
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago
        )

        # Cache the result
        if cache:
            cache.cache_data(cache_key, metrics, ttl=7200)

        return {
            "status": "success",
            "data": metrics
        }

    except ValueError as e:
        error_msg = str(e)
        if "GOOGLE_APPLICATION_CREDENTIALS" in error_msg or "GA4_PROPERTY_ID" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Servicio de Google Analytics no configurado correctamente: {error_msg}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.get("/traffic-sources")
async def get_traffic_sources(
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    days_ago: int = Query(7, ge=1, le=365, description="Días hacia atrás"),
    limit: int = Query(10, ge=1, le=50, description="Número máximo de resultados"),
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Obtiene las fuentes de tráfico (source/medium) ordenadas por sesiones

    Retorna lista con:
    - Fuente (source)
    - Medio (medium)
    - Sesiones
    - Usuarios

    Por defecto obtiene las top 10 fuentes de los últimos 7 días.
    """
    check_service_available()

    try:
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date debe estar en formato YYYY-MM-DD"
                )

        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date debe estar en formato YYYY-MM-DD"
                )

        # Try cache first
        cache = _get_analytics_cache()
        if cache:
            cache_key = cache.build_cache_key("traffic_sources", days_ago=days_ago, limit=limit, start_date=start_date, end_date=end_date)
            cached = cache.get_data(cache_key)
            if cached is not None:
                return {"status": "success", "data": cached, "count": len(cached), "source": "cache"}

        sources = analytics_service.get_traffic_sources(
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago,
            limit=limit
        )

        if cache:
            cache.cache_data(cache_key, sources, ttl=7200)

        return {
            "status": "success",
            "data": sources,
            "count": len(sources)
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.get("/devices")
async def get_device_breakdown(
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    days_ago: int = Query(7, ge=1, le=365, description="Días hacia atrás"),
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Obtiene el desglose por tipo de dispositivo (desktop, mobile, tablet)

    Retorna lista con:
    - Categoría de dispositivo
    - Sesiones
    - Usuarios
    - Tasa de rebote

    Por defecto obtiene datos de los últimos 7 días.
    """
    check_service_available()

    try:
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date debe estar en formato YYYY-MM-DD"
                )

        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date debe estar en formato YYYY-MM-DD"
                )

        # Try cache first
        cache = _get_analytics_cache()
        if cache:
            cache_key = cache.build_cache_key("devices", days_ago=days_ago, start_date=start_date, end_date=end_date)
            cached = cache.get_data(cache_key)
            if cached is not None:
                return {"status": "success", "data": cached, "count": len(cached), "source": "cache"}

        devices = analytics_service.get_device_breakdown(
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago
        )

        if cache:
            cache.cache_data(cache_key, devices, ttl=7200)

        return {
            "status": "success",
            "data": devices,
            "count": len(devices)
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.get("/complete-report")
async def get_complete_report(
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    days_ago: int = Query(7, ge=1, le=365, description="Días hacia atrás"),
    session: Session = Depends(get_session),
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Obtiene un reporte completo con todas las métricas disponibles

    Incluye:
    - Métricas generales (sesiones, usuarios, páginas vistas, bounce rate)
    - Top fuentes de tráfico
    - Top páginas más visitadas
    - Desglose por dispositivo

    Por defecto obtiene datos de los últimos 7 días.
    """
    check_service_available()

    try:
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date debe estar en formato YYYY-MM-DD"
                )

        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date debe estar en formato YYYY-MM-DD"
                )

        # Try cache first
        cache = _get_analytics_cache()
        if cache:
            cache_key = cache.build_cache_key("complete_report", days_ago=days_ago, start_date=start_date, end_date=end_date)
            cached = cache.get_data(cache_key)
            if cached is not None:
                return {"status": "success", "data": cached, "source": "cache"}

        report = analytics_service.get_complete_report(
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago
        )

        # Enriquecer top_pages con nombres de la base de datos
        from database.services.cache.analytics_cache_service import AnalyticsCacheService
        report["top_pages"] = AnalyticsCacheService.enrich_pages(report.get("top_pages", []), session)

        if cache:
            cache.cache_data(cache_key, report, ttl=7200)

        return {
            "status": "success",
            "data": report
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


# ========== Dashboard Endpoints (Frontend Spec) ==========

@router.get("/dashboard/overview")
async def get_dashboard_overview(
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    days_ago: int = Query(30, ge=1, le=365, description="Días hacia atrás (default: 30)"),
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Dashboard Overview - Métricas generales del sitio

    Retorna:
    - totalSessions: Total de sesiones
    - newUsers: Usuarios nuevos
    - returningUsers: Usuarios recurrentes
    - avgSessionDuration: Duración promedio de sesión (segundos)
    - trafficSources: Top 5 fuentes de tráfico

    Por defecto obtiene datos de los últimos 30 días.
    """
    check_service_available()

    try:
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date debe estar en formato YYYY-MM-DD"
                )

        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date debe estar en formato YYYY-MM-DD"
                )

        # Try cache first
        cache = _get_analytics_cache()
        if cache:
            cache_key = cache.build_cache_key("dashboard_overview", days_ago=days_ago, start_date=start_date, end_date=end_date)
            cached = cache.get_data(cache_key)
            if cached is not None:
                return {"status": "success", "data": cached, "source": "cache"}

        data = analytics_service.get_dashboard_overview(
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago
        )

        if cache:
            cache.cache_data(cache_key, data, ttl=3600)

        return {
            "status": "success",
            "data": data
        }

    except ValueError as e:
        error_msg = str(e)
        if "GOOGLE_APPLICATION_CREDENTIALS" in error_msg or "GA4_PROPERTY_ID" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Servicio de Google Analytics no configurado correctamente: {error_msg}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.get("/dashboard/courses")
async def get_dashboard_courses(
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    days_ago: int = Query(30, ge=1, le=365, description="Días hacia atrás (default: 30)"),
    limit: int = Query(20, ge=1, le=100, description="Número máximo de resultados"),
    session: Session = Depends(get_session),
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Dashboard Cursos - Páginas de cursos más visitadas

    Filtra automáticamente páginas que contienen "/ofertaAcademica/" en su path.

    Retorna lista con:
    - rank: Posición en el ranking
    - pageTitle: Título de la página
    - pagePath: Ruta completa
    - slug: Identificador del curso (extraído del path)
    - careerId: ID de la carrera (extraído del slug)
    - careerName: Nombre de la carrera desde la base de datos
    - pageViews: Número de visualizaciones
    - users: Usuarios únicos
    - avgSessionDuration: Duración promedio de sesión (segundos)
    - avgEngagementTime: Tiempo de engagement promedio (segundos)

    Por defecto obtiene top 20 cursos de los últimos 30 días.
    """
    check_service_available()

    try:
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date debe estar en formato YYYY-MM-DD"
                )

        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date debe estar en formato YYYY-MM-DD"
                )

        # Try cache first
        cache = _get_analytics_cache()
        if cache:
            cache_key = cache.build_cache_key("dashboard_courses", days_ago=days_ago, limit=limit, start_date=start_date, end_date=end_date)
            cached = cache.get_data(cache_key)
            if cached is not None:
                return {"status": "success", "data": cached, "count": len(cached), "source": "cache"}

        courses = analytics_service.get_pages_by_path_filter(
            path_filter="/ofertaAcademica/",
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago,
            limit=limit
        )

        # Enriquecer datos con información de la base de datos
        from database.services.cache.analytics_cache_service import AnalyticsCacheService
        enriched_courses = AnalyticsCacheService.enrich_courses(courses, session)

        if cache:
            cache.cache_data(cache_key, enriched_courses, ttl=7200)

        return {
            "status": "success",
            "data": enriched_courses,
            "count": len(enriched_courses)
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.get("/dashboard/news")
async def get_dashboard_news(
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    days_ago: int = Query(30, ge=1, le=365, description="Días hacia atrás (default: 30)"),
    limit: int = Query(20, ge=1, le=100, description="Número máximo de resultados"),
    session: Session = Depends(get_session),
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Dashboard Noticias - Páginas de noticias más visitadas

    Filtra automáticamente páginas que contienen "/noticiasNovedades/" en su path.

    Retorna lista con:
    - rank: Posición en el ranking
    - pageTitle: Título de la página
    - pagePath: Ruta completa
    - slug: Identificador de la noticia (extraído del path)
    - newsId: ID de la noticia (extraído del slug)
    - newsTitle: Título de la noticia desde la base de datos
    - pageViews: Número de visualizaciones
    - users: Usuarios únicos
    - avgSessionDuration: Duración promedio de sesión (segundos)
    - avgEngagementTime: Tiempo de engagement promedio (segundos)

    Por defecto obtiene top 20 noticias de los últimos 30 días.
    """
    check_service_available()

    try:
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date debe estar en formato YYYY-MM-DD"
                )

        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date debe estar en formato YYYY-MM-DD"
                )

        # Try cache first
        cache = _get_analytics_cache()
        if cache:
            cache_key = cache.build_cache_key("dashboard_news", days_ago=days_ago, limit=limit, start_date=start_date, end_date=end_date)
            cached = cache.get_data(cache_key)
            if cached is not None:
                return {"status": "success", "data": cached, "count": len(cached), "source": "cache"}

        news = analytics_service.get_pages_by_path_filter(
            path_filter="/noticiasNovedades/",
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago,
            limit=limit
        )

        # Enriquecer datos con información de la base de datos
        from database.services.cache.analytics_cache_service import AnalyticsCacheService
        enriched_news = AnalyticsCacheService.enrich_news(news, session)

        if cache:
            cache.cache_data(cache_key, enriched_news, ttl=7200)

        return {
            "status": "success",
            "data": enriched_news,
            "count": len(enriched_news)
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


# ========== Geographic Endpoints ==========

@router.get("/geographic/locations")
async def get_geographic_locations(
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    days_ago: int = Query(30, ge=1, le=365, description="Días hacia atrás (default: 30)"),
    limit: int = Query(20, ge=1, le=100, description="Número máximo de resultados"),
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Tráfico por Ubicación Geográfica (Ciudad y País)

    Retorna lista con:
    - rank: Posición en el ranking
    - city: Ciudad
    - country: País
    - sessions: Sesiones desde esa ubicación
    - users: Usuarios únicos
    - pageViews: Páginas vistas

    Por defecto obtiene top 20 ubicaciones de los últimos 30 días.
    """
    check_service_available()

    try:
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date debe estar en formato YYYY-MM-DD"
                )

        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date debe estar en formato YYYY-MM-DD"
                )

        # Try cache first
        cache = _get_analytics_cache()
        if cache:
            cache_key = cache.build_cache_key("geographic_locations", days_ago=days_ago, limit=limit, start_date=start_date, end_date=end_date)
            cached = cache.get_data(cache_key)
            if cached is not None:
                return {"status": "success", "data": cached, "count": len(cached), "source": "cache"}

        locations = analytics_service.get_geographic_data(
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago,
            limit=limit
        )

        if cache:
            cache.cache_data(cache_key, locations, ttl=7200)

        return {
            "status": "success",
            "data": locations,
            "count": len(locations)
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


@router.get("/geographic/local-vs-external")
async def get_local_vs_external_traffic(
    country: str = Query("Uruguay", description="País a considerar como local"),
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    days_ago: int = Query(30, ge=1, le=365, description="Días hacia atrás (default: 30)"),
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Desglose de Tráfico Local vs Externo

    Compara el tráfico desde un país específico (local) contra el resto del mundo (externo).

    Retorna:
    - local: Métricas del país especificado (sessions, users, percentage)
    - external: Métricas del resto de países (sessions, users, percentage)
    - total: Totales generales

    Por defecto usa Chile como país local y obtiene datos de los últimos 30 días.
    """
    check_service_available()

    try:
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date debe estar en formato YYYY-MM-DD"
                )

        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date debe estar en formato YYYY-MM-DD"
                )

        # Try cache first
        cache = _get_analytics_cache()
        if cache:
            cache_key = cache.build_cache_key("geographic_local_external", days_ago=days_ago, country=country, start_date=start_date, end_date=end_date)
            cached = cache.get_data(cache_key)
            if cached is not None:
                return {"status": "success", "data": cached, "source": "cache"}

        traffic_data = analytics_service.get_traffic_by_location_type(
            country_filter=country,
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago
        )

        if cache:
            cache.cache_data(cache_key, traffic_data, ttl=7200)

        return {
            "status": "success",
            "data": traffic_data
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


# ========== Historical Data Endpoint ==========

@router.get("/historical")
async def get_historical_data(
    metric: str = Query(
        "sessions",
        description="Métrica a consultar (sessions, activeUsers, screenPageViews, etc.)"
    ),
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    days_ago: int = Query(90, ge=1, le=365, description="Días hacia atrás (default: 90)"),
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Datos Históricos por Fecha

    Obtiene valores día por día de una métrica específica.

    Métricas disponibles:
    - sessions: Sesiones
    - activeUsers: Usuarios activos
    - newUsers: Usuarios nuevos
    - totalUsers: Total usuarios
    - screenPageViews: Páginas vistas
    - bounceRate: Tasa de rebote
    - averageSessionDuration: Duración promedio de sesión
    - averageEngagementTime: Tiempo de engagement promedio

    Retorna lista con:
    - date: Fecha (YYYY-MM-DD)
    - value: Valor de la métrica
    - metric: Nombre de la métrica

    Por defecto obtiene "sessions" de los últimos 90 días.
    """
    check_service_available()

    try:
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date debe estar en formato YYYY-MM-DD"
                )

        if end_date:
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date debe estar en formato YYYY-MM-DD"
                )

        # Try cache first
        cache = _get_analytics_cache()
        if cache:
            cache_key = cache.build_cache_key("historical", days_ago=days_ago, metric=metric, start_date=start_date, end_date=end_date)
            cached = cache.get_data(cache_key)
            if cached is not None:
                return {"status": "success", "data": cached, "count": len(cached), "metric": metric, "source": "cache"}

        historical_data = analytics_service.get_historical_data(
            metric_name=metric,
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago
        )

        if cache:
            cache.cache_data(cache_key, historical_data, ttl=14400)

        return {
            "status": "success",
            "data": historical_data,
            "count": len(historical_data),
            "metric": metric
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(e)}"
        )


# ========== Cache Management Endpoints ==========

@router.post("/cache/refresh")
async def refresh_analytics_cache(
    current_user: UserRead = Depends(require_admin_role)
):
    """
    Ejecuta manualmente el pre-fetch de analytics.
    Limpia los datos viejos y los reemplaza con datos frescos de GA4.
    Requiere rol de administrador.
    """
    try:
        import threading
        from utils.jobs.analytics_prefetch import prefetch_analytics_data

        # Ejecutar en thread para no bloquear el response
        thread = threading.Thread(target=prefetch_analytics_data, daemon=True)
        thread.start()

        return {
            "status": "success",
            "message": "Pre-fetch de analytics iniciado en background. Los datos se actualizarán en unos segundos."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error iniciando pre-fetch: {str(e)}"
        )


# ========== Debug and Health Endpoints ==========

@router.get("/debug-env")
async def debug_environment_variables():
    """
    DEBUG: Muestra qué variables de entorno ve el servidor
    """
    import os

    creds_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON', '')
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')

    return {
        "GOOGLE_APPLICATION_CREDENTIALS": creds_path if creds_path else "NO CONFIGURADO",
        "GOOGLE_APPLICATION_CREDENTIALS_JSON_length": len(creds_json) if creds_json else 0,
        "GOOGLE_APPLICATION_CREDENTIALS_JSON_preview": creds_json[:80] + '...' if len(creds_json) > 80 else (creds_json if creds_json else "NO CONFIGURADO"),
        "GA4_PROPERTY_ID": os.getenv('GA4_PROPERTY_ID', 'NO CONFIGURADO'),
        "all_google_vars": [k for k in os.environ.keys() if 'GOOGLE' in k.upper() or 'GA4' in k.upper() or 'ANALYTICS' in k.upper()],
        "total_env_vars": len(os.environ)
    }


@router.get("/debug-modules")
async def debug_modules():
    """
    DEBUG: Verifica qué módulos de Google están instalados
    """
    import sys
    from external_services.google.analytics import _initialization_error

    modules_status = {}

    # Verificar módulos necesarios
    required_modules = [
        'google.analytics.data_v1beta',
        'google.oauth2.service_account',
        'google.auth',
    ]

    for module_name in required_modules:
        try:
            __import__(module_name)
            modules_status[module_name] = "Instalado"
        except ImportError as e:
            modules_status[module_name] = f"NO INSTALADO: {str(e)}"

    # Información del servicio
    service_status = {
        "analytics_service_initialized": analytics_service is not None,
        "initialization_error": _initialization_error if _initialization_error else "No hay error registrado",
    }

    return {
        "python_version": sys.version,
        "modules": modules_status,
        "service": service_status
    }


@router.get("/health")
async def analytics_health_check():
    """
    Verifica que el servicio de Google Analytics esté configurado correctamente

    Retorna el estado de las credenciales y la configuración.
    """
    try:
        import os

        credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        property_id = os.getenv('GA4_PROPERTY_ID')

        issues = []

        # Verificar que al menos una forma de credenciales esté configurada
        if not credentials_json and not credentials_path:
            issues.append("Ni GOOGLE_APPLICATION_CREDENTIALS_JSON ni GOOGLE_APPLICATION_CREDENTIALS están configurados")
        elif credentials_path and not credentials_json:
            # Solo verificar archivo si no hay JSON
            if not os.path.exists(credentials_path):
                issues.append(f"Archivo de credenciales no encontrado: {credentials_path}")

        if not property_id:
            issues.append("GA4_PROPERTY_ID no está configurado")

        if issues:
            return {
                "status": "error",
                "configured": False,
                "issues": issues
            }

        # Verificar que el servicio se haya inicializado
        if analytics_service is None:
            from external_services.google.analytics import _initialization_error
            error_detail = f"Error de inicialización: {_initialization_error}" if _initialization_error else "Causa desconocida"
            return {
                "status": "error",
                "configured": False,
                "issues": [
                    "El servicio de Google Analytics no pudo inicializarse.",
                    error_detail,
                    "Verifica que GOOGLE_APPLICATION_CREDENTIALS_JSON y GA4_PROPERTY_ID estén correctamente configurados."
                ]
            }

        # Intentar hacer una consulta simple para verificar que todo funciona
        try:
            analytics_service.get_basic_metrics(days_ago=1)
            return {
                "status": "success",
                "configured": True,
                "property_id": property_id,
                "message": "Google Analytics 4 configurado correctamente"
            }
        except Exception as e:
            return {
                "status": "error",
                "configured": False,
                "issues": [f"Error al conectar con GA4: {str(e)}"]
            }

    except Exception as e:
        return {
            "status": "error",
            "configured": False,
            "issues": [f"Error en health check: {str(e)}"]
        }
