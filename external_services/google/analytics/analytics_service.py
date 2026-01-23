"""
Servicio para interactuar con Google Analytics 4 API
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account


class GoogleAnalyticsService:
    """
    Servicio para obtener datos de Google Analytics 4 mediante la API oficial
    """

    def __init__(self):
        """
        Inicializa el servicio de Google Analytics 4

        Variables de entorno requeridas:
        - GOOGLE_APPLICATION_CREDENTIALS: Ruta al archivo JSON o JSON como string
        - GOOGLE_APPLICATION_CREDENTIALS_JSON: JSON de credenciales como string (alternativa)
        - GA4_PROPERTY_ID: ID de la propiedad de GA4 (formato: properties/123456789)

        Soporta dos modos:
        1. Ruta a archivo (desarrollo): GOOGLE_APPLICATION_CREDENTIALS=./credentials/file.json
        2. JSON como string (producción): GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type": "service_account", ...}'
        """
        self.property_id = os.getenv('GA4_PROPERTY_ID')

        if not self.property_id:
            raise ValueError(
                "GA4_PROPERTY_ID no está configurado. "
                "Debe contener el ID de tu propiedad de GA4 (formato: properties/123456789)"
            )

        # Inicializar cliente con credenciales
        try:
            credentials = self._get_credentials()
            self.client = BetaAnalyticsDataClient(credentials=credentials)
        except Exception as e:
            raise ValueError(f"Error al inicializar el cliente de GA4: {str(e)}")

    def _get_credentials(self):
        """
        Obtiene las credenciales desde archivo o string JSON

        Returns:
            Credenciales de Google configuradas

        Raises:
            ValueError: Si no se encuentra configuración válida
        """
        # Opción 1: JSON como string (ideal para producción)
        credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
        if credentials_json:
            try:
                credentials_info = json.loads(credentials_json)
                return service_account.Credentials.from_service_account_info(
                    credentials_info,
                    scopes=['https://www.googleapis.com/auth/analytics.readonly']
                )
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Error al parsear GOOGLE_APPLICATION_CREDENTIALS_JSON: {str(e)}. "
                    "Verifica que sea un JSON válido."
                )
            except Exception as e:
                raise ValueError(
                    f"Error al crear credenciales desde JSON string: {str(e)}"
                )

        # Opción 2: Ruta a archivo (ideal para desarrollo)
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if credentials_path:
            # Verificar que el archivo existe
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"No se encontró el archivo de credenciales en: {credentials_path}"
                )

            try:
                return service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=['https://www.googleapis.com/auth/analytics.readonly']
                )
            except Exception as e:
                raise ValueError(
                    f"Error al cargar credenciales desde archivo: {str(e)}"
                )

        # Si no hay ninguna configuración
        raise ValueError(
            "No se encontraron credenciales de Google. "
            "Debes configurar una de estas variables:\n"
            "- GOOGLE_APPLICATION_CREDENTIALS_JSON: JSON completo como string (recomendado para producción)\n"
            "- GOOGLE_APPLICATION_CREDENTIALS: Ruta al archivo JSON (recomendado para desarrollo)"
        )

    def _format_date(self, date: datetime) -> str:
        """
        Formatea una fecha al formato requerido por GA4 (YYYY-MM-DD)

        Args:
            date: Objeto datetime

        Returns:
            String con fecha formateada
        """
        return date.strftime('%Y-%m-%d')

    def _get_date_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ago: int = 7
    ) -> DateRange:
        """
        Crea un rango de fechas para las consultas a GA4

        Args:
            start_date: Fecha de inicio (formato YYYY-MM-DD). Si es None, usa days_ago
            end_date: Fecha de fin (formato YYYY-MM-DD). Si es None, usa hoy
            days_ago: Días hacia atrás desde hoy (default: 7)

        Returns:
            DateRange de GA4
        """
        if not end_date:
            end_date = self._format_date(datetime.now())

        if not start_date:
            start_datetime = datetime.now() - timedelta(days=days_ago)
            start_date = self._format_date(start_datetime)

        return DateRange(start_date=start_date, end_date=end_date)

    def get_basic_metrics(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ago: int = 7
    ) -> Dict[str, Any]:
        """
        Obtiene métricas básicas de GA4: sesiones, usuarios, páginas vistas y bounce rate

        Args:
            start_date: Fecha de inicio (formato YYYY-MM-DD)
            end_date: Fecha de fin (formato YYYY-MM-DD)
            days_ago: Días hacia atrás desde hoy (default: 7)

        Returns:
            Dict con las métricas básicas
        """
        try:
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[self._get_date_range(start_date, end_date, days_ago)],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="activeUsers"),
                    Metric(name="screenPageViews"),
                    Metric(name="bounceRate"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="sessionsPerUser"),
                ],
            )

            response = self.client.run_report(request)

            if not response.rows:
                return {
                    "sessions": 0,
                    "active_users": 0,
                    "page_views": 0,
                    "bounce_rate": 0,
                    "avg_session_duration": 0,
                    "sessions_per_user": 0,
                    "date_range": {
                        "start_date": self._get_date_range(start_date, end_date, days_ago).start_date,
                        "end_date": self._get_date_range(start_date, end_date, days_ago).end_date
                    }
                }

            # Extraer valores de la primera fila
            row = response.rows[0]
            metrics = row.metric_values

            return {
                "sessions": int(metrics[0].value),
                "active_users": int(metrics[1].value),
                "page_views": int(metrics[2].value),
                "bounce_rate": round(float(metrics[3].value), 2),
                "avg_session_duration": round(float(metrics[4].value), 2),
                "sessions_per_user": round(float(metrics[5].value), 2),
                "date_range": {
                    "start_date": self._get_date_range(start_date, end_date, days_ago).start_date,
                    "end_date": self._get_date_range(start_date, end_date, days_ago).end_date
                }
            }

        except Exception as e:
            raise ValueError(f"Error obteniendo métricas básicas de GA4: {str(e)}")

    def get_traffic_sources(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ago: int = 7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Obtiene las fuentes de tráfico (source/medium)

        Args:
            start_date: Fecha de inicio (formato YYYY-MM-DD)
            end_date: Fecha de fin (formato YYYY-MM-DD)
            days_ago: Días hacia atrás desde hoy (default: 7)
            limit: Número máximo de resultados (default: 10)

        Returns:
            Lista con las fuentes de tráfico ordenadas por sesiones
        """
        try:
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[self._get_date_range(start_date, end_date, days_ago)],
                dimensions=[
                    Dimension(name="sessionSource"),
                    Dimension(name="sessionMedium"),
                ],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="activeUsers"),
                ],
                limit=limit,
                order_bys=[{
                    "metric": {"metric_name": "sessions"},
                    "desc": True
                }]
            )

            response = self.client.run_report(request)

            sources = []
            for row in response.rows:
                sources.append({
                    "source": row.dimension_values[0].value,
                    "medium": row.dimension_values[1].value,
                    "sessions": int(row.metric_values[0].value),
                    "users": int(row.metric_values[1].value),
                })

            return sources

        except Exception as e:
            raise ValueError(f"Error obteniendo fuentes de tráfico de GA4: {str(e)}")

    def get_top_pages(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ago: int = 7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Obtiene las páginas más visitadas

        Args:
            start_date: Fecha de inicio (formato YYYY-MM-DD)
            end_date: Fecha de fin (formato YYYY-MM-DD)
            days_ago: Días hacia atrás desde hoy (default: 7)
            limit: Número máximo de resultados (default: 10)

        Returns:
            Lista con las páginas más visitadas
        """
        try:
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[self._get_date_range(start_date, end_date, days_ago)],
                dimensions=[
                    Dimension(name="pageTitle"),
                    Dimension(name="pagePath"),
                ],
                metrics=[
                    Metric(name="screenPageViews"),
                    Metric(name="activeUsers"),
                    Metric(name="averageSessionDuration"),
                ],
                limit=limit,
                order_bys=[{
                    "metric": {"metric_name": "screenPageViews"},
                    "desc": True
                }]
            )

            response = self.client.run_report(request)

            pages = []
            for row in response.rows:
                pages.append({
                    "page_title": row.dimension_values[0].value,
                    "page_path": row.dimension_values[1].value,
                    "page_views": int(row.metric_values[0].value),
                    "users": int(row.metric_values[1].value),
                    "avg_session_duration": round(float(row.metric_values[2].value), 2),
                })

            return pages

        except Exception as e:
            raise ValueError(f"Error obteniendo páginas más visitadas de GA4: {str(e)}")

    def get_device_breakdown(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ago: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Obtiene el desglose por tipo de dispositivo (desktop, mobile, tablet)

        Args:
            start_date: Fecha de inicio (formato YYYY-MM-DD)
            end_date: Fecha de fin (formato YYYY-MM-DD)
            days_ago: Días hacia atrás desde hoy (default: 7)

        Returns:
            Lista con el desglose por dispositivo
        """
        try:
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[self._get_date_range(start_date, end_date, days_ago)],
                dimensions=[
                    Dimension(name="deviceCategory"),
                ],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="activeUsers"),
                    Metric(name="bounceRate"),
                ],
                order_bys=[{
                    "metric": {"metric_name": "sessions"},
                    "desc": True
                }]
            )

            response = self.client.run_report(request)

            devices = []
            for row in response.rows:
                devices.append({
                    "device_category": row.dimension_values[0].value,
                    "sessions": int(row.metric_values[0].value),
                    "users": int(row.metric_values[1].value),
                    "bounce_rate": round(float(row.metric_values[2].value), 2),
                })

            return devices

        except Exception as e:
            raise ValueError(f"Error obteniendo desglose por dispositivo de GA4: {str(e)}")

    def get_complete_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ago: int = 7
    ) -> Dict[str, Any]:
        """
        Obtiene un reporte completo con todas las métricas disponibles

        Args:
            start_date: Fecha de inicio (formato YYYY-MM-DD)
            end_date: Fecha de fin (formato YYYY-MM-DD)
            days_ago: Días hacia atrás desde hoy (default: 7)

        Returns:
            Dict con todas las métricas organizadas
        """
        try:
            return {
                "overview": self.get_basic_metrics(start_date, end_date, days_ago),
                "traffic_sources": self.get_traffic_sources(start_date, end_date, days_ago),
                "top_pages": self.get_top_pages(start_date, end_date, days_ago),
                "devices": self.get_device_breakdown(start_date, end_date, days_ago),
            }
        except Exception as e:
            raise ValueError(f"Error generando reporte completo de GA4: {str(e)}")

    def get_dashboard_overview(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ago: int = 30
    ) -> Dict[str, Any]:
        """
        Obtiene métricas para el dashboard overview (según especificación frontend)

        Args:
            start_date: Fecha de inicio (formato YYYY-MM-DD)
            end_date: Fecha de fin (formato YYYY-MM-DD)
            days_ago: Días hacia atrás desde hoy (default: 30)

        Returns:
            Dict con totalSessions, newUsers, returningUsers, avgSessionDuration, trafficSources
        """
        try:
            # Obtener métricas principales
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[self._get_date_range(start_date, end_date, days_ago)],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="newUsers"),
                    Metric(name="totalUsers"),
                    Metric(name="averageSessionDuration"),
                ],
            )

            response = self.client.run_report(request)

            if not response.rows:
                total_sessions = 0
                new_users = 0
                total_users = 0
                avg_session_duration = 0
            else:
                row = response.rows[0]
                total_sessions = int(row.metric_values[0].value)
                new_users = int(row.metric_values[1].value)
                total_users = int(row.metric_values[2].value)
                avg_session_duration = round(float(row.metric_values[3].value), 2)

            # Calcular returning users
            returning_users = max(0, total_users - new_users)

            # Obtener top fuentes de tráfico (top 5)
            traffic_sources = self.get_traffic_sources(start_date, end_date, days_ago, limit=5)

            return {
                "totalSessions": total_sessions,
                "newUsers": new_users,
                "returningUsers": returning_users,
                "avgSessionDuration": avg_session_duration,
                "trafficSources": [
                    {
                        "source": src["source"],
                        "medium": src["medium"],
                        "sessions": src["sessions"]
                    }
                    for src in traffic_sources
                ]
            }

        except Exception as e:
            raise ValueError(f"Error obteniendo dashboard overview: {str(e)}")

    def get_pages_by_path_filter(
        self,
        path_filter: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ago: int = 30,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Obtiene páginas filtradas por un patrón en el path

        Args:
            path_filter: Patrón para filtrar (ej: "/cursos/", "/noticias/")
            start_date: Fecha de inicio (formato YYYY-MM-DD)
            end_date: Fecha de fin (formato YYYY-MM-DD)
            days_ago: Días hacia atrás desde hoy (default: 30)
            limit: Número máximo de resultados (default: 20)

        Returns:
            Lista de páginas con métricas, filtradas y rankeadas
        """
        try:
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[self._get_date_range(start_date, end_date, days_ago)],
                dimensions=[
                    Dimension(name="pageTitle"),
                    Dimension(name="pagePath"),
                ],
                metrics=[
                    Metric(name="screenPageViews"),
                    Metric(name="activeUsers"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="averageEngagementTime"),
                ],
                # Aumentar límite para filtrar después
                limit=1000,
                order_bys=[{
                    "metric": {"metric_name": "screenPageViews"},
                    "desc": True
                }]
            )

            response = self.client.run_report(request)

            # Filtrar páginas que contengan el patrón en el path
            filtered_pages = []
            for row in response.rows:
                page_path = row.dimension_values[1].value

                # Filtrar por el patrón especificado
                if path_filter.lower() in page_path.lower():
                    # Extraer slug (último segmento del path, sin parámetros)
                    slug = page_path.rstrip('/').split('/')[-1].split('?')[0]

                    filtered_pages.append({
                        "pageTitle": row.dimension_values[0].value,
                        "pagePath": page_path,
                        "slug": slug,
                        "pageViews": int(row.metric_values[0].value),
                        "users": int(row.metric_values[1].value),
                        "avgSessionDuration": round(float(row.metric_values[2].value), 2),
                        "avgEngagementTime": round(float(row.metric_values[3].value), 2),
                    })

            # Limitar a top N y agregar ranking
            top_pages = filtered_pages[:limit]
            for idx, page in enumerate(top_pages, start=1):
                page["rank"] = idx

            return top_pages

        except Exception as e:
            raise ValueError(f"Error obteniendo páginas filtradas por path: {str(e)}")

    def get_geographic_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ago: int = 30,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Obtiene datos geográficos de tráfico (ciudad y país)

        Args:
            start_date: Fecha de inicio (formato YYYY-MM-DD)
            end_date: Fecha de fin (formato YYYY-MM-DD)
            days_ago: Días hacia atrás desde hoy (default: 30)
            limit: Número máximo de resultados (default: 20)

        Returns:
            Lista de ubicaciones con métricas de tráfico
        """
        try:
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[self._get_date_range(start_date, end_date, days_ago)],
                dimensions=[
                    Dimension(name="city"),
                    Dimension(name="country"),
                ],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="activeUsers"),
                    Metric(name="screenPageViews"),
                ],
                limit=limit,
                order_bys=[{
                    "metric": {"metric_name": "sessions"},
                    "desc": True
                }]
            )

            response = self.client.run_report(request)

            locations = []
            for idx, row in enumerate(response.rows, start=1):
                locations.append({
                    "rank": idx,
                    "city": row.dimension_values[0].value,
                    "country": row.dimension_values[1].value,
                    "sessions": int(row.metric_values[0].value),
                    "users": int(row.metric_values[1].value),
                    "pageViews": int(row.metric_values[2].value),
                })

            return locations

        except Exception as e:
            raise ValueError(f"Error obteniendo datos geográficos: {str(e)}")

    def get_traffic_by_location_type(
        self,
        country_filter: str = "Chile",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ago: int = 30
    ) -> Dict[str, Any]:
        """
        Obtiene desglose de tráfico local vs externo

        Args:
            country_filter: País a considerar como local (default: "Chile")
            start_date: Fecha de inicio (formato YYYY-MM-DD)
            end_date: Fecha de fin (formato YYYY-MM-DD)
            days_ago: Días hacia atrás desde hoy (default: 30)

        Returns:
            Dict con tráfico local, externo y total
        """
        try:
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[self._get_date_range(start_date, end_date, days_ago)],
                dimensions=[
                    Dimension(name="country"),
                ],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="activeUsers"),
                ],
                limit=100
            )

            response = self.client.run_report(request)

            local_sessions = 0
            local_users = 0
            external_sessions = 0
            external_users = 0

            for row in response.rows:
                country = row.dimension_values[0].value
                sessions = int(row.metric_values[0].value)
                users = int(row.metric_values[1].value)

                if country == country_filter:
                    local_sessions += sessions
                    local_users += users
                else:
                    external_sessions += sessions
                    external_users += users

            total_sessions = local_sessions + external_sessions
            total_users = local_users + external_users

            return {
                "local": {
                    "country": country_filter,
                    "sessions": local_sessions,
                    "users": local_users,
                    "percentage": round((local_sessions / total_sessions * 100) if total_sessions > 0 else 0, 2)
                },
                "external": {
                    "sessions": external_sessions,
                    "users": external_users,
                    "percentage": round((external_sessions / total_sessions * 100) if total_sessions > 0 else 0, 2)
                },
                "total": {
                    "sessions": total_sessions,
                    "users": total_users
                }
            }

        except Exception as e:
            raise ValueError(f"Error obteniendo tráfico por tipo de ubicación: {str(e)}")

    def get_historical_data(
        self,
        metric_name: str = "sessions",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days_ago: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Obtiene datos históricos día por día para una métrica específica

        Args:
            metric_name: Nombre de la métrica GA4 (default: "sessions")
            start_date: Fecha de inicio (formato YYYY-MM-DD)
            end_date: Fecha de fin (formato YYYY-MM-DD)
            days_ago: Días hacia atrás desde hoy (default: 90)

        Returns:
            Lista de datos por fecha con la métrica especificada
        """
        try:
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[self._get_date_range(start_date, end_date, days_ago)],
                dimensions=[
                    Dimension(name="date"),
                ],
                metrics=[
                    Metric(name=metric_name),
                ],
                order_bys=[{
                    "dimension": {"dimension_name": "date"},
                    "desc": False
                }]
            )

            response = self.client.run_report(request)

            historical_data = []
            for row in response.rows:
                date_str = row.dimension_values[0].value
                # Formatear fecha de YYYYMMDD a YYYY-MM-DD
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

                value = row.metric_values[0].value
                # Intentar convertir a int, si falla usar float
                try:
                    numeric_value = int(value)
                except ValueError:
                    numeric_value = round(float(value), 2)

                historical_data.append({
                    "date": formatted_date,
                    "value": numeric_value,
                    "metric": metric_name
                })

            return historical_data

        except Exception as e:
            raise ValueError(f"Error obteniendo datos históricos: {str(e)}")


# Instancia singleton del servicio (lazy initialization)
_analytics_service_instance = None


def get_analytics_service():
    """
    Obtiene la instancia del servicio de Google Analytics (patrón singleton lazy)

    Returns:
        GoogleAnalyticsService: Instancia del servicio

    Raises:
        ValueError: Si el servicio no está configurado correctamente
    """
    global _analytics_service_instance

    if _analytics_service_instance is None:
        try:
            _analytics_service_instance = GoogleAnalyticsService()
        except Exception as e:
            raise ValueError(f"No se pudo inicializar el servicio de Google Analytics: {str(e)}")

    return _analytics_service_instance


# Mantener compatibilidad con código existente
analytics_service = None

try:
    analytics_service = GoogleAnalyticsService()
except Exception:
    # Si falla la inicialización, analytics_service será None
    # Los endpoints manejarán el error apropiadamente
    pass
