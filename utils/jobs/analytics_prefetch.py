"""
Job de pre-fetch para Google Analytics.
Obtiene datos de GA4 y los almacena en Redis para evitar agotar la cuota.
"""
import traceback
from utils.logger import show


# Presets: (endpoint_name, fetch_kwargs, ttl, needs_enrichment)
PRESETS = [
    # Dashboard (más usados)
    ("dashboard_overview", {"days_ago": 30}, 3600, None),
    ("dashboard_courses", {"days_ago": 30, "limit": 20}, 7200, "courses"),
    ("dashboard_news", {"days_ago": 30, "limit": 20}, 7200, "news"),

    # Endpoints básicos (7 días)
    ("basic_metrics", {"days_ago": 7}, 7200, None),
    ("traffic_sources", {"days_ago": 7, "limit": 10}, 7200, None),
    ("devices", {"days_ago": 7}, 7200, None),
    ("complete_report", {"days_ago": 7}, 7200, "pages"),

    # Geográfico
    ("geographic_locations", {"days_ago": 30, "limit": 20}, 7200, None),
    ("geographic_local_external", {"days_ago": 30, "country": "Uruguay"}, 7200, None),

    # Histórico
    ("historical", {"days_ago": 90, "metric": "sessions"}, 14400, None),
]

# Mapeo endpoint → método del servicio GA4
FETCH_METHODS = {
    "basic_metrics": lambda svc, kw: svc.get_basic_metrics(days_ago=kw["days_ago"]),
    "traffic_sources": lambda svc, kw: svc.get_traffic_sources(days_ago=kw["days_ago"], limit=kw.get("limit", 10)),
    "devices": lambda svc, kw: svc.get_device_breakdown(days_ago=kw["days_ago"]),
    "complete_report": lambda svc, kw: svc.get_complete_report(days_ago=kw["days_ago"]),
    "dashboard_overview": lambda svc, kw: svc.get_dashboard_overview(days_ago=kw["days_ago"]),
    "dashboard_courses": lambda svc, kw: svc.get_pages_by_path_filter(
        path_filter="/ofertaAcademica/", days_ago=kw["days_ago"], limit=kw.get("limit", 20)
    ),
    "dashboard_news": lambda svc, kw: svc.get_pages_by_path_filter(
        path_filter="/noticiasNovedades/", days_ago=kw["days_ago"], limit=kw.get("limit", 20)
    ),
    "geographic_locations": lambda svc, kw: svc.get_geographic_data(days_ago=kw["days_ago"], limit=kw.get("limit", 20)),
    "geographic_local_external": lambda svc, kw: svc.get_traffic_by_location_type(
        country_filter=kw.get("country", "Uruguay"), days_ago=kw["days_ago"]
    ),
    "historical": lambda svc, kw: svc.get_historical_data(
        metric_name=kw.get("metric", "sessions"), days_ago=kw["days_ago"]
    ),
}


def prefetch_analytics_data():
    """
    Pre-fetch all analytics presets from GA4 and store in Redis.
    Called by the scheduler every 2 hours.
    """
    show("ANALYTICS_CACHE", "Iniciando pre-fetch de datos de Google Analytics", "info")

    try:
        from external_services.google.analytics.analytics_service import analytics_service
        if analytics_service is None:
            show("ANALYTICS_CACHE", "Servicio GA4 no disponible, saltando pre-fetch", "warning")
            return

        from database.database import get_services, engine
        from sqlmodel import Session

        services = get_services()
        cache = services.analyticsCacheService

        success_count = 0
        error_count = 0

        for endpoint, kwargs, ttl, enrichment in PRESETS:
            try:
                # Fetch from GA4
                fetch_fn = FETCH_METHODS.get(endpoint)
                if not fetch_fn:
                    continue

                data = fetch_fn(analytics_service, kwargs)

                # Enrich with DB data if needed
                if enrichment and data:
                    with Session(engine) as session:
                        if enrichment == "courses":
                            data = cache.enrich_courses(data, session)
                        elif enrichment == "news":
                            data = cache.enrich_news(data, session)
                        elif enrichment == "pages":
                            # complete_report: enrich top_pages inside the dict
                            if isinstance(data, dict) and "top_pages" in data:
                                data["top_pages"] = cache.enrich_pages(data["top_pages"], session)

                # Build cache key and store
                cache_key = cache.build_cache_key(endpoint, **kwargs)
                cache.cache_data(cache_key, data, ttl)
                success_count += 1

            except Exception as e:
                error_count += 1
                show("ANALYTICS_CACHE", f"Error pre-fetching {endpoint}: {e}", "error")

        show("ANALYTICS_CACHE",
             f"Pre-fetch completado: {success_count} exitosos, {error_count} errores",
             "success" if error_count == 0 else "warning")

    except Exception as e:
        show("ANALYTICS_CACHE", f"Error general en pre-fetch: {e}", "error")
        traceback.print_exc()
