"""
Script de diagnóstico detallado para Google Analytics 4
"""
import os
import sys
from datetime import datetime, timedelta

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account
import json

print("="*70)
print("DIAGNÓSTICO DETALLADO DE GOOGLE ANALYTICS 4")
print("="*70)

# 1. Verificar credenciales
credentials_json_str = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
property_id = os.getenv('GA4_PROPERTY_ID')

print(f"\n1. Property ID: {property_id}")

# Parsear las credenciales para ver el email
try:
    creds_data = json.loads(credentials_json_str)
    print(f"2. Email de la cuenta de servicio: {creds_data.get('client_email')}")
    print(f"3. Project ID: {creds_data.get('project_id')}")
except:
    print("❌ Error parseando credenciales")
    sys.exit(1)

# Inicializar cliente
credentials = service_account.Credentials.from_service_account_info(
    creds_data,
    scopes=['https://www.googleapis.com/auth/analytics.readonly']
)
client = BetaAnalyticsDataClient(credentials=credentials)

print("\n" + "="*70)
print("PROBANDO DIFERENTES RANGOS DE FECHAS")
print("="*70)

# Probar diferentes rangos de fechas
date_ranges = [
    ("Últimos 7 días", 7),
    ("Últimos 30 días", 30),
    ("Últimos 90 días", 90),
    ("Último año", 365),
]

for label, days in date_ranges:
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    try:
        request = RunReportRequest(
            property=property_id,
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            metrics=[
                Metric(name="sessions"),
                Metric(name="activeUsers"),
            ],
        )

        response = client.run_report(request)

        if response.rows:
            sessions = int(response.rows[0].metric_values[0].value)
            users = int(response.rows[0].metric_values[1].value)
            print(f"\n✅ {label} ({start_date} a {end_date}):")
            print(f"   Sesiones: {sessions}")
            print(f"   Usuarios: {users}")
        else:
            print(f"\n⚠️  {label} ({start_date} a {end_date}): No hay datos")

    except Exception as e:
        print(f"\n❌ Error en {label}: {str(e)}")

# Probar con rango muy amplio
print("\n" + "="*70)
print("PROBANDO CON RANGO MÁXIMO (últimos 2 años)")
print("="*70)

try:
    request = RunReportRequest(
        property=property_id,
        date_ranges=[DateRange(start_date="2023-01-01", end_date=datetime.now().strftime('%Y-%m-%d'))],
        metrics=[
            Metric(name="sessions"),
            Metric(name="activeUsers"),
            Metric(name="screenPageViews"),
        ],
    )

    response = client.run_report(request)

    if response.rows:
        sessions = int(response.rows[0].metric_values[0].value)
        users = int(response.rows[0].metric_values[1].value)
        pageviews = int(response.rows[0].metric_values[2].value)
        print(f"\n✅ Datos desde 2023-01-01:")
        print(f"   Sesiones totales: {sessions}")
        print(f"   Usuarios totales: {users}")
        print(f"   Páginas vistas totales: {pageviews}")
    else:
        print("\n❌ No hay datos en absoluto desde 2023")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")

# Verificar metadata de la propiedad
print("\n" + "="*70)
print("VERIFICANDO METADATA DE LA PROPIEDAD")
print("="*70)

try:
    # Obtener dimensiones y métricas disponibles
    request = RunReportRequest(
        property=property_id,
        date_ranges=[DateRange(start_date="2023-01-01", end_date=datetime.now().strftime('%Y-%m-%d'))],
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="sessions")],
        limit=10,
    )

    response = client.run_report(request)

    print(f"\nTotal de filas en respuesta: {response.row_count}")

    if response.rows:
        print("\nÚltimas 10 fechas con datos:")
        for row in response.rows[:10]:
            date = row.dimension_values[0].value
            sessions = row.metric_values[0].value
            print(f"   {date}: {sessions} sesiones")
    else:
        print("\n⚠️  No se encontraron datos por fecha")

except Exception as e:
    print(f"\n❌ Error obteniendo metadata: {str(e)}")
    if "403" in str(e) or "permission" in str(e).lower():
        print("\n🚨 ERROR DE PERMISOS DETECTADO:")
        print("   1. Ve a Google Analytics > Admin > Property Access")
        print(f"   2. Verifica que este email esté agregado: {creds_data.get('client_email')}")
        print("   3. Debe tener rol de 'Visor' o superior")
        print("   4. Verifica que el Property ID sea correcto")
        print(f"   5. Property ID actual: {property_id}")

print("\n" + "="*70)
print("INSTRUCCIONES ADICIONALES")
print("="*70)
print("\nPara verificar tu Property ID correcto:")
print("1. Ve a Google Analytics (https://analytics.google.com/)")
print("2. Selecciona tu propiedad")
print("3. Ve a Admin (engranaje abajo a la izquierda)")
print("4. En la columna 'Propiedad', clic en 'Detalles de la propiedad'")
print("5. Copia el 'ID de la propiedad' (solo números)")
print(f"6. En tu .env debe ser: GA4_PROPERTY_ID=properties/[ESE_NUMERO]")
print(f"7. Actualmente tienes: {property_id}")

print("\nPara verificar permisos:")
print("1. En Admin > Acceso a la propiedad")
print(f"2. Busca este email: {creds_data.get('client_email')}")
print("3. Si no está, agrégalo con rol 'Visor'")
