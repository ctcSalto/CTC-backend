# Google Workspace Service - Integración vía n8n

## Descripción

Este módulo proporciona integración con Google Workspace Admin SDK a través de webhooks de n8n.

## Configuración

### Variables de Entorno

Agrega estas variables a tu archivo `.env`:

```bash
# n8n Webhooks - Google Workspace Integration
N8N_BASE_URL=https://automatizaciones-n8n.vtu0xl.easypanel.host/webhook-test
N8N_API_TOKEN=MobuEZYKJfic3G4LoRbliS2u4IyLq1Aup7qQ3L9KCFORBJfDbVCAD090VPZDLZM3
N8N_TIMEOUT=30
```

**Nota:** Para producción, cambia `/webhook-test` por `/webhook`

## Uso

### 1. Importar el servicio

```python
from external_services.google import google_workspace_service, generate_secure_password
```

### 2. Crear usuario en Google Workspace

```python
# Generar contraseña segura
password = generate_secure_password(12)

# Crear usuario
result = google_workspace_service.create_google_account(
    primary_email="estudiante@ctcsalto.edu.uy",
    given_name="Juan",
    family_name="Pérez",
    password=password,
    org_unit_path="/Alumnos"
)

print(f"Usuario creado: {result}")
print(f"Contraseña temporal: {password}")
```

### 3. Actualizar usuario

```python
result = google_workspace_service.update_google_account(
    user_email="estudiante@ctcsalto.edu.uy",
    given_name="Juan Carlos",
    org_unit_path="/Equipo Docente"
)
```

### 4. Suspender usuario

```python
result = google_workspace_service.suspend_google_account(
    user_email="estudiante@ctcsalto.edu.uy"
)
```

### 5. Eliminar usuario

```python
result = google_workspace_service.delete_google_account(
    user_email="estudiante@ctcsalto.edu.uy"
)
```

### 6. Agregar usuario a grupo

```python
result = google_workspace_service.add_user_to_group(
    user_email="estudiante@ctcsalto.edu.uy",
    group_email="alumnos@ctcsalto.edu.uy"
)
```

## Endpoints de Testing

El módulo incluye endpoints de testing en `/google/test/`:

### Crear cuenta

```bash
POST /google/test/create-account
{
  "primaryEmail": "test@ctcsalto.edu.uy",
  "givenName": "Test",
  "familyName": "User",
  "orgUnitPath": "/Alumnos",
  "generatePassword": true
}
```

### Actualizar cuenta

```bash
POST /google/test/update-account
{
  "userEmail": "test@ctcsalto.edu.uy",
  "givenName": "Test Updated",
  "orgUnitPath": "/Equipo Docente"
}
```

### Suspender cuenta

```bash
POST /google/test/suspend-account
{
  "userEmail": "test@ctcsalto.edu.uy"
}
```

### Eliminar cuenta

```bash
POST /google/test/delete-account
{
  "userEmail": "test@ctcsalto.edu.uy"
}
```

### Listar cuentas

```bash
GET /google/test/list-accounts?max_results=50
```

### Agregar a grupo

```bash
POST /google/test/add-to-group
{
  "userEmail": "test@ctcsalto.edu.uy",
  "groupEmail": "alumnos@ctcsalto.edu.uy"
}
```

### Generar contraseña

```bash
GET /google/test/generate-password?length=12
```

## Unidades Organizativas Disponibles

- `/Alumnos` - Estudiantes
- `/Equipo Docente` - Profesores y tutores
- `/Coordinación Académica` - Coordinadores
- `/Administración y Ventas` - Personal administrativo
- `/Gestión de Datos` - Equipo de datos

## Grupos Disponibles

- `alumnos@ctcsalto.edu.uy` - Todos los estudiantes
- `docentes@ctcsalto.edu.uy` - Todos los docentes
- `coordinacion@ctcsalto.edu.uy` - Coordinadores
- `administracion@ctcsalto.edu.uy` - Personal administrativo
- `datos@ctcsalto.edu.uy` - Equipo de datos
- `personal@ctcsalto.edu.uy` - Todo el personal (no alumnos)
- `todos@ctcsalto.edu.uy` - Todos los usuarios

## Manejo de Errores

El servicio lanza `ValueError` en caso de errores:

```python
try:
    result = google_workspace_service.create_google_account(...)
except ValueError as e:
    print(f"Error: {e}")
    # Manejar error (rollback, logging, etc.)
```

## Estructura del Proyecto

```
external_services/google/
├── __init__.py              # Exports del módulo
├── README.md                # Esta documentación
├── google_service.py        # Servicio principal
├── utils.py                 # Utilidades (generador de contraseñas)
└── workspace/
    ├── PLANNING.md          # Planificación completa
    ├── GOOGLE_CONSOLE_SETUP.md  # Guía de configuración
    └── N8N_WORKFLOWS.md     # Documentación de workflows n8n
```

## Workflows de n8n Requeridos

Este servicio requiere los siguientes webhooks configurados en n8n:

1. `createGoogleAccount` - Crear usuario
2. `updateGoogleAccount` - Actualizar usuario
3. `deleteGoogleAccount` - Eliminar usuario
4. `getGoogleAccount` - Obtener información de usuario
5. `listGoogleAccounts` - Listar usuarios
6. `addUserToGroup` - Agregar usuario a grupo
7. `removeUserFromGroup` - Remover usuario de grupo
8. `createGoogleGroup` - Crear grupo
9. `deleteGoogleGroup` - Eliminar grupo
10. `listGroupMembers` - Listar miembros de grupo

## Próximos Pasos

1. Configurar workflows en n8n
2. Testear cada endpoint con datos reales
3. Integrar con UserService para sincronización automática
4. Implementar rollback en caso de errores
5. Agregar logging y monitoreo

## Soporte

Para problemas o dudas, consulta la documentación completa en:
- [PLANNING.md](workspace/PLANNING.md)
- [GOOGLE_CONSOLE_SETUP.md](workspace/GOOGLE_CONSOLE_SETUP.md)
