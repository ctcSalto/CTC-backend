"""
Script de prueba para todos los endpoints de Google Analytics 4
Incluye endpoints originales y nuevos endpoints de dashboard
"""
import requests
import json
from datetime import datetime

# Configuración
BASE_URL = "https://backend-backend-ctc-develop.vtu0xl.easypanel.host"
# Para pruebas locales, descomentar:
# BASE_URL = "http://localhost:8000"

# Colores para terminal
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_step(step_num, total_steps, description):
    """Imprime el paso actual con formato"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}[{step_num}/{total_steps}] {description}{Colors.RESET}")
    print("-" * 80)


def print_success(message):
    """Imprime mensaje de éxito"""
    print(f"{Colors.GREEN}[OK] {message}{Colors.RESET}")


def print_error(message):
    """Imprime mensaje de error"""
    print(f"{Colors.RED}[ERROR] {message}{Colors.RESET}")


def print_warning(message):
    """Imprime mensaje de advertencia"""
    print(f"{Colors.YELLOW}[WARN] {message}{Colors.RESET}")


def print_info(message):
    """Imprime mensaje informativo"""
    print(f"{Colors.BLUE}[INFO] {message}{Colors.RESET}")


def test_endpoint(name, url, expected_keys=None):
    """
    Prueba un endpoint y valida su respuesta

    Args:
        name: Nombre descriptivo del test
        url: URL completa del endpoint
        expected_keys: Lista de claves esperadas en data
    """
    try:
        response = requests.get(url, timeout=10)

        # Verificar status code
        if response.status_code == 200:
            print_success(f"Status: {response.status_code}")

            # Parsear JSON
            try:
                data = response.json()

                # Verificar estructura básica
                if "status" in data and data["status"] == "success":
                    print_success("Estructura de respuesta válida")

                    # Mostrar información de la data
                    if "data" in data:
                        data_content = data["data"]

                        # Verificar claves esperadas
                        if expected_keys:
                            missing_keys = [key for key in expected_keys if key not in str(data_content)]
                            if not missing_keys:
                                print_success(f"Contiene todas las claves esperadas: {expected_keys}")
                            else:
                                print_warning(f"Faltan algunas claves esperadas: {missing_keys}")

                        # Mostrar preview de los datos
                        if isinstance(data_content, dict):
                            print_info(f"Datos recibidos (dict con {len(data_content)} claves):")
                            # Mostrar primeras claves
                            for i, (key, value) in enumerate(list(data_content.items())[:5]):
                                if isinstance(value, (list, dict)):
                                    print(f"  - {key}: {type(value).__name__} (len={len(value)})")
                                else:
                                    print(f"  - {key}: {value}")
                        elif isinstance(data_content, list):
                            print_info(f"Datos recibidos (lista con {len(data_content)} elementos):")
                            # Mostrar primeros elementos
                            for i, item in enumerate(data_content[:3]):
                                print(f"  [{i}]: {item}")
                            if len(data_content) > 3:
                                print(f"  ... y {len(data_content) - 3} más")
                        else:
                            print_info(f"Datos recibidos: {data_content}")

                        # Verificar si hay datos
                        if isinstance(data_content, list) and len(data_content) == 0:
                            print_warning("La respuesta está vacía (sin datos para este período)")
                        elif isinstance(data_content, dict):
                            # Verificar si todos los valores numéricos son 0
                            numeric_values = [v for v in data_content.values() if isinstance(v, (int, float))]
                            if numeric_values and all(v == 0 for v in numeric_values):
                                print_warning("Todas las métricas numéricas son 0 (sin datos para este período)")

                    return True
                else:
                    print_error("Respuesta sin 'status: success'")
                    print(f"Respuesta completa: {json.dumps(data, indent=2)}")
                    return False

            except json.JSONDecodeError as e:
                print_error(f"Error al parsear JSON: {str(e)}")
                print(f"Respuesta raw: {response.text[:500]}")
                return False
        else:
            print_error(f"Status code inesperado: {response.status_code}")
            print(f"Respuesta: {response.text[:500]}")
            return False

    except requests.exceptions.Timeout:
        print_error(f"Timeout al conectar con {url}")
        return False
    except requests.exceptions.ConnectionError:
        print_error(f"Error de conexión con {url}")
        return False
    except Exception as e:
        print_error(f"Error inesperado: {str(e)}")
        return False


def main():
    """Ejecuta todos los tests de analytics"""
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}Google Analytics 4 - Test Suite Completo{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}Base URL:{Colors.RESET} {BASE_URL}")
    print(f"{Colors.BOLD}Fecha:{Colors.RESET} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Contadores
    total_tests = 13
    passed_tests = 0

    # ========== Test 1: Health Check ==========
    print_step(1, total_tests, "Health Check")
    if test_endpoint(
        "Health Check",
        f"{BASE_URL}/api/analytics/health"
    ):
        passed_tests += 1

    # ========== Test 2: Métricas Básicas (30 días) ==========
    print_step(2, total_tests, "Métricas Básicas (últimos 30 días)")
    if test_endpoint(
        "Métricas Básicas",
        f"{BASE_URL}/api/analytics?days_ago=30",
        expected_keys=["sessions", "active_users", "page_views", "bounce_rate"]
    ):
        passed_tests += 1

    # ========== Test 3: Fuentes de Tráfico ==========
    print_step(3, total_tests, "Fuentes de Tráfico (top 10, últimos 30 días)")
    if test_endpoint(
        "Fuentes de Tráfico",
        f"{BASE_URL}/api/analytics/traffic-sources?days_ago=30&limit=10",
        expected_keys=["source", "medium", "sessions"]
    ):
        passed_tests += 1

    # ========== Test 4: Top Páginas ==========
    print_step(4, total_tests, "Páginas Más Visitadas (top 10, últimos 30 días)")
    if test_endpoint(
        "Top Páginas",
        f"{BASE_URL}/api/analytics/top-pages?days_ago=30&limit=10",
        expected_keys=["page_title", "page_path", "page_views"]
    ):
        passed_tests += 1

    # ========== Test 5: Dispositivos ==========
    print_step(5, total_tests, "Desglose por Dispositivo (últimos 30 días)")
    if test_endpoint(
        "Dispositivos",
        f"{BASE_URL}/api/analytics/devices?days_ago=30",
        expected_keys=["device_category", "sessions", "users"]
    ):
        passed_tests += 1

    # ========== Test 6: Dashboard Overview ==========
    print_step(6, total_tests, "Dashboard Overview (nuevo endpoint)")
    if test_endpoint(
        "Dashboard Overview",
        f"{BASE_URL}/api/analytics/dashboard/overview?days_ago=30",
        expected_keys=["totalSessions", "newUsers", "returningUsers", "trafficSources"]
    ):
        passed_tests += 1

    # ========== Test 7: Dashboard Cursos ==========
    print_step(7, total_tests, "Dashboard Cursos (filtrado por /cursos/)")
    if test_endpoint(
        "Dashboard Cursos",
        f"{BASE_URL}/api/analytics/dashboard/courses?days_ago=30&limit=20",
        expected_keys=["rank", "pageTitle", "pagePath", "slug", "pageViews"]
    ):
        passed_tests += 1

    # ========== Test 8: Dashboard Noticias ==========
    print_step(8, total_tests, "Dashboard Noticias (filtrado por /noticias/)")
    if test_endpoint(
        "Dashboard Noticias",
        f"{BASE_URL}/api/analytics/dashboard/news?days_ago=30&limit=20",
        expected_keys=["rank", "pageTitle", "pagePath", "slug", "pageViews"]
    ):
        passed_tests += 1

    # ========== Test 9: Ubicaciones Geográficas ==========
    print_step(9, total_tests, "Tráfico por Ubicación Geográfica")
    if test_endpoint(
        "Ubicaciones Geográficas",
        f"{BASE_URL}/api/analytics/geographic/locations?days_ago=30&limit=20",
        expected_keys=["rank", "city", "country", "sessions", "users"]
    ):
        passed_tests += 1

    # ========== Test 10: Tráfico Local vs Externo ==========
    print_step(10, total_tests, "Tráfico Local vs Externo (Chile)")
    if test_endpoint(
        "Tráfico Local vs Externo",
        f"{BASE_URL}/api/analytics/geographic/local-vs-external?country=Chile&days_ago=30",
        expected_keys=["local", "external", "total"]
    ):
        passed_tests += 1

    # ========== Test 11: Datos Históricos - Sesiones ==========
    print_step(11, total_tests, "Datos Históricos - Sesiones (últimos 90 días)")
    if test_endpoint(
        "Histórico de Sesiones",
        f"{BASE_URL}/api/analytics/historical?metric=sessions&days_ago=90",
        expected_keys=["date", "value", "metric"]
    ):
        passed_tests += 1

    # ========== Test 12: Datos Históricos - Usuarios Nuevos ==========
    print_step(12, total_tests, "Datos Históricos - Usuarios Nuevos (últimos 30 días)")
    if test_endpoint(
        "Histórico de Usuarios Nuevos",
        f"{BASE_URL}/api/analytics/historical?metric=newUsers&days_ago=30",
        expected_keys=["date", "value", "metric"]
    ):
        passed_tests += 1

    # ========== Test 13: Reporte Completo ==========
    print_step(13, total_tests, "Reporte Completo (endpoint original)")
    if test_endpoint(
        "Reporte Completo",
        f"{BASE_URL}/api/analytics/complete-report?days_ago=30",
        expected_keys=["overview", "traffic_sources", "top_pages", "devices"]
    ):
        passed_tests += 1

    # ========== Resumen Final ==========
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}Resumen de Pruebas{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}{'='*80}{Colors.RESET}")

    success_rate = (passed_tests / total_tests) * 100

    if passed_tests == total_tests:
        print(f"{Colors.GREEN}{Colors.BOLD}[SUCCESS] Todos los tests pasaron: {passed_tests}/{total_tests} ({success_rate:.1f}%){Colors.RESET}")
    elif passed_tests > total_tests / 2:
        print(f"{Colors.YELLOW}{Colors.BOLD}[PARTIAL] Tests parcialmente exitosos: {passed_tests}/{total_tests} ({success_rate:.1f}%){Colors.RESET}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}[FAILED] Muchos tests fallaron: {passed_tests}/{total_tests} ({success_rate:.1f}%){Colors.RESET}")

    print(f"\n{Colors.BOLD}Notas:{Colors.RESET}")
    print(f"  - Si ves advertencias sobre datos vacíos o ceros, es normal si no hay tráfico en ese período")
    print(f"  - Los endpoints de filtrado (/cursos/, /noticias/) pueden estar vacíos si no hay páginas con esos paths")
    print(f"  - Para pruebas locales, cambia BASE_URL a http://localhost:8000")
    print()


if __name__ == "__main__":
    main()
