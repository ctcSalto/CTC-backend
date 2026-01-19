# Google Workspace Admin Console - Guía de Configuración

## Fecha: 2025-12-28

---

## Tabla de Contenidos
- [Prerrequisitos](#prerrequisitos)
- [Paso 1: Crear Proyecto en Google Cloud Console](#paso-1-crear-proyecto-en-google-cloud-console)
- [Paso 2: Habilitar APIs Necesarias](#paso-2-habilitar-apis-necesarias)
- [Paso 3: Crear Service Account](#paso-3-crear-service-account)
- [Paso 4: Configurar Domain-Wide Delegation](#paso-4-configurar-domain-wide-delegation)
- [Paso 5: Descargar Credenciales](#paso-5-descargar-credenciales)
- [Paso 6: Obtener Customer ID](#paso-6-obtener-customer-id)
- [Paso 7: Crear Grupos Base](#paso-7-crear-grupos-base)
- [Paso 8: Configurar Variables de Entorno](#paso-8-configurar-variables-de-entorno)
- [Paso 9: Verificar Configuración](#paso-9-verificar-configuración)
- [Ambientes Test y Producción](#ambientes-test-y-producción)
- [Troubleshooting](#troubleshooting)

---

## Prerrequisitos

- ✅ Cuenta de Google Workspace con permisos de **Super Admin**
- ✅ Acceso a Google Cloud Console (console.cloud.google.com)
- ✅ Acceso a Google Admin Console (admin.google.com)
- ✅ Unidades Organizativas ya creadas en Google Admin
- ✅ Dominio verificado: `ctcsalto.edu.uy`

---

## IMPORTANTE: Service Account vs OAuth Client ID

### ¿Qué usar para este proyecto?

Para la integración de Google Workspace Admin SDK, **DEBES usar Service Account**, NO OAuth Client ID/Secret.

### ¿Por qué Service Account?

| Característica | Service Account | OAuth Client ID/Secret |
|----------------|-----------------|------------------------|
| **Tipo de autenticación** | Server-to-server | User-to-server |
| **Requiere interacción de usuario** | ❌ No | ✅ Sí (login Google) |
| **Ideal para backend** | ✅ Sí | ❌ No |
| **Domain-Wide Delegation** | ✅ Soportado | ❌ No |
| **Acceso a Admin SDK** | ✅ Completo | ❌ Limitado |
| **Expiración de token** | Auto-renovable | Requiere refresh manual |

### Conclusión
✅ **Usaremos Service Account con archivo JSON** (no Client ID/Secret)

---

## Paso 1: Crear Proyecto en Google Cloud Console

### 1.1 Acceder a Google Cloud Console
1. Ve a: https://console.cloud.google.com/
2. Inicia sesión con tu cuenta de Super Admin de Google Workspace

### 1.2 Crear Nuevo Proyecto
1. Haz clic en el **selector de proyectos** (arriba a la izquierda)
2. Clic en **"Nuevo Proyecto"** (New Project)
3. Configurar proyecto:
   ```
   Nombre del proyecto: Backend-CTC-Production
   Organización: ctcsalto.edu.uy
   Ubicación: Sin organización (o seleccionar ctcsalto.edu.uy si está disponible)
   ```
4. Clic en **"Crear"** (Create)
5. Espera a que se cree el proyecto (1-2 minutos)
6. Selecciona el proyecto recién creado

### 1.3 Crear Proyecto de Test (Opcional pero recomendado)
1. Repite el proceso anterior para crear:
   ```
   Nombre del proyecto: Backend-CTC-Test
   Organización: ctcsalto.edu.uy
   ```

> **Nota**: Tendrás 2 proyectos separados, cada uno con sus propias credenciales.

---

## Paso 2: Habilitar APIs Necesarias

### 2.1 Habilitar Admin SDK API
1. En Google Cloud Console, ve al menú (☰) → **APIs y servicios** → **Biblioteca**
2. Busca: `Admin SDK API`
3. Haz clic en **"Admin SDK API"**
4. Clic en **"Habilitar"** (Enable)
5. Espera a que se active (puede tardar 1-2 minutos)

### 2.2 Verificar APIs Habilitadas
1. Ve a: **APIs y servicios** → **Panel**
2. Deberías ver: **Admin SDK API** en la lista de APIs habilitadas

### 2.3 Repetir para Proyecto Test
- Cambia al proyecto `Backend-CTC-Test`
- Repite los pasos 2.1 y 2.2

---

## Paso 3: Crear Service Account

### 3.1 Acceder a Service Accounts
1. En Google Cloud Console, ve al menú (☰)
2. **IAM y administración** → **Cuentas de servicio** (Service Accounts)
3. Asegúrate de estar en el proyecto correcto (Backend-CTC-Production)

### 3.2 Crear Service Account - PRODUCCIÓN
1. Clic en **"+ Crear cuenta de servicio"** (Create Service Account)
2. Configurar Service Account:

   **Paso 1: Detalles de la cuenta de servicio**
   ```
   Nombre de la cuenta de servicio: backend-ctc-workspace-admin
   ID de la cuenta de servicio: backend-ctc-workspace-admin
   Descripción: Service Account para gestión de usuarios en Google Workspace via Admin SDK
   ```
   Clic en **"Crear y continuar"**

   **Paso 2: Otorgar acceso a este proyecto (Opcional)**
   - Puedes omitir este paso
   - Clic en **"Continuar"**

   **Paso 3: Otorgar acceso a los usuarios (Opcional)**
   - Puedes omitir este paso
   - Clic en **"Listo"**

### 3.3 Crear Service Account - TEST
1. Cambia al proyecto `Backend-CTC-Test`
2. Repite el paso 3.2 con el mismo nombre:
   ```
   Nombre: backend-ctc-workspace-admin-test
   ID: backend-ctc-workspace-admin-test
   Descripción: Service Account de TEST para Google Workspace Admin SDK
   ```

### 3.4 Copiar Email de Service Account

Después de crear, verás algo como:
```
backend-ctc-workspace-admin@backend-ctc-production.iam.gserviceaccount.com
```

**Copia este email**, lo necesitarás en el Paso 4.

---

## Paso 4: Configurar Domain-Wide Delegation

Esta es la parte MÁS IMPORTANTE. Domain-Wide Delegation permite que el Service Account actúe en nombre de usuarios del dominio.

### 4.1 Obtener Client ID del Service Account

1. En **Google Cloud Console** → **IAM y administración** → **Cuentas de servicio**
2. Encuentra tu Service Account: `backend-ctc-workspace-admin@...`
3. Haz clic en los **3 puntos** (⋮) a la derecha
4. Selecciona **"Administrar detalles"** o haz clic en el email
5. Ve a la pestaña **"Detalles"**
6. Busca el campo: **"ID único (Client ID)"** o **"OAuth 2 Client ID"**
7. **Copia este número** (es un número largo, ej: `1234567890123456789`)

### 4.2 Configurar en Google Admin Console

1. Abre una **nueva pestaña** y ve a: https://admin.google.com/
2. Inicia sesión con tu cuenta de **Super Admin**
3. En el menú lateral, ve a:
   - **Seguridad** → **Acceso y control de datos** → **Controles de API**
   - O busca: "Delegación en todo el dominio" (Domain-wide delegation)

4. En la sección **"Delegación en todo el dominio"**, clic en **"Administrar la delegación en todo el dominio"**

5. Clic en **"Agregar nuevo"** (Add new)

6. Configurar delegación:
   ```
   ID de cliente: [Pega el Client ID copiado en 4.1]
   Ámbitos de OAuth: https://www.googleapis.com/auth/admin.directory.user,https://www.googleapis.com/auth/admin.directory.group,https://www.googleapis.com/auth/admin.directory.orgunit,https://www.googleapis.com/auth/admin.directory.userschema
   ```

   **IMPORTANTE**: Los scopes deben estar separados por comas SIN ESPACIOS.

7. Clic en **"Autorizar"** (Authorize)

### 4.3 Verificar Delegación

Deberías ver tu Service Account en la lista con los scopes autorizados.

### 4.4 Repetir para Service Account de TEST

- Obtén el Client ID del Service Account de test
- Agrégalo a la misma sección de Domain-Wide Delegation
- Usa los mismos scopes

> **Nota**: Ambos Service Accounts (prod y test) se configuran en el **mismo** Google Admin Console, porque es el **mismo dominio** (ctcsalto.edu.uy).

---

## Paso 5: Descargar Credenciales

### 5.1 Crear Clave para Service Account - PRODUCCIÓN

1. Vuelve a **Google Cloud Console**
2. Asegúrate de estar en el proyecto: `Backend-CTC-Production`
3. Ve a: **IAM y administración** → **Cuentas de servicio**
4. Haz clic en el Service Account: `backend-ctc-workspace-admin@...`
5. Ve a la pestaña **"Claves"** (Keys)
6. Clic en **"Agregar clave"** → **"Crear clave nueva"**
7. Selecciona tipo: **JSON**
8. Clic en **"Crear"**

Un archivo JSON se descargará automáticamente:
```
backend-ctc-production-1a2b3c4d5e6f.json
```

### 5.2 Crear Clave para Service Account - TEST

1. Cambia al proyecto: `Backend-CTC-Test`
2. Repite los pasos 5.1
3. Descarga el JSON de test

### 5.3 Guardar Archivos Seguros

**MUY IMPORTANTE:**
- ❌ **NUNCA** subir estos archivos a Git
- ❌ **NUNCA** compartir estos archivos públicamente
- ✅ Guardar en ubicación segura (ej: 1Password, Vault)
- ✅ Agregar a `.gitignore`:
  ```
  # Google Service Account Keys
  *-service-account.json
  backend-ctc-*.json
  google-credentials*.json
  ```

### 5.4 Renombrar Archivos (Opcional)

Para mayor claridad:
```bash
# Renombrar
backend-ctc-production-1a2b3c4d5e6f.json → google-workspace-prod.json
backend-ctc-test-1a2b3c4d5e6f.json → google-workspace-test.json
```

---

## Paso 6: Obtener Customer ID

El Customer ID es el ID único de tu organización de Google Workspace.

### 6.1 Obtener desde Google Admin Console

1. Ve a: https://admin.google.com/
2. En el menú lateral, ve a: **Cuenta** → **Configuración de la cuenta** → **Perfil**
3. Busca el campo: **"ID de cliente"** o **"Customer ID"**
4. Copia el valor (formato: `C0xxxxxxx`)

Ejemplo:
```
Customer ID: C01234567
```

---

## Paso 7: Crear Grupos Base

Vamos a crear los grupos de Google Workspace que usará el sistema.

### 7.1 Acceder a Grupos

1. Ve a: https://admin.google.com/
2. En el menú lateral: **Directorio** → **Grupos**

### 7.2 Crear Grupos Principales

Para cada grupo, haz clic en **"Crear grupo"** y configura:

#### Grupo 1: Todos los Alumnos
```
Nombre del grupo: Alumnos
Correo electrónico del grupo: alumnos@ctcsalto.edu.uy
Descripción: Todos los estudiantes de CTC Salto
```

#### Grupo 2: Equipo Docente
```
Nombre del grupo: Docentes
Correo electrónico del grupo: docentes@ctcsalto.edu.uy
Descripción: Todos los profesores y tutores
```

#### Grupo 3: Coordinación Académica
```
Nombre del grupo: Coordinación Académica
Correo electrónico del grupo: coordinacion@ctcsalto.edu.uy
Descripción: Coordinadores y administradores académicos
```

#### Grupo 4: Administración
```
Nombre del grupo: Administración
Correo electrónico del grupo: administracion@ctcsalto.edu.uy
Descripción: Equipo administrativo y de ventas
```

#### Grupo 5: Gestión de Datos
```
Nombre del grupo: Gestión de Datos
Correo electrónico del grupo: datos@ctcsalto.edu.uy
Descripción: Equipo de análisis y gestión de datos
```

#### Grupo 6: Personal (Todos menos alumnos)
```
Nombre del grupo: Personal
Correo electrónico del grupo: personal@ctcsalto.edu.uy
Descripción: Todo el personal de CTC (docentes, admin, coordinación)
```

#### Grupo 7: Todos
```
Nombre del grupo: Todos
Correo electrónico del grupo: todos@ctcsalto.edu.uy
Descripción: Todos los usuarios de CTC Salto
```

### 7.3 Configurar Permisos de Grupo

Para cada grupo:
1. Haz clic en el grupo
2. Ve a **"Configuración"** → **"Permisos del grupo"**
3. Configura:
   ```
   ¿Quién puede publicar?: Solo miembros del grupo
   ¿Quién puede ver conversaciones?: Solo miembros del grupo
   ¿Quién puede unirse al grupo?: Solo propietarios invitan
   ```

---

## Paso 8: Configurar Variables de Entorno

### 8.1 Actualizar `.env` - PRODUCCIÓN

Agrega estas variables a tu archivo `.env` de producción:

```bash
# === Google Workspace API - PRODUCTION ===
GOOGLE_WORKSPACE_ENVIRONMENT=production
GOOGLE_WORKSPACE_ADMIN_EMAIL=admin@ctcsalto.edu.uy
GOOGLE_WORKSPACE_CUSTOMER_ID=C01234567
GOOGLE_WORKSPACE_DOMAIN=ctcsalto.edu.uy

# Service Account (opción 1: ruta al archivo)
GOOGLE_WORKSPACE_SERVICE_ACCOUNT_FILE=/path/to/google-workspace-prod.json

# Service Account (opción 2: contenido JSON en base64)
# GOOGLE_WORKSPACE_SERVICE_ACCOUNT_JSON=eyJ0eXBlIjogInNlcnZpY2...

# URLs del backend (para callbacks si los necesitas)
BACKEND_URL_PRODUCTION=https://api.ctcsalto.edu.uy
BACKEND_URL_TEST=https://api-test.ctcsalto.edu.uy
```

### 8.2 Actualizar `.env.example`

Agrega un ejemplo sin valores reales:

```bash
# === Google Workspace API ===
GOOGLE_WORKSPACE_ENVIRONMENT=production
GOOGLE_WORKSPACE_ADMIN_EMAIL=admin@your-domain.edu.uy
GOOGLE_WORKSPACE_CUSTOMER_ID=C0xxxxxxx
GOOGLE_WORKSPACE_DOMAIN=your-domain.edu.uy
GOOGLE_WORKSPACE_SERVICE_ACCOUNT_FILE=/path/to/service-account.json
# O usar: GOOGLE_WORKSPACE_SERVICE_ACCOUNT_JSON=<base64-encoded-json>

# URLs del backend
BACKEND_URL_PRODUCTION=https://api.your-domain.edu.uy
BACKEND_URL_TEST=https://api-test.your-domain.edu.uy
```

### 8.3 Variables para Ambiente TEST

Para tu ambiente de test, crea un archivo `.env.test`:

```bash
# === Google Workspace API - TEST ===
GOOGLE_WORKSPACE_ENVIRONMENT=test
GOOGLE_WORKSPACE_ADMIN_EMAIL=admin@ctcsalto.edu.uy
GOOGLE_WORKSPACE_CUSTOMER_ID=C01234567
GOOGLE_WORKSPACE_DOMAIN=ctcsalto.edu.uy
GOOGLE_WORKSPACE_SERVICE_ACCOUNT_FILE=/path/to/google-workspace-test.json

BACKEND_URL_PRODUCTION=https://api.ctcsalto.edu.uy
BACKEND_URL_TEST=https://api-test.ctcsalto.edu.uy
```

---

## Paso 9: Verificar Configuración

### 9.1 Checklist de Verificación

- [ ] ✅ Proyecto creado en Google Cloud Console (Prod + Test)
- [ ] ✅ Admin SDK API habilitada en ambos proyectos
- [ ] ✅ Service Account creado en ambos proyectos
- [ ] ✅ Domain-Wide Delegation configurada para ambos Service Accounts
- [ ] ✅ Archivos JSON descargados y guardados de forma segura
- [ ] ✅ Customer ID obtenido
- [ ] ✅ 7 grupos creados en Google Admin
- [ ] ✅ Variables de entorno configuradas
- [ ] ✅ Archivos JSON agregados a `.gitignore`

### 9.2 Script de Prueba (Ejecutar después de implementación)

Una vez implementado el código, ejecutarás:

```bash
# Test de conexión
python scripts/test_google_workspace_connection.py
```

Este script verificará:
- ✅ Conexión a Google Workspace API
- ✅ Autenticación con Service Account
- ✅ Permisos de Domain-Wide Delegation
- ✅ Acceso a usuarios, grupos y OUs

---

## Ambientes Test y Producción

### Estrategia Recomendada

#### Opción 1: Dos Proyectos, Mismo Dominio (Recomendado)
```
Google Cloud Projects:
├── Backend-CTC-Production
│   └── Service Account: backend-ctc-workspace-admin@backend-ctc-production.iam.gserviceaccount.com
│
└── Backend-CTC-Test
    └── Service Account: backend-ctc-workspace-admin-test@backend-ctc-test.iam.gserviceaccount.com

Google Workspace Domain (compartido):
└── ctcsalto.edu.uy
    ├── Usuarios: gestionados por ambos proyectos
    ├── Grupos: compartidos
    └── OUs: compartidas
```

**Ventajas:**
- ✅ Mismos usuarios en ambos ambientes
- ✅ Fácil testing sin duplicar usuarios
- ✅ Credenciales separadas para seguridad

**Desventajas:**
- ⚠️ El ambiente test modifica usuarios reales
- ⚠️ Requiere cuidado al testear eliminaciones

#### Opción 2: Dos Proyectos, Dominio Test Separado (Ideal pero requiere segundo dominio)
```
Si tienes un dominio test (ej: ctcsalto-test.edu.uy):
├── Backend-CTC-Production → ctcsalto.edu.uy
└── Backend-CTC-Test → ctcsalto-test.edu.uy
```

**Ventajas:**
- ✅ Completo aislamiento
- ✅ Testing sin riesgo

**Desventajas:**
- ❌ Requiere segundo dominio Google Workspace
- ❌ Costo adicional

### Recomendación Final

**Usar Opción 1** (dos proyectos, mismo dominio) porque:
- Ya tienes un dominio configurado
- Puedes crear usuarios de test con prefijo (ej: `test-usuario@ctcsalto.edu.uy`)
- Menor costo y complejidad

---

## Troubleshooting

### Error: "Access Not Configured"
**Causa:** Admin SDK API no habilitada
**Solución:**
1. Ve a Google Cloud Console
2. APIs y servicios → Biblioteca
3. Busca y habilita "Admin SDK API"
4. Espera 5-10 minutos para que se propague

### Error: "Insufficient Permission" o "Not Authorized"
**Causa:** Domain-Wide Delegation no configurada correctamente
**Solución:**
1. Verifica que copiaste el Client ID correcto
2. Verifica que los scopes estén sin espacios:
   ```
   https://www.googleapis.com/auth/admin.directory.user,https://www.googleapis.com/auth/admin.directory.group,https://www.googleapis.com/auth/admin.directory.orgunit,https://www.googleapis.com/auth/admin.directory.userschema
   ```
3. Espera 5-10 minutos para que los cambios se propaguen
4. Limpia caché del navegador

### Error: "Invalid Grant"
**Causa:** El admin_email no tiene permisos de Super Admin
**Solución:**
1. Ve a Google Admin Console
2. Usuarios → selecciona el usuario admin
3. Roles y privilegios → asignar "Super Admin"

### Error: "Customer not found"
**Causa:** Customer ID incorrecto
**Solución:**
1. Ve a Google Admin Console → Cuenta → Configuración → Perfil
2. Copia el Customer ID exacto (incluye la 'C')

### Error al cargar archivo JSON
**Causa:** Ruta incorrecta o permisos de archivo
**Solución:**
1. Verifica que la ruta sea absoluta
2. Verifica permisos del archivo: `chmod 600 google-workspace-prod.json`
3. Prueba usar la opción de base64 en lugar de archivo

---

## Contactos y Recursos

### Documentación Oficial
- [Google Workspace Admin SDK](https://developers.google.com/admin-sdk)
- [Service Account Authentication](https://developers.google.com/identity/protocols/oauth2/service-account)
- [Domain-Wide Delegation](https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority)

### Consolas
- Google Cloud Console: https://console.cloud.google.com/
- Google Admin Console: https://admin.google.com/
- API Dashboard: https://console.cloud.google.com/apis/dashboard

### Soporte
- Google Workspace Support: https://support.google.com/a/
- Stack Overflow: Tag `google-admin-sdk`

---

## Siguiente Paso

Una vez completados todos estos pasos:

1. ✅ Verifica el checklist del Paso 9
2. ✅ Guarda las credenciales de forma segura
3. ✅ Actualiza las variables de entorno
4. ✅ Notifica al equipo de desarrollo que la configuración está lista
5. ✅ Procede con la implementación del código

---

**Guía de Configuración - Google Workspace Admin Console**
**Versión:** 1.0
**Última Actualización:** 2025-12-28
**Autor:** Backend CTC Team
