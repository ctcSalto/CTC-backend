"""
Script de prueba completo para endpoints de Google Workspace y Google Analytics
Ejecuta: python test_google_endpoints.py
"""
import sys
import requests
import json
import time
from datetime import datetime

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuración
BASE_URL = "https://backend-backend-ctc-develop.vtu0xl.easypanel.host"
# BASE_URL = "http://localhost:8000"  # Descomentar para testing local

# Colores para la consola
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Imprime un header grande"""
    print("\n" + "="*80)
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.END}")
    print("="*80)

def print_step(step_number, text):
    """Imprime un paso de la ejecución"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}[PASO {step_number}]{Colors.END} {text}")

def print_success(text):
    """Imprime mensaje de éxito"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    """Imprime mensaje de error"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    """Imprime mensaje de advertencia"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    """Imprime información"""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

def print_json(data, indent=2):
    """Imprime JSON formateado"""
    print(json.dumps(data, indent=indent, ensure_ascii=False))

def make_request(method, endpoint, data=None, params=None):
    """Hace una petición HTTP y retorna la respuesta"""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, params=params, timeout=30)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        elif method == "PUT":
            response = requests.put(url, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, json=data, timeout=30)

        return response
    except requests.exceptions.RequestException as e:
        print_error(f"Error en la petición: {str(e)}")
        return None

# ============================================================================
# TESTS DE GOOGLE WORKSPACE
# ============================================================================

def test_google_workspace():
    """Prueba todos los endpoints de Google Workspace"""
    print_header("🔵 PRUEBAS DE GOOGLE WORKSPACE")

    # Generar email único con timestamp
    timestamp = int(time.time())
    test_email = f"test.user.{timestamp}@ctcsalto.edu.uy"
    test_group_email = f"test-group-{timestamp}@ctcsalto.edu.uy"

    print_info(f"Email de prueba: {test_email}")
    print_info(f"Grupo de prueba: {test_group_email}")

    # PASO 1: Generar contraseña
    print_step(1, "Generar contraseña segura")
    response = make_request("GET", "/google/test/generate-password", params={"length": 12})
    if response and response.status_code == 200:
        password_data = response.json()
        password = password_data.get("password")
        print_success("Contraseña generada")
        print_info(f"Contraseña: {password}")
        print_json(password_data)
    else:
        print_error(f"Error generando contraseña: {response.status_code if response else 'Sin respuesta'}")
        return False

    # PASO 2: Crear usuario
    print_step(2, "Crear usuario en Google Workspace")
    user_data = {
        "primaryEmail": test_email,
        "givenName": "Test",
        "familyName": "Usuario",
        "password": password,
        "orgUnitPath": "/Alumnos"
    }
    response = make_request("POST", "/google/test/create-account", data=user_data)
    if response and response.status_code == 201:
        result = response.json()
        print_success("Usuario creado exitosamente")
        print_json(result)
    else:
        print_error(f"Error creando usuario: {response.status_code if response else 'Sin respuesta'}")
        if response:
            print_json(response.json())
        return False

    # Esperar un poco para que se propague en Google
    time.sleep(2)

    # PASO 3: Obtener información del usuario
    print_step(3, "Obtener información del usuario")
    response = make_request("POST", "/google/test/get-account", data={"primaryEmail": test_email})
    if response and response.status_code == 200:
        result = response.json()
        print_success("Información del usuario obtenida")
        print_json(result)
    else:
        print_error(f"Error obteniendo usuario: {response.status_code if response else 'Sin respuesta'}")

    # PASO 4: Actualizar usuario
    print_step(4, "Actualizar información del usuario")
    update_data = {
        "primaryEmail": test_email,
        "givenName": "Test Modificado",
        "familyName": "Usuario Actualizado"
    }
    response = make_request("POST", "/google/test/update-account", data=update_data)
    if response and response.status_code == 200:
        result = response.json()
        print_success("Usuario actualizado exitosamente")
        print_json(result)
    else:
        print_error(f"Error actualizando usuario: {response.status_code if response else 'Sin respuesta'}")

    time.sleep(2)

    # PASO 5: Crear grupo
    print_step(5, "Crear grupo en Google Workspace")
    group_data = {
        "groupEmail": test_group_email,
        "groupName": f"Test Group {timestamp}",
        "description": "Grupo de prueba creado automáticamente"
    }
    response = make_request("POST", "/google/test/create-group", data=group_data)
    if response and response.status_code == 201:
        result = response.json()
        print_success("Grupo creado exitosamente")
        print_json(result)
    else:
        print_error(f"Error creando grupo: {response.status_code if response else 'Sin respuesta'}")
        if response:
            print_json(response.json())

    time.sleep(2)

    # PASO 6: Listar grupos
    print_step(6, "Listar grupos de Google Workspace")
    response = make_request("GET", "/google/test/list-groups", params={"max_results": 5})
    if response and response.status_code == 200:
        result = response.json()
        print_success(f"Grupos listados: {result.get('data', {}).get('groups', []).__len__() if 'data' in result else 0}")
        print_json(result)
    else:
        print_error(f"Error listando grupos: {response.status_code if response else 'Sin respuesta'}")

    # PASO 7: Agregar usuario al grupo
    print_step(7, "Agregar usuario al grupo")
    add_to_group_data = {
        "primaryEmail": test_email,
        "groupId": test_group_email
    }
    response = make_request("POST", "/google/test/add-to-group", data=add_to_group_data)
    if response and response.status_code == 200:
        result = response.json()
        print_success("Usuario agregado al grupo exitosamente")
        print_json(result)
    else:
        print_error(f"Error agregando usuario al grupo: {response.status_code if response else 'Sin respuesta'}")
        if response:
            print_json(response.json())

    time.sleep(2)

    # PASO 8: Listar miembros del grupo
    print_step(8, "Listar miembros del grupo")
    response = make_request("POST", "/google/test/list-group-members", data={"groupEmail": test_group_email})
    if response and response.status_code == 200:
        result = response.json()
        print_success("Miembros del grupo listados")
        print_json(result)
    else:
        print_error(f"Error listando miembros: {response.status_code if response else 'Sin respuesta'}")

    # PASO 9: Remover usuario del grupo
    print_step(9, "Remover usuario del grupo")
    response = make_request("POST", "/google/test/remove-from-group", data=add_to_group_data)
    if response and response.status_code == 200:
        result = response.json()
        print_success("Usuario removido del grupo exitosamente")
        print_json(result)
    else:
        print_error(f"Error removiendo usuario del grupo: {response.status_code if response else 'Sin respuesta'}")

    time.sleep(2)

    # PASO 10: Suspender usuario
    print_step(10, "Suspender usuario")
    response = make_request("POST", "/google/test/suspend-account", data={"primaryEmail": test_email})
    if response and response.status_code == 200:
        result = response.json()
        print_success("Usuario suspendido exitosamente")
        print_json(result)
    else:
        print_error(f"Error suspendiendo usuario: {response.status_code if response else 'Sin respuesta'}")

    time.sleep(1)

    # PASO 11: Reactivar usuario
    print_step(11, "Reactivar usuario")
    response = make_request("POST", "/google/test/unsuspend-account", data={"primaryEmail": test_email})
    if response and response.status_code == 200:
        result = response.json()
        print_success("Usuario reactivado exitosamente")
        print_json(result)
    else:
        print_error(f"Error reactivando usuario: {response.status_code if response else 'Sin respuesta'}")

    time.sleep(2)

    # PASO 12: Eliminar usuario
    print_step(12, "Eliminar usuario de Google Workspace")
    response = make_request("POST", "/google/test/delete-account", data={"primaryEmail": test_email})
    if response and response.status_code == 200:
        result = response.json()
        print_success("Usuario eliminado exitosamente")
        print_json(result)
    else:
        print_error(f"Error eliminando usuario: {response.status_code if response else 'Sin respuesta'}")

    time.sleep(2)

    # PASO 13: Eliminar grupo
    print_step(13, "Eliminar grupo de Google Workspace")
    response = make_request("POST", "/google/test/delete-group", data={"groupId": test_group_email})
    if response and response.status_code == 200:
        result = response.json()
        print_success("Grupo eliminado exitosamente")
        print_json(result)
    else:
        print_error(f"Error eliminando grupo: {response.status_code if response else 'Sin respuesta'}")

    print_success("Pruebas de Google Workspace completadas")
    return True

# ============================================================================
# TESTS DE GOOGLE ANALYTICS
# ============================================================================

def test_google_analytics():
    """Prueba todos los endpoints de Google Analytics"""
    print_header("📊 PRUEBAS DE GOOGLE ANALYTICS 4")

    # PASO 0: Debug - Ver variables de entorno en el servidor
    print_step(0, "Debug: Verificar variables de entorno en el servidor")
    response = make_request("GET", "/api/analytics/debug-env")
    if response and response.status_code == 200:
        result = response.json()
        print_info("Variables de entorno que ve el servidor:")
        print_json(result)
    else:
        print_warning(f"No se pudo obtener debug info: {response.status_code if response else 'Sin respuesta'}")

    # PASO 1: Health check
    print_step(1, "Verificar configuración de Google Analytics")
    response = make_request("GET", "/api/analytics/health")
    if response and response.status_code == 200:
        result = response.json()
        print_success("Configuración verificada")
        print_json(result)

        if not result.get("configured"):
            print_error("Google Analytics no está configurado correctamente")
            return False
    else:
        print_error(f"Error en health check: {response.status_code if response else 'Sin respuesta'}")
        return False

    # PASO 2: Métricas básicas (últimos 30 días)
    print_step(2, "Obtener métricas básicas (últimos 30 días)")
    response = make_request("GET", "/api/analytics", params={"days_ago": 30})
    if response and response.status_code == 200:
        result = response.json()
        print_success("Métricas básicas obtenidas")

        data = result.get("data", {})
        print(f"\n   📊 Sesiones: {data.get('sessions', 0)}")
        print(f"   👥 Usuarios activos: {data.get('active_users', 0)}")
        print(f"   📄 Páginas vistas: {data.get('page_views', 0)}")
        print(f"   📈 Tasa de rebote: {data.get('bounce_rate', 0)}%")
        print(f"   ⏱️  Duración promedio: {data.get('avg_session_duration', 0)}s")
        print(f"   🔄 Sesiones por usuario: {data.get('sessions_per_user', 0)}")

        date_range = data.get('date_range', {})
        print(f"\n   📅 Período: {date_range.get('start_date')} a {date_range.get('end_date')}")
    else:
        print_error(f"Error obteniendo métricas: {response.status_code if response else 'Sin respuesta'}")
        if response:
            print_json(response.json())

    # PASO 3: Métricas con rango personalizado
    print_step(3, "Obtener métricas con rango personalizado (últimos 90 días)")
    response = make_request("GET", "/api/analytics", params={"days_ago": 90})
    if response and response.status_code == 200:
        result = response.json()
        print_success("Métricas obtenidas para 90 días")
        data = result.get("data", {})
        print(f"\n   📊 Sesiones totales: {data.get('sessions', 0)}")
        print(f"   👥 Usuarios totales: {data.get('active_users', 0)}")
    else:
        print_error(f"Error obteniendo métricas: {response.status_code if response else 'Sin respuesta'}")

    # PASO 4: Fuentes de tráfico
    print_step(4, "Obtener fuentes de tráfico (top 10)")
    response = make_request("GET", "/api/analytics/traffic-sources", params={"days_ago": 90, "limit": 10})
    if response and response.status_code == 200:
        result = response.json()
        print_success(f"Fuentes de tráfico obtenidas: {result.get('count', 0)} resultados")

        sources = result.get("data", [])
        if sources:
            print("\n   Top fuentes de tráfico:")
            for i, source in enumerate(sources[:5], 1):
                print(f"   {i}. {source.get('source')} / {source.get('medium')} - {source.get('sessions')} sesiones")
        else:
            print_warning("No hay datos de fuentes de tráfico")
    else:
        print_error(f"Error obteniendo fuentes: {response.status_code if response else 'Sin respuesta'}")

    # PASO 5: Páginas más visitadas
    print_step(5, "Obtener páginas más visitadas (top 10)")
    response = make_request("GET", "/api/analytics/top-pages", params={"days_ago": 90, "limit": 10})
    if response and response.status_code == 200:
        result = response.json()
        print_success(f"Páginas obtenidas: {result.get('count', 0)} resultados")

        pages = result.get("data", [])
        if pages:
            print("\n   Top páginas más visitadas:")
            for i, page in enumerate(pages[:5], 1):
                print(f"   {i}. {page.get('page_path')} - {page.get('page_views')} vistas")
        else:
            print_warning("No hay datos de páginas")
    else:
        print_error(f"Error obteniendo páginas: {response.status_code if response else 'Sin respuesta'}")

    # PASO 6: Desglose por dispositivo
    print_step(6, "Obtener desglose por dispositivo")
    response = make_request("GET", "/api/analytics/devices", params={"days_ago": 90})
    if response and response.status_code == 200:
        result = response.json()
        print_success(f"Dispositivos obtenidos: {result.get('count', 0)} categorías")

        devices = result.get("data", [])
        if devices:
            print("\n   Desglose por dispositivo:")
            for device in devices:
                print(f"   • {device.get('device_category')}: {device.get('sessions')} sesiones ({device.get('bounce_rate')}% rebote)")
        else:
            print_warning("No hay datos de dispositivos")
    else:
        print_error(f"Error obteniendo dispositivos: {response.status_code if response else 'Sin respuesta'}")

    # PASO 7: Reporte completo
    print_step(7, "Obtener reporte completo")
    response = make_request("GET", "/api/analytics/complete-report", params={"days_ago": 90})
    if response and response.status_code == 200:
        result = response.json()
        print_success("Reporte completo obtenido")

        data = result.get("data", {})
        print(f"\n   📊 Overview:")
        overview = data.get("overview", {})
        print(f"      - Sesiones: {overview.get('sessions', 0)}")
        print(f"      - Usuarios: {overview.get('active_users', 0)}")

        print(f"\n   🌐 Fuentes de tráfico: {len(data.get('traffic_sources', []))} fuentes")
        print(f"   📄 Top páginas: {len(data.get('top_pages', []))} páginas")
        print(f"   📱 Dispositivos: {len(data.get('devices', []))} categorías")
    else:
        print_error(f"Error obteniendo reporte: {response.status_code if response else 'Sin respuesta'}")

    print_success("Pruebas de Google Analytics completadas")
    return True

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Función principal"""
    print_header(f"🚀 INICIANDO TESTS DE ENDPOINTS DE GOOGLE")
    print_info(f"URL Base: {BASE_URL}")
    print_info(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Determinar qué tests ejecutar (desde argumentos o todos por defecto)
    import sys
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        # Ejecutar ambos por defecto
        choice = "3"

    print("\n" + "="*80)
    print("Tests a ejecutar:")
    if choice == "1":
        print("✓ Google Workspace solamente")
    elif choice == "2":
        print("✓ Google Analytics solamente")
    else:
        print("✓ Google Workspace + Google Analytics")
    print("="*80)

    results = {
        "workspace": None,
        "analytics": None,
        "start_time": time.time()
    }

    try:
        if choice in ["1", "3"]:
            results["workspace"] = test_google_workspace()

        if choice in ["2", "3"]:
            results["analytics"] = test_google_analytics()

    except KeyboardInterrupt:
        print_warning("\n\nTests interrumpidos por el usuario")
    except Exception as e:
        print_error(f"\n\nError inesperado: {str(e)}")
        import traceback
        traceback.print_exc()

    # Resumen final
    elapsed_time = time.time() - results["start_time"]

    print_header("📋 RESUMEN DE RESULTADOS")

    if results["workspace"] is not None:
        status = "✅ EXITOSO" if results["workspace"] else "❌ FALLÓ"
        print(f"Google Workspace: {status}")

    if results["analytics"] is not None:
        status = "✅ EXITOSO" if results["analytics"] else "❌ FALLÓ"
        print(f"Google Analytics:  {status}")

    print(f"\n⏱️  Tiempo total: {elapsed_time:.2f} segundos")
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
