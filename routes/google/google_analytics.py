"""
Endpoints para Google Analytics 4
"""
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from external_services.google.analytics import analytics_service

router = APIRouter(
    prefix="/api/analytics",
    tags=["Google Analytics 4"]
)


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
    days_ago: int = Query(7, ge=1, le=365, description="Días hacia atrás")
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

        metrics = analytics_service.get_basic_metrics(
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago
        )

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
    limit: int = Query(10, ge=1, le=50, description="Número máximo de resultados")
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

        sources = analytics_service.get_traffic_sources(
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago,
            limit=limit
        )

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


@router.get("/top-pages")
async def get_top_pages(
    start_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    days_ago: int = Query(7, ge=1, le=365, description="Días hacia atrás"),
    limit: int = Query(10, ge=1, le=50, description="Número máximo de resultados")
):
    """
    Obtiene las páginas más visitadas ordenadas por páginas vistas

    Retorna lista con:
    - Título de página
    - Ruta de página
    - Páginas vistas
    - Usuarios
    - Duración promedio de sesión

    Por defecto obtiene las top 10 páginas de los últimos 7 días.
    """
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

        pages = analytics_service.get_top_pages(
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago,
            limit=limit
        )

        return {
            "status": "success",
            "data": pages,
            "count": len(pages)
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
    days_ago: int = Query(7, ge=1, le=365, description="Días hacia atrás")
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

        devices = analytics_service.get_device_breakdown(
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago
        )

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
    days_ago: int = Query(7, ge=1, le=365, description="Días hacia atrás")
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

        report = analytics_service.get_complete_report(
            start_date=start_date,
            end_date=end_date,
            days_ago=days_ago
        )

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


@router.get("/health")
async def analytics_health_check():
    """
    Verifica que el servicio de Google Analytics esté configurado correctamente

    Retorna el estado de las credenciales y la configuración.
    """
    try:
        import os

        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        property_id = os.getenv('GA4_PROPERTY_ID')

        issues = []

        if not credentials_path:
            issues.append("GOOGLE_APPLICATION_CREDENTIALS no está configurado")
        elif not os.path.exists(credentials_path):
            issues.append(f"Archivo de credenciales no encontrado: {credentials_path}")

        if not property_id:
            issues.append("GA4_PROPERTY_ID no está configurado")

        if issues:
            return {
                "status": "error",
                "configured": False,
                "issues": issues
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
