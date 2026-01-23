# Google Workspace API - Planificación de Integración

## Fecha de Planificación
2025-12-28

---

## Tabla de Contenidos
- [Objetivo](#objetivo)
- [Alcance de la Integración](#alcance-de-la-integración)
- [Arquitectura Propuesta](#arquitectura-propuesta)
- [Análisis del Modelo User Actual](#análisis-del-modelo-user-actual)
- [Modificaciones Necesarias al Modelo User](#modificaciones-necesarias-al-modelo-user)
- [Unidades Organizativas y Mapeo de Roles](#unidades-organizativas-y-mapeo-de-roles)
- [Grupos de Google Workspace](#grupos-de-google-workspace)
- [Flujos de Integración](#flujos-de-integración)
- [Estructura de Archivos Propuesta](#estructura-de-archivos-propuesta)
- [Endpoints a Implementar](#endpoints-a-implementar)
- [Modelos y Payloads](#modelos-y-payloads)
- [Configuración y Credenciales](#configuración-y-credenciales)
- [Plan de Sincronización](#plan-de-sincronización)
- [Manejo de Errores y Rollback](#manejo-de-errores-y-rollback)
- [Consideraciones de Seguridad](#consideraciones-de-seguridad)
- [Plan de Migración de Datos](#plan-de-migración-de-datos)
- [Testing](#testing)
- [Roadmap de Implementación](#roadmap-de-implementación)

---

## Objetivo

Integrar Google Workspace Admin SDK API para:
1. **Gestión centralizada de usuarios** en 3 plataformas:
   - Backend CTC (base de datos local)
   - Google Workspace (cuentas educativas @ctcsalto.edu.uy)
   - Moodle LMS (autenticación vía Google)

2. **Sincronización automática** de usuarios entre plataformas
3. **Gestión de cuotas** de Google for Education
4. **Control de grupos y unidades organizativas**

---

## Alcance de la Integración

### Fase 1: CRUD de Usuarios en Google Workspace
- ✅ Crear usuario en Google Workspace al registrar usuario local
- ✅ Actualizar usuario en Google Workspace al modificar usuario local
- ✅ Suspender/Eliminar usuario en Google Workspace al desactivar usuario local
- ✅ Asignar usuarios a Unidades Organizativas
- ✅ Generación de contraseñas seguras automáticas

### Fase 2: Gestión de Grupos
- ✅ CRUD de grupos de Google Workspace
- ✅ Agregar/remover usuarios de grupos
- ✅ Sincronización de grupos con roles locales

### Fase 3: Sincronización con Moodle
- ✅ Integración con el flujo existente de Moodle
- ✅ Crear usuario Moodle con autenticación Google
- ✅ Eliminar usuario Moodle al eliminar cuenta Google

### Fuera de Alcance (Futuras Integraciones)
- ❌ Gmail API
- ❌ Google Drive API
- ❌ Google Classroom API
- ❌ Google Calendar API
- ❌ Google Meet API (ya integrado en Moodle)

---

## Arquitectura Propuesta

```
┌─────────────────────────────────────────────────────────────────┐
│                  Backend CTC - User Registration                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              UserService.create_user()                           │
│  1. Validar datos                                                │
│  2. Hashear contraseña (local)                                   │
│  3. Guardar en DB local                                          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         GoogleWorkspaceService.create_workspace_user()           │
│  1. Generar contraseña temporal segura                           │
│  2. Determinar orgUnitPath según rol                             │
│  3. Crear usuario en Google Workspace                            │
│  4. Guardar googleWorkspaceId en DB local                        │
│  5. (Opcional) Asignar a grupos                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         MoodleService.create_moodle_user()                       │
│  1. Crear usuario Moodle con auth='google'                       │
│  2. Configurar email @ctcsalto.edu.uy                            │
│  3. Guardar moodleUserId en DB local                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Usuario creado en 3 plataformas                │
│  ✅ Backend CTC (userId)                                         │
│  ✅ Google Workspace (googleWorkspaceId)                         │
│  ✅ Moodle LMS (moodleUserId) con login Google                   │
└─────────────────────────────────────────────────────────────────┘
```

### Flujo de Eliminación (Soft Delete Local + Hard Delete Google/Moodle)

```
┌─────────────────────────────────────────────────────────────────┐
│          UserService.delete_user(userId)                         │
│  1. Marcar user.active = False (soft delete local)               │
│  2. Actualizar modificationDate                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│   GoogleWorkspaceService.delete_workspace_user()                 │
│  1. Eliminar usuario de Google Workspace (liberar cuota)         │
│  2. Actualizar googleWorkspaceId = null en DB                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         MoodleService.delete_moodle_user()                       │
│  1. Eliminar usuario de Moodle                                   │
│  2. Actualizar moodleUserId = null en DB                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│     Usuario desactivado localmente y eliminado de sistemas       │
│     externos (libera cupo de Google for Education)               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Análisis del Modelo User Actual

### Campos Existentes en [database/models/user.py](../../../database/models/user.py)

```python
class User(SQLModel, table=True):
    userId: Optional[int]              # PK local
    email: str                         # Único, será @ctcsalto.edu.uy
    name: str                          # givenName en Google
    lastname: str                      # familyName en Google
    phone: str                         # No usado en Google
    document: str                      # Único, podría ser idnumber
    rol: UserRole                      # ADMIN | STUDENT
    confirmed: bool                    # Confirmación local
    creationDate: date                 # Audit trail
    modificationDate: Optional[date]   # Audit trail
    lastAccess: Optional[date]         # Audit trail local
    password: str                      # Hasheado, solo local
    active: bool                       # Soft delete local
```

### Fortalezas del Modelo Actual
✅ Campos de auditoría completos
✅ Soft delete implementado
✅ Validación de contraseñas robusta
✅ Roles bien definidos
✅ Email y documento únicos

### Debilidades para Integración con Google
❌ No almacena ID de Google Workspace
❌ No almacena contraseña temporal de Google
❌ No almacena Unidad Organizativa asignada
❌ No indica si el usuario tiene cuenta Google activa
❌ Rol solo tiene 2 valores (ADMIN, STUDENT), falta mapeo a OUs
❌ No almacena grupos de Google Workspace
❌ No almacena ID de Moodle (ya debería tenerlo por integración existente)

---

## Modificaciones Necesarias al Modelo User

### Nuevos Campos a Agregar

```python
class User(SQLModel, table=True):
    # ... campos existentes ...

    # === Google Workspace Integration ===
    googleWorkspaceId: Optional[str] = Field(default=None, unique=True, index=True)
    # ID único del usuario en Google Workspace (email completo)

    googleOrgUnitPath: Optional[str] = Field(default=None, max_length=255)
    # Unidad organizativa asignada en Google
    # Ej: "/Alumnos", "/Equipo Docente", "/Administración y Ventas"

    googleSuspended: bool = Field(default=False)
    # Indica si la cuenta de Google está suspendida

    googleCreatedAt: Optional[datetime] = None
    # Fecha de creación en Google Workspace

    googleLastSync: Optional[datetime] = None
    # Última sincronización con Google Workspace

    # === Moodle Integration ===
    moodleUserId: Optional[int] = Field(default=None, unique=True, index=True)
    # ID del usuario en Moodle (si ya no existe)

    moodleUsername: Optional[str] = Field(default=None, max_length=100)
    # Username en Moodle

    # === Additional Fields ===
    organizationalUnit: Optional[str] = Field(default=None, max_length=100)
    # Unidad organizativa interna (puede diferir de Google OU)
    # Valores: "administracion_ventas", "alumnos", "coordinacion_academica",
    #          "equipo_docente", "gestion_datos"
```

### Nuevo Enum para Unidades Organizativas

```python
class OrganizationalUnit(str, Enum):
    """Unidades organizativas de CTC Salto"""
    ADMINISTRACION_VENTAS = "administracion_ventas"
    ALUMNOS = "alumnos"
    COORDINACION_ACADEMICA = "coordinacion_academica"
    EQUIPO_DOCENTE = "equipo_docente"
    GESTION_DATOS = "gestion_datos"

    @property
    def google_path(self) -> str:
        """Mapeo a paths de Google Workspace"""
        mapping = {
            self.ADMINISTRACION_VENTAS: "/Administración y Ventas",
            self.ALUMNOS: "/Alumnos",
            self.COORDINACION_ACADEMICA: "/Coordinación Académica",
            self.EQUIPO_DOCENTE: "/Equipo Docente",
            self.GESTION_DATOS: "/Gestión de Datos",
        }
        return mapping[self]
```

### Actualización de UserRole

```python
class UserRole(str, Enum):
    ADMIN = "admin"
    STUDENT = "student"
    TEACHER = "teacher"          # Nuevo: Docentes
    COORDINATOR = "coordinator"  # Nuevo: Coordinadores académicos
    SALES = "sales"              # Nuevo: Equipo de ventas
    DATA_MANAGER = "data_manager"  # Nuevo: Gestión de datos

    @property
    def default_org_unit(self) -> OrganizationalUnit:
        """Mapeo automático de rol a unidad organizativa"""
        mapping = {
            self.ADMIN: OrganizationalUnit.ADMINISTRACION_VENTAS,
            self.STUDENT: OrganizationalUnit.ALUMNOS,
            self.TEACHER: OrganizationalUnit.EQUIPO_DOCENTE,
            self.COORDINATOR: OrganizationalUnit.COORDINACION_ACADEMICA,
            self.SALES: OrganizationalUnit.ADMINISTRACION_VENTAS,
            self.DATA_MANAGER: OrganizationalUnit.GESTION_DATOS,
        }
        return mapping[self]
```

### Migración de Base de Datos

**Archivo de migración Alembic necesario:**

```python
# alembic/versions/XXXXXX_add_google_workspace_fields.py

def upgrade():
    # Agregar columnas para Google Workspace
    op.add_column('user', sa.Column('googleWorkspaceId', sa.String(255), nullable=True))
    op.add_column('user', sa.Column('googleOrgUnitPath', sa.String(255), nullable=True))
    op.add_column('user', sa.Column('googleSuspended', sa.Boolean(), default=False))
    op.add_column('user', sa.Column('googleCreatedAt', sa.DateTime(), nullable=True))
    op.add_column('user', sa.Column('googleLastSync', sa.DateTime(), nullable=True))

    # Agregar columnas para Moodle (si no existen)
    op.add_column('user', sa.Column('moodleUserId', sa.Integer(), nullable=True))
    op.add_column('user', sa.Column('moodleUsername', sa.String(100), nullable=True))

    # Agregar columna para unidad organizativa interna
    op.add_column('user', sa.Column('organizationalUnit', sa.String(100), nullable=True))

    # Índices para optimización
    op.create_index('ix_user_googleWorkspaceId', 'user', ['googleWorkspaceId'], unique=True)
    op.create_index('ix_user_moodleUserId', 'user', ['moodleUserId'], unique=True)

def downgrade():
    op.drop_index('ix_user_moodleUserId', 'user')
    op.drop_index('ix_user_googleWorkspaceId', 'user')
    op.drop_column('user', 'organizationalUnit')
    op.drop_column('user', 'moodleUsername')
    op.drop_column('user', 'moodleUserId')
    op.drop_column('user', 'googleLastSync')
    op.drop_column('user', 'googleCreatedAt')
    op.drop_column('user', 'googleSuspended')
    op.drop_column('user', 'googleOrgUnitPath')
    op.drop_column('user', 'googleWorkspaceId')
```

---

## Unidades Organizativas y Mapeo de Roles

### Unidades Organizativas en Google Workspace

```
ctcsalto.edu.uy (Raíz)
│
├── Administración y Ventas
│   ├── Políticas: Sin acceso a recursos educativos
│   ├── Usuarios tipo: Administradores, personal de ventas
│   └── Permisos: Gmail, Drive (limitado), Calendar
│
├── Alumnos
│   ├── Políticas: Acceso a Classroom, Meet (limitado)
│   ├── Usuarios tipo: Estudiantes
│   └── Permisos: Gmail educativo, Drive, Classroom (estudiante)
│
├── Coordinación Académica
│   ├── Políticas: Acceso completo a recursos educativos
│   ├── Usuarios tipo: Coordinadores, administradores académicos
│   └── Permisos: Gmail, Drive, Classroom (admin), Meet
│
├── Equipo Docente
│   ├── Políticas: Acceso a recursos de enseñanza
│   ├── Usuarios tipo: Profesores, tutores
│   └── Permisos: Gmail, Drive, Classroom (teacher), Meet
│
└── Gestión de Datos
    ├── Políticas: Acceso a datos y reportes
    ├── Usuarios tipo: Analistas, gestores de datos
    └── Permisos: Gmail, Drive, Sheets
```

### Tabla de Mapeo: Rol Local → Unidad Organizativa

| Rol Backend (UserRole) | Unidad Organizativa Google | OrgUnitPath | isAdmin |
|------------------------|----------------------------|-------------|---------|
| ADMIN | Administración y Ventas | `/Administración y Ventas` | true |
| STUDENT | Alumnos | `/Alumnos` | false |
| TEACHER | Equipo Docente | `/Equipo Docente` | false |
| COORDINATOR | Coordinación Académica | `/Coordinación Académica` | false |
| SALES | Administración y Ventas | `/Administración y Ventas` | false |
| DATA_MANAGER | Gestión de Datos | `/Gestión de Datos` | false |

---

## Grupos de Google Workspace

### Grupos Principales a Crear

```python
class GoogleWorkspaceGroup(str, Enum):
    """Grupos de Google Workspace para organización"""

    # Grupos académicos
    ALL_STUDENTS = "alumnos@ctcsalto.edu.uy"
    ALL_TEACHERS = "docentes@ctcsalto.edu.uy"
    COORDINATORS = "coordinacion@ctcsalto.edu.uy"

    # Grupos administrativos
    ADMIN_TEAM = "administracion@ctcsalto.edu.uy"
    SALES_TEAM = "ventas@ctcsalto.edu.uy"
    DATA_TEAM = "datos@ctcsalto.edu.uy"

    # Grupos por carrera (dinámicos, a crear según careers en DB)
    # Ej: "carrera-administracion@ctcsalto.edu.uy"

    # Grupos especiales
    ALL_STAFF = "personal@ctcsalto.edu.uy"  # Todos excepto alumnos
    EVERYONE = "todos@ctcsalto.edu.uy"  # Todos los usuarios
```

### Mapeo Automático: Rol → Grupos

| UserRole | Grupos Asignados Automáticamente |
|----------|----------------------------------|
| ADMIN | admin_team, all_staff, everyone |
| STUDENT | all_students, everyone |
| TEACHER | all_teachers, all_staff, everyone |
| COORDINATOR | coordinators, all_staff, everyone |
| SALES | sales_team, all_staff, everyone |
| DATA_MANAGER | data_team, all_staff, everyone |

---

## Flujos de Integración

### Flujo 1: Creación de Usuario

```
1. Usuario se registra en frontend
   ↓
2. POST /auth/register
   - Valida datos (email, documento, contraseña)
   - Email debe ser @ctcsalto.edu.uy (validar en backend)
   ↓
3. UserService.create_user()
   - Crea usuario en DB local
   - Hashea contraseña
   - Asigna rol (default: STUDENT)
   - Estado: confirmed=False, active=False (requiere confirmación admin)
   ↓
4. [NUEVO] GoogleWorkspaceService.create_workspace_user()
   - Genera contraseña temporal segura (16 chars, mayús, minús, números, especiales)
   - Determina orgUnitPath según rol
   - Crea usuario en Google Workspace API
   - Configura changePasswordAtNextLogin=true
   - Guarda googleWorkspaceId en DB
   ↓
5. [NUEVO] GoogleWorkspaceService.add_user_to_groups()
   - Asigna usuario a grupos según rol
   ↓
6. [EXISTENTE] MoodleService.create_moodle_user()
   - Crea usuario en Moodle con auth='google'
   - Email: mismo que Google Workspace
   - Guarda moodleUserId en DB
   ↓
7. Enviar email con:
   - Email: usuario@ctcsalto.edu.uy
   - Contraseña temporal
   - Instrucciones de primer login
   - Link a Moodle (login automático con Google)
```

### Flujo 2: Confirmación de Usuario por Admin

```
1. Admin confirma usuario en panel
   ↓
2. POST /auth/confirm/{userId}
   - Actualiza confirmed=True, active=True en DB local
   ↓
3. [NUEVO] GoogleWorkspaceService.unsuspend_user()
   - Activa cuenta de Google (si estaba suspendida)
   ↓
4. [OPCIONAL] Enviar email de bienvenida
```

### Flujo 3: Actualización de Usuario

```
1. Admin actualiza datos de usuario
   ↓
2. PUT /auth/users/{userId}
   - Valida cambios (email, nombre, apellido, rol)
   ↓
3. UserService.update_user()
   - Actualiza DB local
   ↓
4. [NUEVO] GoogleWorkspaceService.update_workspace_user()
   - Actualiza nombre/apellido en Google
   - Si cambió rol: mover a nueva OrgUnit
   - Si cambió rol: actualizar grupos
   - Actualiza googleLastSync
   ↓
5. [EXISTENTE] MoodleService.update_moodle_user()
   - Actualiza datos en Moodle
```

### Flujo 4: Desactivación de Usuario (Soft Delete Local)

```
1. Admin desactiva usuario
   ↓
2. POST /auth/deactivate/{userId}
   - Marca active=False en DB local (soft delete)
   ↓
3. [NUEVO] GoogleWorkspaceService.suspend_user()
   - Suspende cuenta en Google (libera licencia pero mantiene datos)
   - Marca googleSuspended=True
   ↓
4. [OPCIONAL] Mantener usuario en Moodle pero suspendido
```

### Flujo 5: Eliminación Definitiva de Usuario

```
1. Admin elimina usuario definitivamente
   ↓
2. DELETE /auth/users/{userId}
   - Mantiene soft delete en DB local (active=False)
   ↓
3. [NUEVO] GoogleWorkspaceService.delete_workspace_user()
   - ELIMINA usuario de Google Workspace (libera cupo)
   - Actualiza googleWorkspaceId=null
   - Actualiza googleSuspended=null
   ↓
4. [NUEVO] MoodleService.delete_moodle_user()
   - ELIMINA usuario de Moodle
   - Actualiza moodleUserId=null
   ↓
5. Resultado: Usuario desactivado localmente, eliminado de Google y Moodle
```

### Flujo 6: Sincronización Manual (Admin Panel)

```
1. Admin ejecuta sincronización manual
   ↓
2. POST /google/workspace/sync/users
   ↓
3. GoogleWorkspaceService.sync_all_users()
   - Lista todos los usuarios activos en DB local
   - Para cada usuario:
     a. Verifica si existe en Google (por googleWorkspaceId o email)
     b. Si no existe: crear en Google
     c. Si existe: comparar datos y actualizar si difieren
     d. Actualizar googleLastSync
   - Retorna reporte: creados, actualizados, errores
```

---

## Estructura de Archivos Propuesta

```
external_services/
└── google/
    ├── __init__.py
    ├── workspace/
    │   ├── __init__.py
    │   ├── PLANNING.md                 # Este archivo
    │   │
    │   ├── config/
    │   │   ├── __init__.py
    │   │   └── workspace_config.py     # Configuración, credenciales, scopes
    │   │
    │   ├── models/
    │   │   ├── __init__.py
    │   │   ├── user_models.py          # Modelos de usuario Google
    │   │   ├── group_models.py         # Modelos de grupos Google
    │   │   └── org_unit_models.py      # Modelos de unidades organizativas
    │   │
    │   ├── payloads/
    │   │   ├── __init__.py
    │   │   ├── user_payloads.py        # Schemas request/response usuarios
    │   │   └── group_payloads.py       # Schemas request/response grupos
    │   │
    │   ├── controllers/
    │   │   ├── __init__.py
    │   │   ├── user_controller.py      # CRUD usuarios Google
    │   │   ├── group_controller.py     # CRUD grupos Google
    │   │   └── org_unit_controller.py  # Gestión de OUs
    │   │
    │   ├── services/
    │   │   ├── __init__.py
    │   │   ├── workspace_service.py    # Servicio principal de integración
    │   │   └── sync_service.py         # Servicio de sincronización
    │   │
    │   └── utils/
    │       ├── __init__.py
    │       ├── password_generator.py   # Generador de contraseñas seguras
    │       ├── email_validator.py      # Validador @ctcsalto.edu.uy
    │       └── retry_handler.py        # Manejo de reintentos API
    │
    └── (futuro)
        ├── gmail/
        ├── drive/
        └── classroom/
```

---

## Endpoints a Implementar

### Endpoints en `routes/google/workspace/workspace_users.py`

```python
# === CRUD Usuarios Google Workspace ===

POST   /google/workspace/users
# Crear usuario en Google Workspace manualmente
# Body: GoogleWorkspaceUserCreate
# Admin only

GET    /google/workspace/users
# Listar usuarios en Google Workspace
# Query params: orgUnitPath, suspended, limit, pageToken
# Admin only

GET    /google/workspace/users/{googleWorkspaceId}
# Obtener usuario específico de Google
# Admin only

PUT    /google/workspace/users/{googleWorkspaceId}
# Actualizar usuario en Google Workspace
# Body: GoogleWorkspaceUserUpdate
# Admin only

DELETE /google/workspace/users/{googleWorkspaceId}
# Eliminar usuario de Google Workspace (libera cupo)
# Admin only

PATCH  /google/workspace/users/{googleWorkspaceId}/suspend
# Suspender usuario (mantiene datos, libera licencia)
# Admin only

PATCH  /google/workspace/users/{googleWorkspaceId}/unsuspend
# Reactivar usuario suspendido
# Admin only

# === Sincronización ===

POST   /google/workspace/sync/users
# Sincronizar todos los usuarios locales con Google
# Admin only

POST   /google/workspace/sync/user/{userId}
# Sincronizar usuario específico local → Google
# Admin only

GET    /google/workspace/sync/status
# Estado de última sincronización
# Admin only

# === Gestión de Grupos ===

GET    /google/workspace/groups
# Listar grupos de Google Workspace
# Admin only

POST   /google/workspace/groups
# Crear grupo
# Body: GoogleWorkspaceGroupCreate
# Admin only

DELETE /google/workspace/groups/{groupEmail}
# Eliminar grupo
# Admin only

POST   /google/workspace/groups/{groupEmail}/members
# Agregar usuario a grupo
# Body: {userEmail: str}
# Admin only

DELETE /google/workspace/groups/{groupEmail}/members/{userEmail}
# Remover usuario de grupo
# Admin only

GET    /google/workspace/groups/{groupEmail}/members
# Listar miembros de un grupo
# Admin only

# === Unidades Organizativas ===

GET    /google/workspace/orgunits
# Listar todas las OUs
# Admin only

POST   /google/workspace/orgunits
# Crear OU (si no existe)
# Body: {name: str, parentOrgUnitPath: str}
# Admin only

# === Utilidades ===

POST   /google/workspace/validate-email
# Validar si email está disponible en Google
# Body: {email: str}
# Admin only

POST   /google/workspace/generate-password
# Generar contraseña temporal segura
# Returns: {password: str}
# Admin only
```

### Modificaciones a Endpoints Existentes en `routes/auth.py`

```python
# MODIFICAR: POST /auth/register
# Agregar integración automática con Google Workspace y Moodle

# MODIFICAR: PUT /auth/users/{userId}
# Agregar sincronización automática con Google Workspace

# MODIFICAR: DELETE /auth/users/{userId}
# Agregar eliminación en Google Workspace y Moodle

# MODIFICAR: POST /auth/deactivate/{userId}
# Agregar suspensión en Google Workspace

# MODIFICAR: POST /auth/activate/{userId}
# Agregar reactivación en Google Workspace
```

---

## Modelos y Payloads

### `external_services/google/workspace/models/user_models.py`

```python
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime

class GoogleWorkspaceName(BaseModel):
    """Nombre completo del usuario"""
    givenName: str = Field(..., description="Nombre")
    familyName: str = Field(..., description="Apellido")
    fullName: Optional[str] = None  # Auto-generado por Google

class GoogleWorkspaceUser(BaseModel):
    """Modelo completo de usuario de Google Workspace"""
    id: Optional[str] = None  # ID único de Google
    primaryEmail: EmailStr
    name: GoogleWorkspaceName
    password: Optional[str] = None  # Solo en creación
    hashFunction: Optional[str] = "SHA-1"  # Para contraseñas hasheadas
    changePasswordAtNextLogin: bool = True
    isAdmin: bool = False
    isDelegatedAdmin: bool = False
    suspended: bool = False
    orgUnitPath: str = "/Alumnos"  # Default
    customSchemas: Optional[Dict[str, Any]] = None
    creationTime: Optional[datetime] = None
    lastLoginTime: Optional[datetime] = None

class GoogleWorkspaceUserList(BaseModel):
    """Lista paginada de usuarios"""
    users: list[GoogleWorkspaceUser] = []
    nextPageToken: Optional[str] = None
```

### `external_services/google/workspace/payloads/user_payloads.py`

```python
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
import re

class GoogleWorkspaceUserCreate(BaseModel):
    """Payload para crear usuario en Google Workspace"""
    primaryEmail: EmailStr = Field(..., description="Email @ctcsalto.edu.uy")
    givenName: str = Field(..., min_length=1, max_length=50)
    familyName: str = Field(..., min_length=1, max_length=50)
    password: Optional[str] = None  # Si None, se genera automáticamente
    changePasswordAtNextLogin: bool = True
    isAdmin: bool = False
    orgUnitPath: str = Field(default="/Alumnos")

    @field_validator('primaryEmail')
    @classmethod
    def validate_email_domain(cls, v: str):
        if not v.endswith('@ctcsalto.edu.uy'):
            raise ValueError('El email debe ser del dominio @ctcsalto.edu.uy')
        return v

class GoogleWorkspaceUserUpdate(BaseModel):
    """Payload para actualizar usuario en Google Workspace"""
    givenName: Optional[str] = Field(None, min_length=1, max_length=50)
    familyName: Optional[str] = Field(None, min_length=1, max_length=50)
    password: Optional[str] = None
    suspended: Optional[bool] = None
    orgUnitPath: Optional[str] = None
    isAdmin: Optional[bool] = None

class SyncUserResponse(BaseModel):
    """Respuesta de sincronización de usuario"""
    userId: int
    email: str
    googleWorkspaceId: Optional[str]
    moodleUserId: Optional[int]
    status: str  # "created", "updated", "error", "skipped"
    message: str
    errors: Optional[list[str]] = None

class SyncAllUsersResponse(BaseModel):
    """Respuesta de sincronización masiva"""
    total_users: int
    created: int
    updated: int
    errors: int
    skipped: int
    results: list[SyncUserResponse]
```

---

## Configuración y Credenciales

### Variables de Entorno (.env)

```bash
# === Google Workspace API ===
GOOGLE_WORKSPACE_ADMIN_EMAIL=admin@ctcsalto.edu.uy
GOOGLE_WORKSPACE_CUSTOMER_ID=C01234567  # ID del dominio en Google Admin
GOOGLE_WORKSPACE_DOMAIN=ctcsalto.edu.uy

# Credenciales de Service Account (JSON)
GOOGLE_WORKSPACE_SERVICE_ACCOUNT_FILE=path/to/service-account-key.json
# O como variable de entorno (contenido del JSON codificado en base64)
GOOGLE_WORKSPACE_SERVICE_ACCOUNT_JSON=eyJ0eXBlIjogInNlcnZpY2...

# Scopes necesarios (predefinidos en config)
# https://www.googleapis.com/auth/admin.directory.user
# https://www.googleapis.com/auth/admin.directory.group
# https://www.googleapis.com/auth/admin.directory.orgunit
```

### `external_services/google/workspace/config/workspace_config.py`

```python
import os
import json
import base64
from dataclasses import dataclass
from typing import List

@dataclass
class GoogleWorkspaceConfig:
    """Configuración de Google Workspace API"""

    # Credenciales
    service_account_file: str
    service_account_info: dict  # Alternativa: cargar JSON desde env var
    admin_email: str
    customer_id: str
    domain: str

    # Scopes de API necesarios
    scopes: List[str] = None

    # Configuración de reintentos
    max_retries: int = 3
    retry_delay: int = 2  # segundos

    # Límites de cuotas
    max_users: int = 1000  # Límite de Google for Education (ajustar según plan)

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = [
                'https://www.googleapis.com/auth/admin.directory.user',
                'https://www.googleapis.com/auth/admin.directory.group',
                'https://www.googleapis.com/auth/admin.directory.orgunit',
                'https://www.googleapis.com/auth/admin.directory.userschema',
            ]

    @classmethod
    def from_env(cls):
        """Cargar configuración desde variables de entorno"""

        # Intentar cargar desde archivo
        service_account_file = os.getenv('GOOGLE_WORKSPACE_SERVICE_ACCOUNT_FILE')
        service_account_info = None

        # O desde variable de entorno (JSON base64)
        if not service_account_file:
            sa_json_b64 = os.getenv('GOOGLE_WORKSPACE_SERVICE_ACCOUNT_JSON')
            if sa_json_b64:
                sa_json = base64.b64decode(sa_json_b64).decode('utf-8')
                service_account_info = json.loads(sa_json)
        else:
            with open(service_account_file, 'r') as f:
                service_account_info = json.load(f)

        return cls(
            service_account_file=service_account_file,
            service_account_info=service_account_info,
            admin_email=os.getenv('GOOGLE_WORKSPACE_ADMIN_EMAIL'),
            customer_id=os.getenv('GOOGLE_WORKSPACE_CUSTOMER_ID'),
            domain=os.getenv('GOOGLE_WORKSPACE_DOMAIN', 'ctcsalto.edu.uy'),
        )
```

---

## Plan de Sincronización

### Estrategias de Sincronización

#### 1. Sincronización en Tiempo Real (Preferida)
- **Cuándo:** Cada vez que se crea/actualiza/elimina un usuario local
- **Ventajas:** Datos siempre actualizados, no requiere cron jobs
- **Desventajas:** Mayor carga en API de Google (límites de cuota)
- **Implementación:** Llamar a GoogleWorkspaceService directamente desde UserService

#### 2. Sincronización en Segundo Plano (Alternativa)
- **Cuándo:** Encolar tarea en Redis/Celery para procesamiento asíncrono
- **Ventajas:** No bloquea respuesta al usuario, maneja errores mejor
- **Desventajas:** Requiere infraestructura adicional (Celery, RabbitMQ)

#### 3. Sincronización Manual (Complementaria)
- **Cuándo:** Admin ejecuta desde panel de administración
- **Ventajas:** Control total, útil para migraciones masivas
- **Desventajas:** Requiere intervención manual

### Manejo de Conflictos

**Escenario 1: Usuario existe en Google pero no en DB local**
- Acción: Importar usuario a DB local (sincronización inversa)
- Estado: active=True, confirmed=True
- Notificar admin

**Escenario 2: Usuario existe en DB pero no en Google**
- Acción: Crear en Google
- Usar datos de DB local

**Escenario 3: Datos difieren entre DB y Google**
- Regla: **DB local es fuente de verdad**
- Acción: Actualizar Google con datos de DB
- Registrar en log

**Escenario 4: Usuario eliminado en Google pero activo en DB**
- Acción: Marcar googleWorkspaceId=null, googleSuspended=null
- Notificar admin para revisar

---

## Manejo de Errores y Rollback

### Estrategia de Rollback en Creación de Usuario

```python
async def create_user_with_integrations(user_data: UserCreate, session: Session):
    """Crear usuario en las 3 plataformas con rollback en caso de error"""

    local_user = None
    google_user = None
    moodle_user = None

    try:
        # 1. Crear en DB local
        local_user = user_service.create_user(user_data, session)

        # 2. Crear en Google Workspace
        try:
            google_user = workspace_service.create_workspace_user(
                email=local_user.email,
                given_name=local_user.name,
                family_name=local_user.lastname,
                org_unit_path=local_user.rol.default_org_unit.google_path
            )

            # Guardar ID de Google en DB
            user_service.update_google_workspace_id(
                local_user.userId,
                google_user['primaryEmail'],
                session
            )

        except Exception as e:
            # Rollback: eliminar usuario local
            user_service.delete_user(local_user.userId, session)
            raise ValueError(f"Error creando usuario en Google Workspace: {str(e)}")

        # 3. Crear en Moodle
        try:
            moodle_user = moodle_service.create_moodle_user(
                username=local_user.email.split('@')[0],
                firstname=local_user.name,
                lastname=local_user.lastname,
                email=local_user.email,
                auth='google'
            )

            # Guardar ID de Moodle en DB
            user_service.update_moodle_user_id(
                local_user.userId,
                moodle_user['id'],
                session
            )

        except Exception as e:
            # Rollback: eliminar usuario de Google y local
            workspace_service.delete_workspace_user(google_user['id'])
            user_service.delete_user(local_user.userId, session)
            raise ValueError(f"Error creando usuario en Moodle: {str(e)}")

        return {
            "local_user": local_user,
            "google_user": google_user,
            "moodle_user": moodle_user
        }

    except Exception as e:
        # Log del error completo
        logger.error(f"Error en creación de usuario: {str(e)}")
        raise
```

### Códigos de Error de Google Workspace API

| Código | Descripción | Acción |
|--------|-------------|--------|
| 400 | Bad Request | Validar datos antes de enviar |
| 401 | Unauthorized | Revisar credenciales de Service Account |
| 403 | Forbidden | Verificar permisos de Service Account |
| 404 | Not Found | Usuario/grupo no existe |
| 409 | Conflict | Email ya existe, usar otro |
| 429 | Too Many Requests | Implementar rate limiting y backoff |
| 500 | Internal Server Error | Reintentar después de delay |

---

## Consideraciones de Seguridad

### 1. Autenticación de Service Account
- **Usar Service Account con OAuth 2.0**
- **Delegar autoridad** al admin principal (Domain-Wide Delegation)
- **Rotación de claves** cada 90 días
- **Almacenar credenciales** como secretos (no en código)

### 2. Scopes Mínimos Necesarios
```python
REQUIRED_SCOPES = [
    'https://www.googleapis.com/auth/admin.directory.user',       # Gestión de usuarios
    'https://www.googleapis.com/auth/admin.directory.group',      # Gestión de grupos
    'https://www.googleapis.com/auth/admin.directory.orgunit',    # Gestión de OUs
]
```

### 3. Validación de Emails
- **Solo permitir** emails @ctcsalto.edu.uy
- **Prevenir** email spoofing
- **Verificar disponibilidad** antes de crear

### 4. Generación de Contraseñas Temporales
```python
# Criterios:
- Longitud: 16 caracteres
- Complejidad: mayúsculas, minúsculas, números, caracteres especiales
- Sin caracteres ambiguos (0, O, l, 1)
- Única por usuario
- Almacenada solo temporalmente (no en DB)
- Enviar por canal seguro (email institucional)
```

### 5. Rate Limiting
- **Límites de cuota de Google Workspace:**
  - 1,500 requests/minute/user (pooled)
  - Implementar exponential backoff

### 6. Logs de Auditoría
- **Registrar todas las operaciones:**
  - Creación de usuarios
  - Modificaciones
  - Eliminaciones
  - Cambios de permisos
- **Incluir:**
  - Timestamp
  - Admin que ejecutó la acción
  - Datos antes/después

---

## Plan de Migración de Datos

### Usuarios Existentes sin Cuenta Google

```python
# Script de migración: scripts/migrate_users_to_google.py

async def migrate_existing_users():
    """Migrar usuarios existentes a Google Workspace"""

    # 1. Obtener todos los usuarios activos sin googleWorkspaceId
    users = session.exec(
        select(User).where(
            User.active == True,
            User.googleWorkspaceId == None
        )
    ).all()

    results = {
        "total": len(users),
        "created": 0,
        "errors": [],
    }

    for user in users:
        try:
            # 2. Crear cuenta de Google
            google_user = workspace_service.create_workspace_user(
                email=user.email,
                given_name=user.name,
                family_name=user.lastname,
                org_unit_path=user.rol.default_org_unit.google_path,
                send_welcome_email=False  # No enviar email masivo
            )

            # 3. Actualizar DB
            user.googleWorkspaceId = google_user['primaryEmail']
            user.googleOrgUnitPath = google_user['orgUnitPath']
            user.googleCreatedAt = datetime.now()
            user.googleLastSync = datetime.now()
            session.commit()

            results["created"] += 1

        except Exception as e:
            results["errors"].append({
                "userId": user.userId,
                "email": user.email,
                "error": str(e)
            })

    return results
```

---

## Testing

### Tests Unitarios

```python
# tests/test_google_workspace_service.py

def test_create_workspace_user():
    """Test creación de usuario en Google Workspace"""
    user_data = {
        "primaryEmail": "test@ctcsalto.edu.uy",
        "givenName": "Test",
        "familyName": "User",
        "orgUnitPath": "/Alumnos"
    }
    result = workspace_service.create_workspace_user(**user_data)
    assert result['primaryEmail'] == user_data['primaryEmail']

def test_password_generation():
    """Test generador de contraseñas"""
    password = generate_secure_password()
    assert len(password) == 16
    assert any(c.isupper() for c in password)
    assert any(c.islower() for c in password)
    assert any(c.isdigit() for c in password)
    assert any(c in '@.*$!' for c in password)

def test_email_validation():
    """Test validación de emails @ctcsalto.edu.uy"""
    assert validate_ctc_email("user@ctcsalto.edu.uy") == True
    assert validate_ctc_email("user@gmail.com") == False
```

### Tests de Integración

```python
# tests/integration/test_user_creation_flow.py

@pytest.mark.integration
async def test_full_user_creation_flow():
    """Test flujo completo: DB → Google → Moodle"""
    user_data = UserCreate(
        email="integration-test@ctcsalto.edu.uy",
        name="Integration",
        lastname="Test",
        phone="123456789",
        document="12345678",
        password="TestPass123@",
        rol=UserRole.STUDENT
    )

    # Crear usuario
    result = await create_user_with_integrations(user_data, session)

    # Verificar DB local
    assert result['local_user'].userId is not None

    # Verificar Google
    assert result['google_user']['primaryEmail'] == user_data.email

    # Verificar Moodle
    assert result['moodle_user']['id'] is not None

    # Cleanup
    workspace_service.delete_workspace_user(result['google_user']['id'])
    moodle_service.delete_moodle_user(result['moodle_user']['id'])
    user_service.delete_user(result['local_user'].userId, session)
```

---

## Roadmap de Implementación

### Fase 1: Configuración Inicial (Semana 1)
- [ ] Obtener credenciales de Service Account de Google Workspace
- [ ] Configurar Domain-Wide Delegation
- [ ] Crear Unidades Organizativas en Google Admin
- [ ] Crear grupos principales en Google Workspace
- [ ] Configurar variables de entorno
- [ ] Instalar dependencias: `google-auth`, `google-api-python-client`

### Fase 2: Modelos y Configuración (Semana 1-2)
- [ ] Crear migración Alembic para nuevos campos User
- [ ] Actualizar modelo User con campos Google/Moodle
- [ ] Crear enums OrganizationalUnit y actualizar UserRole
- [ ] Implementar GoogleWorkspaceConfig
- [ ] Implementar modelos y payloads de Google Workspace

### Fase 3: Servicios Core (Semana 2-3)
- [ ] Implementar GoogleWorkspaceUserController (CRUD)
- [ ] Implementar GoogleWorkspaceGroupController (CRUD)
- [ ] Implementar GoogleWorkspaceService (servicio principal)
- [ ] Implementar generador de contraseñas seguras
- [ ] Implementar validador de emails @ctcsalto.edu.uy
- [ ] Implementar retry handler para API calls

### Fase 4: Integración con UserService (Semana 3-4)
- [ ] Modificar UserService.create_user() para crear en Google
- [ ] Modificar UserService.update_user() para sincronizar con Google
- [ ] Modificar UserService.delete_user() para eliminar de Google
- [ ] Implementar rollback en caso de errores
- [ ] Actualizar endpoints de auth.py

### Fase 5: Sincronización (Semana 4)
- [ ] Implementar SyncService para sincronización manual
- [ ] Crear endpoints de sincronización
- [ ] Implementar manejo de conflictos
- [ ] Crear script de migración de usuarios existentes

### Fase 6: Integración con Moodle (Semana 5)
- [ ] Verificar/actualizar integración Moodle existente
- [ ] Asegurar que Moodle use auth='google'
- [ ] Sincronizar creación/eliminación con Google Workspace
- [ ] Testing de flujo completo

### Fase 7: Testing y Documentación (Semana 5-6)
- [ ] Tests unitarios de todos los servicios
- [ ] Tests de integración de flujos completos
- [ ] Actualizar ARCHITECTURE.md con integración Google
- [ ] Documentar API en Scalar/OpenAPI
- [ ] Crear guía de uso para admins

### Fase 8: Despliegue y Migración (Semana 6)
- [ ] Deploy a entorno de staging
- [ ] Ejecutar migración de usuarios existentes
- [ ] Validar sincronización en producción
- [ ] Capacitación a administradores
- [ ] Deploy a producción

---

## Dependencias Adicionales a Instalar

```bash
# requirements.txt (agregar)

# Google Workspace Admin SDK
google-auth==2.23.0
google-auth-oauthlib==1.1.0
google-auth-httplib2==0.1.1
google-api-python-client==2.108.0

# Utilidades
secrets  # Generador de contraseñas seguras (built-in Python 3.6+)
```

---

## Notas Importantes

### Límites de Google Workspace API
- **1,500 requests/minute** por proyecto
- **5 users creados por segundo**
- **Implementar exponential backoff** para 429 (Too Many Requests)

### Cuotas de Google for Education
- Verificar límite de usuarios con Google (varía según plan)
- Implementar monitoreo de cuotas usadas vs disponibles
- Alertar cuando se acerque al límite

### Compliance GDPR/Protección de Datos
- Obtener consentimiento explícito para crear cuentas Google
- Política de retención de datos (cuánto tiempo mantener usuarios inactivos)
- Derecho al olvido: eliminar completamente usuarios que lo soliciten

### Backup y Recuperación
- Google Workspace tiene backup automático (Vault)
- Mantener backup local de mapeo userId ↔ googleWorkspaceId
- Plan de recuperación ante desastre

---

## Próximos Pasos

1. **Revisar y aprobar esta planificación**
2. **Obtener credenciales de Google Workspace**
3. **Configurar Service Account con permisos necesarios**
4. **Crear Unidades Organizativas en Google Admin Console**
5. **Comenzar Fase 1 del Roadmap**

---

## Referencias

- [Google Workspace Admin SDK - Directory API](https://developers.google.com/admin-sdk/directory/v1/guides)
- [Google Workspace for Education](https://edu.google.com/workspace-for-education/)
- [Service Accounts - Domain-Wide Delegation](https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority)
- [Admin SDK User Resource](https://developers.google.com/admin-sdk/directory/reference/rest/v1/users)
- [Admin SDK Group Resource](https://developers.google.com/admin-sdk/directory/reference/rest/v1/groups)

---

**Documento de Planificación - Google Workspace API Integration**
**Versión:** 1.0
**Autor:** Planificación Automatizada
**Última Actualización:** 2025-12-28
