"""
Script de prueba para verificar la configuración de Google Analytics 4
Ejecuta: python test_ga4_connection.py
"""
import os
import sys

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Variables de entorno cargadas desde .env")
except ImportError:
    print("⚠️  python-dotenv no instalado, usando variables del sistema")

# Verificar variables de entorno
print("\n" + "="*60)
print("VERIFICANDO CONFIGURACIÓN")
print("="*60)

credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
property_id = os.getenv('GA4_PROPERTY_ID')

print(f"\n1. GOOGLE_APPLICATION_CREDENTIALS_JSON: {'✅ Configurado' if credentials_json else '❌ No configurado'}")
if credentials_json:
    print(f"   Longitud: {len(credentials_json)} caracteres")
    print(f"   Comienza con: {credentials_json[:30]}...")

print(f"\n2. GOOGLE_APPLICATION_CREDENTIALS: {'✅ Configurado' if credentials_path else '❌ No configurado'}")
if credentials_path:
    print(f"   Ruta: {credentials_path}")
    print(f"   Archivo existe: {'✅ Sí' if os.path.exists(credentials_path) else '❌ No'}")

print(f"\n3. GA4_PROPERTY_ID: {'✅ Configurado' if property_id else '❌ No configurado'}")
if property_id:
    print(f"   Valor: {property_id}")
    print(f"   Formato correcto: {'✅ Sí' if property_id.startswith('properties/') else '⚠️  Debe comenzar con properties/'}")

# Intentar inicializar el servicio
print("\n" + "="*60)
print("PROBANDO CONEXIÓN CON GOOGLE ANALYTICS 4")
print("="*60 + "\n")

try:
    from external_services.google.analytics import analytics_service
    print("✅ Servicio de Google Analytics inicializado correctamente")

    # Intentar obtener métricas
    print("\n⏳ Obteniendo métricas de los últimos 7 días...")
    metrics = analytics_service.get_basic_metrics(days_ago=7)

    print("\n✅ ¡CONEXIÓN EXITOSA! Datos obtenidos:")
    print(f"\n   📊 Sesiones: {metrics['sessions']}")
    print(f"   👥 Usuarios activos: {metrics['active_users']}")
    print(f"   📄 Páginas vistas: {metrics['page_views']}")
    print(f"   📈 Tasa de rebote: {metrics['bounce_rate']}%")
    print(f"   ⏱️  Duración promedio sesión: {metrics['avg_session_duration']}s")
    print(f"   🔄 Sesiones por usuario: {metrics['sessions_per_user']}")
    print(f"\n   📅 Período: {metrics['date_range']['start_date']} a {metrics['date_range']['end_date']}")

    print("\n" + "="*60)
    print("🎉 TODO FUNCIONA CORRECTAMENTE")
    print("="*60)
    print("\nPuedes usar los endpoints de la API:")
    print("  • GET http://localhost:8000/api/analytics")
    print("  • GET http://localhost:8000/api/analytics/traffic-sources")
    print("  • GET http://localhost:8000/api/analytics/top-pages")
    print("  • GET http://localhost:8000/api/analytics/devices")
    print("  • GET http://localhost:8000/api/analytics/complete-report")

except ImportError as e:
    print(f"❌ Error importando el servicio: {e}")
    print("\n💡 Asegúrate de que las dependencias estén instaladas:")
    print("   pip install google-analytics-data google-auth")
    sys.exit(1)

except ValueError as e:
    print(f"❌ Error de configuración: {e}")
    print("\n💡 Verifica tu archivo .env y las variables de entorno")
    sys.exit(1)

except Exception as e:
    print(f"❌ Error inesperado: {e}")
    print(f"\n🔍 Tipo de error: {type(e).__name__}")

    # Mostrar más detalles si es un error de permisos
    error_str = str(e).lower()
    if 'permission' in error_str or '403' in error_str:
        print("\n💡 Error de permisos. Verifica que:")
        print("   1. El email de la cuenta de servicio esté agregado en GA4")
        print("   2. Tenga rol de 'Visor' al menos")
        print("   3. El Property ID sea correcto")
        print(f"   4. Email de cuenta de servicio: {credentials_json[credentials_json.find('client_email')+15:credentials_json.find('client_email')+80] if credentials_json and 'client_email' in credentials_json else 'No encontrado'}")

    import traceback
    print("\n📋 Stack trace completo:")
    traceback.print_exc()
    sys.exit(1)
