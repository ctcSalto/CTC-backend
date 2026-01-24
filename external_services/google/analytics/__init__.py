"""
Google Analytics 4 service module
"""
from .analytics_service import (
    GoogleAnalyticsService,
    analytics_service,
    _initialization_error
)

# Lazy initialization - solo se crea cuando se usa
_analytics_service_instance = None

def get_analytics_service():
    """Obtiene la instancia del servicio (lazy initialization)"""
    global _analytics_service_instance
    if _analytics_service_instance is None:
        _analytics_service_instance = GoogleAnalyticsService()
    return _analytics_service_instance

__all__ = [
    'GoogleAnalyticsService',
    'get_analytics_service',
    'analytics_service',
    '_initialization_error'
]
