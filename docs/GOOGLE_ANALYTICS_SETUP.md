# Google Analytics 4 - Guía de Configuración

Esta guía te ayudará a integrar Google Analytics 4 (GA4) con tu backend FastAPI para obtener datos analíticos de tu sitio web.

## Tabla de Contenidos

1. [Requisitos Previos](#requisitos-previos)
2. [Configuración en Google Cloud Console](#configuración-en-google-cloud-console)
3. [Configuración en Google Analytics 4](#configuración-en-google-analytics-4)
4. [Configuración del Backend](#configuración-del-backend)
5. [Uso de los Endpoints](#uso-de-los-endpoints)
6. [Solución de Problemas](#solución-de-problemas)

---

## Requisitos Previos

Antes de comenzar, asegúrate de tener:

- Una cuenta de Google Analytics 4 configurada
- Acceso a Google Cloud Console
- Permisos de administrador en tu propiedad de GA4
- Python 3.8+ instalado

---

## Configuración en Google Cloud Console

### Paso 1: Crear un Proyecto (si no tienes uno)

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Haz clic en el selector de proyectos en la parte superior
3. Haz clic en "Nuevo Proyecto"
4. Ingresa un nombre para tu proyecto
5. Haz clic en "Crear"

### Paso 2: Habilitar la API de Google Analytics Data

1. En Google Cloud Console, ve a "APIs y Servicios" > "Biblioteca"
2. Busca "Google Analytics Data API"
3. Haz clic en "Google Analytics Data API"
4. Haz clic en "Habilitar"

### Paso 3: Crear una Cuenta de Servicio

1. Ve a "APIs y Servicios" > "Credenciales"
2. Haz clic en "Crear credenciales" > "Cuenta de servicio"
3. Completa los detalles:
   - **Nombre**: `ga4-backend-service`
   - **Descripción**: "Cuenta de servicio para acceder a Google Analytics 4 desde el backend"
4. Haz clic en "Crear y continuar"
5. En "Otorgar acceso a este servicio", puedes omitir este paso (clic en "Continuar")
6. En "Otorgar acceso a los usuarios", omite también (clic en "Listo")

### Paso 4: Generar y Descargar la Clave JSON

1. En la lista de cuentas de servicio, haz clic en la cuenta que acabas de crear
2. Ve a la pestaña "Claves"
3. Haz clic en "Agregar clave" > "Crear clave nueva"
4. Selecciona "JSON"
5. Haz clic en "Crear"
6. Se descargará automáticamente un archivo JSON con las credenciales
7. **¡IMPORTANTE!** Guarda este archivo en un lugar seguro. Lo necesitarás más adelante

---

## Configuración en Google Analytics 4

### Paso 1: Obtener tu Property ID

1. Ve a [Google Analytics](https://analytics.google.com/)
2. Selecciona tu propiedad de GA4
3. Haz clic en "Administrador" (ícono de engranaje en la parte inferior izquierda)
4. En la columna "Propiedad", haz clic en "Configuración de la propiedad"
5. Copia el **ID de propiedad** (tiene el formato: `123456789`)

### Paso 2: Dar Permisos a la Cuenta de Servicio

1. En Google Analytics, ve a "Administrador"
2. En la columna "Propiedad", haz clic en "Acceso a la propiedad"
3. Haz clic en el botón "+" (Agregar usuarios)
4. Ingresa el email de tu cuenta de servicio
   - Lo encuentras en el archivo JSON descargado (campo `client_email`)
   - Tiene el formato: `nombre@proyecto.iam.gserviceaccount.com`
5. Selecciona el rol "**Visor**" (es suficiente para leer datos)
6. Desmarca "Notificar a este usuario por correo electrónico"
7. Haz clic en "Agregar"

---

## Configuración del Backend

### Paso 1: Instalar Dependencias

```bash
pip install -r requirements.txt
```

Esto instalará:
- `google-analytics-data` - Cliente oficial de Google Analytics Data API
- `google-auth` - Biblioteca de autenticación de Google

### Paso 2: Organizar el Archivo de Credenciales

1. Crea una carpeta para las credenciales (si no existe):

   ```bash
   mkdir credentials
   ```

2. Copia el archivo JSON descargado a esta carpeta:

   ```bash
   # Windows
   copy C:\Downloads\tu-archivo.json credentials\ga4-service-account.json

   # Linux/Mac
   cp ~/Downloads/tu-archivo.json credentials/ga4-service-account.json
   ```

3. **IMPORTANTE**: Agrega esta carpeta al `.gitignore` para no subir las credenciales al repositorio:

   ```bash
   echo "credentials/" >> .gitignore
   ```

### Paso 3: Configurar Variables de Entorno

1. Copia el archivo `.env.example` a `.env`:

   ```bash
   cp .env.example .env
   ```

2. Edita el archivo `.env` y configura las variables de Google Analytics.

   **Tienes 2 opciones:**

   #### Opción A: Archivo JSON (Recomendado para DESARROLLO)

   ```env
   # Ruta al archivo de credenciales
   GOOGLE_APPLICATION_CREDENTIALS=./credentials/ga4-service-account.json

   # Property ID de GA4
   GA4_PROPERTY_ID=properties/123456789
   ```

   **Ventajas:**
   - Más fácil de configurar localmente
   - Archivo separado del código

   **Desventajas:**
   - No puedes subir el archivo a producción por seguridad
   - Requiere sistema de archivos

   #### Opción B: JSON como String (Recomendado para PRODUCCIÓN) ⭐

   ```env
   # JSON completo como string (copia TODO el contenido del archivo)
   GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account","project_id":"tu-proyecto","private_key_id":"abc123","private_key":"-----BEGIN PRIVATE KEY-----\nMII...","client_email":"nombre@proyecto.iam.gserviceaccount.com","client_id":"123456789","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"https://www.googleapis.com/robot/v1/metadata/x509/..."}'

   # Property ID de GA4
   GA4_PROPERTY_ID=properties/123456789
   ```

   **Ventajas:**
   - ✅ **Perfecto para producción** (Heroku, Vercel, Railway, Docker, etc.)
   - ✅ No necesitas subir archivos al servidor
   - ✅ Se configura como variable de entorno estándar

   **Desventajas:**
   - Más largo de copiar/pegar

   **Cómo obtener el JSON como string:**

   1. Abre tu archivo `ga4-service-account.json` con un editor de texto
   2. Selecciona TODO el contenido del archivo
   3. Cópialo completo (desde `{` hasta `}`)
   4. Pégalo en el `.env` como valor de `GOOGLE_APPLICATION_CREDENTIALS_JSON`
   5. Asegúrate de que esté entre comillas simples `'...'`

   **Ejemplo de cómo se ve el JSON:**
   ```json
   {
     "type": "service_account",
     "project_id": "mi-proyecto-12345",
     "private_key_id": "abc123def456...",
     "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg...\n-----END PRIVATE KEY-----\n",
     "client_email": "ga4-backend@mi-proyecto-12345.iam.gserviceaccount.com",
     "client_id": "123456789012345678901",
     "auth_uri": "https://accounts.google.com/o/oauth2/auth",
     "token_uri": "https://oauth2.googleapis.com/token",
     "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
     "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
   }
   ```

### Paso 4: Verificar la Configuración

Inicia tu servidor FastAPI:

```bash
python main.py
```

Verifica que el servicio esté configurado correctamente visitando:

```
http://localhost:8000/api/analytics/health
```

Deberías recibir una respuesta como:

```json
{
  "status": "success",
  "configured": true,
  "property_id": "properties/123456789",
  "message": "Google Analytics 4 configurado correctamente"
}
```

---

## Uso de los Endpoints

### 1. Obtener Métricas Básicas

```http
GET /api/analytics?days_ago=7
```

**Respuesta:**

```json
{
  "status": "success",
  "data": {
    "sessions": 1250,
    "active_users": 980,
    "page_views": 4500,
    "bounce_rate": 45.3,
    "avg_session_duration": 180.5,
    "sessions_per_user": 1.27,
    "date_range": {
      "start_date": "2024-01-15",
      "end_date": "2024-01-22"
    }
  }
}
```

**Parámetros opcionales:**

- `start_date` (YYYY-MM-DD): Fecha de inicio
- `end_date` (YYYY-MM-DD): Fecha de fin
- `days_ago` (número): Días hacia atrás desde hoy (default: 7)

**Ejemplos:**

```http
# Últimos 30 días
GET /api/analytics?days_ago=30

# Rango personalizado
GET /api/analytics?start_date=2024-01-01&end_date=2024-01-31
```

### 2. Obtener Fuentes de Tráfico

```http
GET /api/analytics/traffic-sources?days_ago=7&limit=10
```

**Respuesta:**

```json
{
  "status": "success",
  "data": [
    {
      "source": "google",
      "medium": "organic",
      "sessions": 850,
      "users": 720
    },
    {
      "source": "facebook",
      "medium": "social",
      "sessions": 200,
      "users": 180
    }
  ],
  "count": 2
}
```

### 3. Obtener Páginas Más Visitadas

```http
GET /api/analytics/top-pages?days_ago=7&limit=10
```

**Respuesta:**

```json
{
  "status": "success",
  "data": [
    {
      "page_title": "Inicio",
      "page_path": "/",
      "page_views": 1500,
      "users": 900,
      "avg_session_duration": 200.5
    },
    {
      "page_title": "Carreras",
      "page_path": "/carreras",
      "page_views": 850,
      "users": 650,
      "avg_session_duration": 180.2
    }
  ],
  "count": 2
}
```

### 4. Obtener Desglose por Dispositivo

```http
GET /api/analytics/devices?days_ago=7
```

**Respuesta:**

```json
{
  "status": "success",
  "data": [
    {
      "device_category": "mobile",
      "sessions": 650,
      "users": 550,
      "bounce_rate": 48.5
    },
    {
      "device_category": "desktop",
      "sessions": 500,
      "users": 380,
      "bounce_rate": 40.2
    },
    {
      "device_category": "tablet",
      "sessions": 100,
      "users": 50,
      "bounce_rate": 52.1
    }
  ],
  "count": 3
}
```

### 5. Obtener Reporte Completo

```http
GET /api/analytics/complete-report?days_ago=7
```

**Respuesta:**

```json
{
  "status": "success",
  "data": {
    "overview": {
      "sessions": 1250,
      "active_users": 980,
      "page_views": 4500,
      "bounce_rate": 45.3,
      "avg_session_duration": 180.5,
      "sessions_per_user": 1.27,
      "date_range": {
        "start_date": "2024-01-15",
        "end_date": "2024-01-22"
      }
    },
    "traffic_sources": [...],
    "top_pages": [...],
    "devices": [...]
  }
}
```

---

## Solución de Problemas

### Error: "GOOGLE_APPLICATION_CREDENTIALS no está configurado"

**Causa:** La variable de entorno no está definida o el archivo `.env` no está siendo cargado.

**Solución:**

1. Verifica que el archivo `.env` existe en la raíz del proyecto
2. Verifica que la variable `GOOGLE_APPLICATION_CREDENTIALS` está definida en `.env`
3. Reinicia el servidor después de modificar `.env`

### Error: "No se encontró el archivo de credenciales"

**Causa:** La ruta al archivo JSON es incorrecta.

**Solución:**

1. Verifica que el archivo JSON existe en la ruta especificada
2. Si usas rutas relativas, asegúrate de que sean relativas a la raíz del proyecto
3. En Windows, puedes usar rutas absolutas: `C:/ruta/completa/archivo.json`

### Error: "GA4_PROPERTY_ID no está configurado"

**Causa:** No has configurado el Property ID de GA4.

**Solución:**

1. Ve a Google Analytics > Admin > Property Settings
2. Copia el Property ID (número de 9 dígitos)
3. Agrégalo al `.env` en formato: `GA4_PROPERTY_ID=properties/123456789`

### Error: "403 Forbidden" o "Permission Denied"

**Causa:** La cuenta de servicio no tiene permisos en GA4.

**Solución:**

1. Ve a Google Analytics > Admin > Property Access
2. Verifica que el email de la cuenta de servicio está agregado
3. Verifica que tiene rol de "Visor" al menos
4. Espera unos minutos después de agregar los permisos

### Error: "No rows returned" o métricas en cero

**Causa:** Puede ser que no haya datos para el período seleccionado.

**Solución:**

1. Verifica que estás consultando el Property ID correcto
2. Verifica que tu sitio web tiene tráfico en el período consultado
3. Verifica que el código de GA4 está instalado correctamente en tu sitio
4. Prueba con un rango de fechas más amplio (ej: `days_ago=30`)

### Error: "Unable to find the server"

**Causa:** Problemas de conectividad o credenciales inválidas.

**Solución:**

1. Verifica tu conexión a internet
2. Verifica que el archivo JSON no está corrupto
3. Descarga nuevamente las credenciales desde Google Cloud Console

---

## Configuración en Producción

### Método Recomendado: JSON como Variable de Entorno

Para producción (Heroku, Railway, Vercel, Docker, etc.), usa la variable `GOOGLE_APPLICATION_CREDENTIALS_JSON`:

#### En Heroku:

```bash
# Copia el contenido completo del JSON y ejecuta:
heroku config:set GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account",...}'
heroku config:set GA4_PROPERTY_ID=properties/123456789
```

#### En Railway:

1. Ve a tu proyecto en Railway
2. Variables > New Variable
3. Agrega `GOOGLE_APPLICATION_CREDENTIALS_JSON` con el JSON completo
4. Agrega `GA4_PROPERTY_ID` con tu Property ID

#### En Vercel:

1. Settings > Environment Variables
2. Agrega `GOOGLE_APPLICATION_CREDENTIALS_JSON` con el JSON completo
3. Agrega `GA4_PROPERTY_ID` con tu Property ID

#### En Docker:

```dockerfile
# En tu docker-compose.yml o Dockerfile
environment:
  - GOOGLE_APPLICATION_CREDENTIALS_JSON={"type":"service_account",...}
  - GA4_PROPERTY_ID=properties/123456789
```

O usando archivo `.env`:

```bash
docker run -d \
  --env-file .env \
  tu-imagen
```

#### En Servidor Linux (systemd):

```bash
# En /etc/systemd/system/tu-app.service
[Service]
Environment="GOOGLE_APPLICATION_CREDENTIALS_JSON={\"type\":\"service_account\",...}"
Environment="GA4_PROPERTY_ID=properties/123456789"
```

---

## Seguridad

### Mejores Prácticas

1. **Nunca subas el archivo JSON al repositorio**

   ```bash
   # Agrega al .gitignore
   credentials/
   *.json
   .env
   ```

2. **Usa variables de entorno en producción**

   En servicios como Heroku, Vercel, Railway, etc., configura las variables de entorno:

   - `GOOGLE_APPLICATION_CREDENTIALS`: Contenido completo del JSON (no la ruta)
   - `GA4_PROPERTY_ID`: Tu Property ID

3. **Limita los permisos de la cuenta de servicio**

   - Usa solo el rol "Visor" en GA4
   - No otorgues permisos de "Editor" o "Administrador" a menos que sea necesario

4. **Rota las credenciales periódicamente**

   - Cada 6-12 meses, genera nuevas credenciales
   - Elimina las credenciales antiguas después de migrar

---

## Métricas Disponibles

### Métricas Principales

- **sessions**: Número total de sesiones
- **activeUsers**: Usuarios activos únicos
- **screenPageViews**: Total de páginas vistas
- **bounceRate**: Porcentaje de sesiones de una sola página
- **averageSessionDuration**: Duración promedio de sesión (segundos)
- **sessionsPerUser**: Promedio de sesiones por usuario

### Dimensiones Disponibles

- **sessionSource**: Fuente del tráfico (google, facebook, etc.)
- **sessionMedium**: Medio del tráfico (organic, social, referral, etc.)
- **pageTitle**: Título de la página
- **pagePath**: Ruta de la página
- **deviceCategory**: Tipo de dispositivo (mobile, desktop, tablet)

---

## Recursos Adicionales

- [Google Analytics Data API Documentation](https://developers.google.com/analytics/devguides/reporting/data/v1)
- [Google Analytics Dimensions & Metrics](https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema)
- [Service Account Guide](https://cloud.google.com/iam/docs/service-accounts)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## Soporte

Si encuentras problemas o tienes preguntas:

1. Verifica el endpoint de health check: `/api/analytics/health`
2. Revisa los logs del servidor para errores específicos
3. Consulta la documentación oficial de Google Analytics Data API
4. Verifica que tu Property ID sea correcto (formato: `properties/123456789`)

---

**Última actualización:** Enero 2024
