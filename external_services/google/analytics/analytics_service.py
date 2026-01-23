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


# Instancia singleton del servicio
analytics_service = GoogleAnalyticsService()
