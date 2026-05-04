# Portal Institucional CTC - v2

## Planificación Técnica

**Fecha:** Marzo 2026
**Rama:** `bedelia`

---

## 1. Autenticación con Google OAuth 2.0

### 1.1 ¿Qué devuelve Google al hacer login?

Al autenticarse con Google OAuth 2.0, el ID token/userinfo devuelve:

```json
{
  "sub": "1102547839012345",      // ID único de Google (permanente)
  "email": "nombre.apellido@ctcsalto.edu.uy",
  "name": "Nombre Apellido",
  "given_name": "Nombre",
  "family_name": "Apellido",
  "picture": "https://lh3.googleusercontent.com/...",
  "verified_email": true,
  "hd": "ctcsalto.edu.uy",        // Dominio hospedado (solo Workspace)
  "locale": "es"
}
```

**Importante:**
- `hd` (hosted domain) confirma que es una cuenta @ctcsalto.edu.uy
- `sub` es el ID permanente de Google del usuario (no cambia aunque cambie el email)
- **NO devuelve** la Unidad Organizativa (OU). Para obtener la OU necesitamos el Admin SDK.

### 1.2 Flujo de autenticación propuesto

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Frontend │────►│ Google OAuth  │────►│ Backend      │────►│ n8n          │
│ (click   │     │ Login con    │     │ Recibe code, │     │ Consulta OU  │
│ "Entrar  │     │ cuenta       │     │ valida hd=   │     │ vía Admin    │
│ con      │     │ institucional│     │ ctcsalto,    │     │ SDK de Google│
│ Google") │     │              │     │ obtiene user │     │              │
└──────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                             │
                                             ▼
                                     ┌──────────────┐
                                     │ PostgreSQL   │
                                     │ Busca/crea   │
                                     │ usuario,     │
                                     │ genera JWT   │
                                     │ con rol      │
                                     └──────────────┘
```

**Paso a paso:**

1. Frontend redirige a Google OAuth con `hd=ctcsalto.edu.uy` (restringe dominio en UI)
2. Usuario se autentica con su cuenta institucional
3. Google redirige al backend con un `code`
4. Backend intercambia `code` por `access_token` + `id_token`
5. Backend valida que `hd == "ctcsalto.edu.uy"` (seguridad obligatoria)
6. Backend consulta **n8n** para obtener la OU del usuario (n8n tiene acceso al Admin SDK de Google)
7. Backend busca al usuario en la BD local (por `google_id` o `email`):
   - Si existe: actualiza `last_access`, re-sincroniza rol si cambió de OU, genera JWT
   - Si no existe: crea usuario con rol basado en OU, genera JWT
8. Frontend recibe JWT y lo usa para todas las peticiones

### 1.3 Obtener OU vía n8n

**No tenemos Service Account propia** (plan gratuito de Google for Education), pero **n8n sí tiene acceso al Admin SDK** de Google Workspace. Esto nos permite crear un workflow en n8n que reciba un email y devuelva la OU:

```
Backend                          n8n                         Google Admin SDK
   │                              │                              │
   │  GET /google-user-ou         │                              │
   │  ?email=nombre@ctcsalto...   │                              │
   │─────────────────────────────►│                              │
   │                              │  GET /admin/directory/v1/    │
   │                              │  users/{email}               │
   │                              │─────────────────────────────►│
   │                              │                              │
   │                              │◄─ orgUnitPath: "/Alumnos"   │
   │◄─ { "ou": "/Alumnos" }      │                              │
   │                              │                              │
```

### 1.4 Mapeo OU → Rol del sistema

| OU de Google | Rol en el sistema | Permisos |
|---|---|---|
| `/Alumnos` | `ESTUDIANTE` | Ver sus notas, inscribirse a materias/exámenes |
| `/Equipo Docente` | `DOCENTE` | Cargar notas, ver alumnos de sus materias |
| `/Administración y Ventas` | `ADMINISTRATIVO` | Gestionar todo: períodos, materias, previaturas, etc. |

**Ventajas de este enfoque (n8n + OU):**
- **Confiable**: la OU en Google es la fuente de verdad real del rol
- **Cubre todos los roles**: incluido ADMINISTRATIVO (que no se podía detectar solo con Moodle)
- **Re-sync automático**: en cada login se verifica si cambió de OU y se actualiza el rol
- **Simple**: una sola llamada a n8n, sin inferir roles desde Moodle

---

## 2. Modelo de Datos

### 2.1 Diagrama de Relaciones

```
┌─────────────────┐         ┌──────────────────────┐
│    usuario       │         │     programa          │
│─────────────────│         │──────────────────────│
│ id              │         │ id                    │
│ google_id       │         │ nombre                │
│ moodle_id       │         │ tipo                  │
│ email           │         │ moodle_category_id    │
│ nombre          │         │ activo                │
│ apellido        │         └──────────┬───────────┘
│ foto_url        │                    │
│ rol             │                    │ 1:N
│ activo          │                    │
│ fecha_creacion  │         ┌──────────▼───────────┐
│ ultimo_acceso   │         │     materia           │
└────────┬────────┘         │──────────────────────│
         │                  │ id                    │
         │                  │ programa_id (FK)      │
         │                  │ nombre                │
         │                  │ moodle_course_id      │
         │                  │ semestre              │
         │                  │ creditos              │
         │                  │ politica_id (FK)      │
         │                  │ activo                │
         │                  └──┬────────┬──────────┘
         │                     │        │
         │            ┌────────┘        └────────┐
         │            │ 1:N                 N:M  │
         │            │                          │
         │  ┌─────────▼──────────┐    ┌──────────▼──────────┐
         │  │ materia_instancia  │    │   previatura         │
         │  │   _evaluacion      │    │──────────────────────│
         │  │────────────────────│    │ materia_id (FK)      │
         │  │ id                 │    │ materia_previa_id FK │
         │  │ materia_id (FK)    │    │ tipo_requerido       │
         │  │ nombre             │    └──────────────────────┘
         │  │ peso_maximo        │
         │  │ orden              │
         │  │ es_grupal          │
         │  │ anio_lectivo       │
         │  └────────┬───────────┘
         │           │
         │           │ 1:N
         │           │
         │  ┌────────▼───────────────────────┐
         │  │  inscripcion_materia            │
         │  │────────────────────────────────│
         │  │ id                             │
         │  │ usuario_id (FK)                │◄──────────┐
         │  │ materia_id (FK)                │           │
         │  │ anio_lectivo                   │           │
         │  │ estado                         │           │
         │  │   CURSANDO | EXONERADO         │           │
         │  │   A_EXAMEN | APROBADO          │           │
         │  │   REPROBADO                    │           │
         │  │   PERDIDO_INASISTENCIA         │           │
         │  │   ABANDONO                     │           │
         │  │ nota_curso (calculada)         │           │
         │  │ nota_final                     │           │
         │  │ creditos_obtenidos             │           │
         │  │ snapshot_politica (JSONB)      │           │
         │  │ snapshot_instancias (JSONB)    │           │
         │  └────────┬──────────────────────┘           │
         │           │                                   │
         │           │ 1:N                               │
         │           │                                   │
         │  ┌────────▼───────────────────────┐           │
         │  │  calificacion                   │           │
         │  │────────────────────────────────│           │
         │  │ id                             │           │
         │  │ inscripcion_id (FK)            │           │
         │  │ instancia_evaluacion_id (FK)   │           │
         │  │ nota                           │           │
         │  │ equipo_id (FK, nullable)       │           │
         │  │ docente_id (FK)                │           │
         │  │ fecha                          │           │
         │  └────────────────────────────────┘           │
         │                                               │
         │                                               │
         │  ┌────────────────────────────────┐           │
         │  │  periodo_examen                 │           │
         │  │────────────────────────────────│           │
         │  │ id                             │           │
         │  │ nombre                         │           │
         │  │ fecha_inicio_inscripcion       │           │
         │  │ fecha_fin_inscripcion          │           │
         │  │ fecha_consulta                 │           │
         │  │ fecha_examen                   │           │
         │  │ habilitado                     │           │
         │  └────────┬──────────────────────┘           │
         │           │                                   │
         │           │ 1:N                               │
         │           │                                   │
         │  ┌────────▼───────────────────────┐           │
         │  │  inscripcion_examen             │           │
         │  │────────────────────────────────│           │
         │  │ id                             │           │
         │  │ inscripcion_materia_id (FK) ───┼───────────┘
         │  │ periodo_examen_id (FK)         │
         │  │ fecha_inscripcion              │
         │  │ nota_examen                    │
         │  │ estado                         │
         │  │ snapshot_politica_examen JSONB │
         │  └────────────────────────────────┘
         │
         │
         │  ┌────────────────────────────────┐
         │  │  equipo                         │
         │  │────────────────────────────────│
         │  │ id                             │
         │  │ instancia_evaluacion_id (FK)   │
         │  │ nombre                         │
         │  └────────┬──────────────────────┘
         │           │
         │           │ N:M
         │           │
         │  ┌────────▼───────────────────────┐
         │  │  equipo_miembro                 │
         │  │────────────────────────────────│
         │  │ equipo_id (FK)                 │
         │  │ usuario_id (FK)                │
         │  └────────────────────────────────┘


     Tablas de configuración (independientes):

┌──────────────────────────┐     ┌──────────────────────────────┐
│  politica_calificacion    │     │  periodo_inscripcion_materia  │
│──────────────────────────│     │──────────────────────────────│
│ id                        │     │ id                            │
│ nombre                    │     │ programa_id (FK)              │
│ descripcion               │     │ anio_lectivo                  │
│ nota_maxima               │     │ fecha_inicio                  │
│ tipo_nota                 │     │ fecha_fin                     │
│ umbral_aprobacion         │     │ habilitado                    │
│ umbral_examen (nullable)  │     └──────────────────────────────┘
│ umbral_exoneracion (null) │
│ activo                    │
└──────────────────────────┘

┌──────────────────────────┐
│  politica_examen          │
│──────────────────────────│
│ id                        │
│ nombre                    │
│ nota_maxima               │
│ umbral_aprobacion         │
│ activo                    │
└──────────────────────────┘

┌──────────────────────────┐
│  docente_materia          │
│──────────────────────────│
│ docente_id (FK usuario)   │
│ materia_id (FK)           │
│ anio_lectivo              │
│ rol (TITULAR|ADJUNTO)     │
└──────────────────────────┘
```

### 2.2 Detalle de cada tabla

#### `usuario`
Central del sistema. Vincula Google + Moodle + datos locales.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK, autoincrement | ID interno del sistema |
| `google_id` | String, unique, nullable | `sub` del ID token de Google (permanente) |
| `moodle_id` | Integer, unique, nullable | ID del usuario en Moodle |
| `email` | String, unique, indexed | Email institucional |
| `nombre` | String(100) | Nombre del usuario |
| `apellido` | String(100) | Apellido del usuario |
| `foto_url` | String, nullable | URL de la foto de Google |
| `documento` | String, nullable | Cédula/documento |
| `telefono` | String, nullable | Para notificaciones WhatsApp |
| `rol` | Enum | `ESTUDIANTE`, `DOCENTE`, `ADMINISTRATIVO` |
| `ou_google` | String, nullable | Última OU conocida (ej: "/Alumnos") |
| `activo` | Boolean | Si el usuario tiene acceso al sistema |
| `google_activo` | Boolean | Si la cuenta de Google sigue existiendo |
| `moodle_activo` | Boolean | Si la cuenta de Moodle sigue existiendo |
| `fecha_creacion` | DateTime | Primer login |
| `ultimo_acceso` | DateTime, nullable | Último login |

**Sobre el histórico:** Cuando se borra la cuenta de Google/Moodle, se marca `google_activo = false` / `moodle_activo = false` pero **el usuario y toda su escolaridad se mantienen**. El `google_id` y `moodle_id` quedan como referencia histórica.

---

#### `programa`
Carreras, cursos cortos, diplomas. Se sincroniza con categorías de Moodle.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK | |
| `nombre` | String(150) | "Analista Programador", "Marketing Digital" |
| `tipo` | Enum | `CARRERA`, `CURSO_CORTO`, `TALLER`, `DIPLOMA` |
| `moodle_category_id` | Integer, nullable | Categoría correspondiente en Moodle |
| `descripcion` | Text, nullable | |
| `duracion_semestres` | Integer, nullable | Solo para carreras |
| `activo` | Boolean | |
| `fecha_creacion` | DateTime | |

---

#### `politica_calificacion`
Define las reglas de evaluación. Flexible para cambios futuros.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK | |
| `nombre` | String(100) | "Base 100 - Carrera", "Base 12 - Nuevo sistema" |
| `descripcion` | Text, nullable | Explicación de la política |
| `nota_maxima` | Decimal | 100, 12, etc. |
| `tipo_nota` | Enum | `NUMERICA`, `LETRA`, `ESCALA_CUSTOM` |
| `umbral_aprobacion` | Decimal | 70 (aprueba directo en cursos cortos) |
| `umbral_examen` | Decimal, nullable | 70 (mínimo para derecho a examen, null si no aplica) |
| `umbral_exoneracion` | Decimal, nullable | 86 (exonera sin examen, null si no aplica) |
| `activo` | Boolean | |
| `fecha_creacion` | DateTime | |

**Ejemplos de políticas:**

| Nombre | Máx | Aprobación | Examen | Exoneración |
|---|---|---|---|---|
| "Base 100 - Carrera AP" | 100 | 70 | 70 | 86 |
| "Base 100 - Curso Corto" | 100 | 70 | null | null |
| "Base 12 - Futuro" | 12 | 8 | 8 | 10 |
| "Letras A-F" | null | "C" | null | null |

**Lógica de la política:**
```
Si tiene umbral_exoneracion:
  nota >= umbral_exoneracion → EXONERADO (aprueba)
  nota >= umbral_examen → A_EXAMEN (derecho a examen)
  nota < umbral_examen → REPROBADO

Si NO tiene umbral_exoneracion ni umbral_examen:
  nota >= umbral_aprobacion → APROBADO
  nota < umbral_aprobacion → REPROBADO

Casos especiales (independientes de la nota):
  Inasistencias excesivas → PERDIDO_INASISTENCIA
  Abandono / baja voluntaria → ABANDONO
```

---

#### `politica_examen`
Políticas de aprobación de examen (separada porque puede cambiar independientemente).

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK | |
| `nombre` | String(100) | "Examen estándar base 100" |
| `nota_maxima` | Decimal | 100 |
| `umbral_aprobacion` | Decimal | 70 |
| `activo` | Boolean | |

---

#### `materia`
Cada asignatura dentro de un programa. Vinculada a un curso de Moodle.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK | |
| `programa_id` | Integer, FK → programa | |
| `nombre` | String(150) | "Programación 1", "Base de Datos" |
| `codigo` | String(20), unique, nullable | "PROG1", "BD1" (código corto) |
| `moodle_course_id` | Integer, nullable | Curso en Moodle |
| `semestre` | Integer | Semestre en la carrera (1, 2, 3...) |
| `creditos` | Integer | Créditos de la materia |
| `politica_id` | Integer, FK → politica_calificacion | Política vigente |
| `politica_examen_id` | Integer, FK → politica_examen, nullable | |
| `activo` | Boolean | |

---

#### `materia_instancia_evaluacion`
Las instancias de evaluación de cada materia (parcial 1, obligatorio, etc.). **Por año lectivo** para mantener el histórico.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK | |
| `materia_id` | Integer, FK → materia | |
| `nombre` | String(100) | "Primer Parcial", "Proyecto Obligatorio" |
| `peso_maximo` | Decimal | 15, 30, 40, 15... (la suma debe ≤ nota_maxima de la política) |
| `orden` | Integer | Orden de visualización (1, 2, 3, 4) |
| `es_grupal` | Boolean | Si permite evaluación en equipo |
| `anio_lectivo` | Integer | 2026, 2027... |
| `activo` | Boolean | |

**Ejemplo para AP 2026:**

| materia_id | nombre | peso_maximo | orden | es_grupal | anio_lectivo |
|---|---|---|---|---|---|
| 1 | Primer Parcial | 15 | 1 | false | 2026 |
| 1 | Segundo Parcial | 30 | 2 | false | 2026 |
| 1 | Proyecto Obligatorio | 40 | 3 | true | 2026 |
| 1 | Valoración Docente | 15 | 4 | false | 2026 |

**Sobre el histórico:** Si en 2027 cambian las instancias, se crean nuevas con `anio_lectivo = 2027`. Las de 2026 permanecen intactas y las calificaciones de 2026 siguen referenciando a sus instancias de 2026.

---

#### `previatura`
Relaciones de prerequisitos entre materias.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK | |
| `materia_id` | Integer, FK → materia | La materia que tiene el requisito |
| `materia_previa_id` | Integer, FK → materia | La materia que es prerequisito |
| `tipo_requerido` | Enum | `APROBADA` (examen o exoneración), `EXONERADA` (solo exoneración) |

---

#### `inscripcion_materia`
Registro académico por alumno/materia/año. **Tabla central del sistema.**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK | |
| `usuario_id` | Integer, FK → usuario | |
| `materia_id` | Integer, FK → materia | |
| `anio_lectivo` | Integer | 2026 |
| `estado` | Enum | `CURSANDO`, `EXONERADO`, `A_EXAMEN`, `APROBADO`, `REPROBADO`, `PERDIDO_INASISTENCIA`, `ABANDONO` |
| `nota_curso` | Decimal, nullable | Suma de calificaciones de instancias |
| `nota_final` | Decimal, nullable | Nota definitiva (puede ser nota examen) |
| `creditos_obtenidos` | Integer, default 0 | creditos de la materia si aprobó, sino 0 |
| `snapshot_politica` | JSONB | Copia de la política al momento de cursar |
| `snapshot_instancias` | JSONB | Copia de las instancias y pesos al momento de cursar |
| `fecha_inscripcion` | DateTime | |
| `fecha_cierre` | DateTime, nullable | Cuando se determinó el estado final |
| `motivo_cierre` | String, nullable | Motivo para PERDIDO_INASISTENCIA o ABANDONO |

**Estados posibles:**

| Estado | Significado | Créditos |
|---|---|---|
| `CURSANDO` | Activo en el curso | - |
| `EXONERADO` | Nota >= umbral exoneración | Sí |
| `A_EXAMEN` | Nota entre umbral_examen y umbral_exoneración | - |
| `APROBADO` | Aprobó (examen o directo en curso corto) | Sí |
| `REPROBADO` | Nota < umbral mínimo | No |
| `PERDIDO_INASISTENCIA` | Perdió por exceso de faltas | No |
| `ABANDONO` | Dejó de asistir / se dio de baja | No |

**Sobre PERDIDO_INASISTENCIA y ABANDONO:**
- El docente o admin marca manualmente al alumno desde el portal
- Las asistencias se gestionan desde el plugin Attendance de Moodle (futuro)
- Estos estados son independientes de la nota: aunque tenga buenas calificaciones, si pierde por faltas queda como PERDIDO_INASISTENCIA
- En ambos casos, el alumno no obtiene créditos y la materia queda en su escolaridad con ese estado

**Sobre los snapshots JSONB:**

El `snapshot_politica` guarda la política que aplicaba cuando el alumno cursó:
```json
{
  "politica_id": 1,
  "nombre": "Base 100 - Carrera AP",
  "nota_maxima": 100,
  "umbral_aprobacion": 70,
  "umbral_examen": 70,
  "umbral_exoneracion": 86
}
```

El `snapshot_instancias` guarda las instancias con las que fue evaluado:
```json
[
  {"id": 1, "nombre": "Primer Parcial", "peso_maximo": 15, "orden": 1},
  {"id": 2, "nombre": "Segundo Parcial", "peso_maximo": 30, "orden": 2},
  {"id": 3, "nombre": "Proyecto Obligatorio", "peso_maximo": 40, "orden": 3},
  {"id": 4, "nombre": "Valoración Docente", "peso_maximo": 15, "orden": 4}
]
```

**¿Por qué snapshots y no solo FKs?** Porque si mañana cambia la política o las instancias, el registro histórico del alumno debe reflejar cómo fue evaluado en su momento. Los FKs apuntan a la versión vigente; los snapshots preservan el contexto histórico.

---

#### `calificacion`
Notas individuales por instancia de evaluación.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK | |
| `inscripcion_id` | Integer, FK → inscripcion_materia | |
| `instancia_evaluacion_id` | Integer, FK → materia_instancia_evaluacion | |
| `nota` | Decimal | Nota obtenida (dentro del peso_maximo de la instancia) |
| `equipo_id` | Integer, FK → equipo, nullable | Si es evaluación grupal |
| `docente_id` | Integer, FK → usuario | Quién puso la nota |
| `fecha` | DateTime | Cuándo se cargó |
| `observaciones` | Text, nullable | Comentarios del docente |

**Nota:** Aunque la evaluación sea grupal, cada miembro tiene su propio registro de calificación (porque pueden tener notas diferentes).

---

#### `equipo` y `equipo_miembro`
Para evaluaciones grupales (obligatorios).

**equipo:**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK | |
| `instancia_evaluacion_id` | Integer, FK | La instancia grupal |
| `nombre` | String(100) | "Equipo 1", "Grupo A" |

**equipo_miembro:**

| Campo | Tipo | Descripción |
|---|---|---|
| `equipo_id` | Integer, FK → equipo | |
| `usuario_id` | Integer, FK → usuario | |

---

#### `periodo_inscripcion_materia`
Períodos donde los admins habilitan inscripción a materias.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK | |
| `programa_id` | Integer, FK → programa | |
| `anio_lectivo` | Integer | 2026 |
| `semestre` | Integer, nullable | Si aplica por semestre |
| `fecha_inicio` | DateTime | |
| `fecha_fin` | DateTime | |
| `habilitado` | Boolean | Control manual del admin |

---

#### `periodo_examen`
Períodos de exámenes.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK | |
| `nombre` | String(100) | "Febrero 2026", "Julio 2026" |
| `fecha_inicio_inscripcion` | DateTime | |
| `fecha_fin_inscripcion` | DateTime | |
| `fecha_consulta` | DateTime, nullable | Clase de consulta previa |
| `fecha_examen` | DateTime | Fecha de la prueba |
| `habilitado` | Boolean | Control manual |

---

#### `inscripcion_examen`
Alumnos inscriptos a exámenes.

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer, PK | |
| `inscripcion_materia_id` | Integer, FK → inscripcion_materia | |
| `periodo_examen_id` | Integer, FK → periodo_examen | |
| `fecha_inscripcion` | DateTime | |
| `nota_examen` | Decimal, nullable | |
| `estado` | Enum | `INSCRIPTO`, `APROBADO`, `REPROBADO`, `AUSENTE` |
| `snapshot_politica_examen` | JSONB | Política de examen que aplicaba |

---

#### `docente_materia`
Vincula docentes a materias por año lectivo.

| Campo | Tipo | Descripción |
|---|---|---|
| `docente_id` | Integer, FK → usuario | |
| `materia_id` | Integer, FK → materia | |
| `anio_lectivo` | Integer | |
| `rol_docente` | Enum | `TITULAR`, `ADJUNTO`, `ASISTENTE` |

---

## 3. Integración con Moodle

### 3.1 Lo que ya tenemos

| Función | Estado |
|---|---|
| CRUD usuarios | Implementado |
| CRUD cursos | Implementado |
| CRUD categorías | Implementado |
| Inscripción/desinscripción | Implementado |
| Listar inscriptos | Implementado |
| **Calificaciones** | **NO necesario** (nuestro sistema es el principal) |

### 3.2 Funciones de Moodle que usaremos

| Función | Uso |
|---|---|
| `core_user_get_users_by_field` | Buscar usuario por email al hacer login (obtener moodle_id) |
| `core_enrol_get_users_courses` | Saber en qué cursos está un usuario |
| `core_course_get_courses` | Sincronizar cursos → materias |
| `core_course_get_categories` | Sincronizar categorías → programas |
| `enrol_manual_enrol_users` | Inscribir alumno en Moodle cuando se inscribe en nuestro portal |
| `enrol_manual_unenrol_users` | Desinscribir si es necesario |
| `core_enrol_get_enrolled_users` | Listar alumnos de un curso |

### 3.3 Funciones de Moodle que NO usaremos

| Función | Por qué no |
|---|---|
| `gradereport_user_get_grade_items` | Lee notas de Moodle. Las notas se gestionan en nuestro portal. |
| `core_grades_update_grades` | Escribe notas a Moodle. Moodle no es nuestro sistema de calificaciones. |

**Decisión:** Moodle se usa para **gestión de cursos e inscripciones**. Las **calificaciones viven exclusivamente en nuestro sistema**.

### 3.4 Sincronización con Moodle

```
Servicio de Sincronización
│
├── Sync Categorías (manual por admin)
│   Moodle categorías → verificar que nuestros programas coincidan
│
├── Sync Cursos (manual por admin)
│   Moodle cursos por categoría → verificar que nuestras materias coincidan
│
└── Sync al inscribir materia (en tiempo real)
    Alumno se inscribe en nuestro portal
    → Validar previaturas (lógica local)
    → Si pasa: inscribir en Moodle via enrol_manual_enrol_users
    → Si falla: informar qué materias le faltan
```

### 3.5 Flujo de inscripción a materia

```
Alumno quiere inscribirse a "Programación 2"
│
├── 1. ¿Está en período de inscripción habilitado? → NO: rechazar
│
├── 2. Obtener previaturas de Prog 2
│       → Requiere: Prog 1 (APROBADA)
│
├── 3. Verificar inscripcion_materia del alumno en Prog 1
│       → ¿estado = EXONERADO o APROBADO? → SI: continuar
│       → NO: rechazar, informar "Debe aprobar Prog 1"
│
├── 4. Crear inscripcion_materia local
│       estado = CURSANDO
│       snapshot_politica = copia de la política vigente
│       snapshot_instancias = copia de las instancias del año
│
└── 5. Inscribir en Moodle
        enrol_manual_enrol_users(user_id, course_id, roleid=5)
```

---

## 4. Flujo de Calificaciones

### 4.1 Carga de notas por docente

```
Docente selecciona materia → ve lista de alumnos
│
├── Selecciona instancia (ej: "Primer Parcial")
│
├── Si es grupal: puede crear/editar equipos
│
├── Carga notas (validando 0 ≤ nota ≤ peso_maximo de la instancia)
│
└── Guarda en tabla calificacion (local)
```

### 4.2 Cálculo automático de nota de curso

```python
# Pseudocódigo del motor de calificaciones
def calcular_estado(inscripcion):
    # Si ya está marcado como perdido o abandono, no recalcular
    if inscripcion.estado in (PERDIDO_INASISTENCIA, ABANDONO):
        return  # estado fijado manualmente

    politica = inscripcion.snapshot_politica
    calificaciones = inscripcion.calificaciones

    # Sumar notas de todas las instancias
    nota_curso = sum(c.nota for c in calificaciones)
    inscripcion.nota_curso = nota_curso

    # Aplicar reglas de la política
    if politica.umbral_exoneracion and nota_curso >= politica.umbral_exoneracion:
        inscripcion.estado = EXONERADO
        inscripcion.nota_final = nota_curso
        inscripcion.creditos_obtenidos = materia.creditos

    elif politica.umbral_examen and nota_curso >= politica.umbral_examen:
        inscripcion.estado = A_EXAMEN
        # nota_final se define cuando rinda examen

    elif not politica.umbral_examen and nota_curso >= politica.umbral_aprobacion:
        # Curso corto: aprueba directo
        inscripcion.estado = APROBADO
        inscripcion.nota_final = nota_curso
        inscripcion.creditos_obtenidos = materia.creditos

    else:
        inscripcion.estado = REPROBADO
        inscripcion.nota_final = nota_curso
        inscripcion.creditos_obtenidos = 0
```

### 4.3 Marcado manual de inasistencia / abandono

```
Docente o Admin desde el portal:
│
├── Selecciona alumno en la materia
│
├── Marca como "Perdido por inasistencia" o "Abandono"
│   (opcionalmente agrega motivo)
│
├── Sistema actualiza inscripcion_materia:
│   estado = PERDIDO_INASISTENCIA o ABANDONO
│   creditos_obtenidos = 0
│   motivo_cierre = "Exceso de faltas" / "Dejó de asistir"
│   fecha_cierre = now()
│
└── El alumno ve en su escolaridad el estado correspondiente
    y la materia NO cuenta como aprobada para previaturas
```

### 4.4 Escolaridad del estudiante

La escolaridad es una vista calculada sobre `inscripcion_materia`:

```
Para estudiante X en programa "Analista Programador":

Semestre 1:
  Programación 1    │ 2026 │ EXONERADO            │ 92/100 │ 10 créditos ✓
  Base de Datos 1   │ 2026 │ APROBADO             │ 75/100 │ 10 créditos ✓  (examen)
  Matemática 1      │ 2026 │ PERDIDO_INASISTENCIA │  --    │  0 créditos ✗
  Inglés 1          │ 2026 │ ABANDONO             │  --    │  0 créditos ✗

Semestre 2:
  Programación 2    │ (puede inscribirse, Prog1 aprobada)
  Base de Datos 2   │ (puede inscribirse, BD1 aprobada)
  Matemática 2      │ ⚠ No puede inscribirse (requiere Matemática 1)

Total créditos: 20 / 180
```

---

## 5. Integración Google → Roles → Endpoints

### 5.1 Protección de endpoints por rol

```python
# Dependencias de autenticación
def require_estudiante():  # Endpoints de alumno
def require_docente():     # Endpoints de docente
def require_admin():       # Endpoints de administrador
def require_any_role():    # Cualquier usuario autenticado
```

### 5.2 Endpoints por rol

**Estudiante:**
- `GET /portal/mi-escolaridad` — Ver todas sus materias y estados
- `GET /portal/materias-disponibles` — Materias a las que puede inscribirse
- `POST /portal/inscribirse-materia` — Inscribirse (valida previaturas)
- `GET /portal/examenes-disponibles` — Períodos abiertos
- `POST /portal/inscribirse-examen` — Inscribirse a examen
- `GET /portal/mis-calificaciones/{materia}` — Ver notas de una materia

**Docente:**
- `GET /portal/mis-materias` — Materias que dicta
- `GET /portal/materia/{id}/alumnos` — Lista de alumnos
- `POST /portal/materia/{id}/calificaciones` — Cargar notas
- `POST /portal/materia/{id}/equipos` — Gestionar equipos
- `GET /portal/examen/{id}/inscriptos` — Ver inscriptos a examen
- `POST /portal/examen/{id}/notas` — Cargar notas de examen
- `POST /portal/materia/{id}/marcar-inasistencia` — Marcar alumno como perdido por inasistencia
- `POST /portal/materia/{id}/marcar-abandono` — Marcar alumno como abandono

**Administrativo:**
- `POST /admin/programas` — CRUD de programas
- `POST /admin/materias` — CRUD de materias
- `POST /admin/politicas` — CRUD de políticas de calificación
- `POST /admin/previaturas` — Configurar previaturas
- `POST /admin/instancias-evaluacion` — Configurar instancias
- `POST /admin/periodos-inscripcion` — Habilitar inscripción a materias
- `POST /admin/periodos-examen` — Habilitar exámenes
- `GET /admin/escolaridad/{usuario_id}` — Consultar cualquier alumno
- `POST /admin/sync-moodle` — Forzar sincronización con Moodle
- `POST /admin/materia/{id}/marcar-inasistencia` — Marcar alumno (también puede hacerlo)
- `POST /admin/materia/{id}/marcar-abandono` — Marcar alumno (también puede hacerlo)

---

## 6. Puntos Pendientes de Definición

1. **Malla curricular:** Qué materia es previa de cuál para cada carrera
2. **Política de examen:** Si un alumno aprueba el examen, la nota del examen es la nota final (confirmado), pero ¿qué pasa si se presenta múltiples veces? ¿Se guarda la mejor nota?
3. **Límite de recursado:** ¿Hay un máximo de veces que un alumno puede recursar una materia?
4. **Asistencia mínima:** ¿Cuál es el umbral de inasistencias para perder la materia? (se maneja desde el plugin Attendance de Moodle, el docente/admin marca manualmente en nuestro portal)
5. **Aprobación por créditos:** ¿Hay un mínimo de créditos por semestre/año?
6. **WhatsApp:** ¿Qué proveedor usar? (Twilio, WhatsApp Business API, n8n?)
7. **Workflow n8n para OU:** Crear el workflow que reciba email y devuelva la OU del usuario
8. **Notas de Moodle:** Confirmado que los docentes cargan notas solo en nuestro portal, no en Moodle

---

## 7. Fases de Implementación Sugeridas

### Fase 1: Infraestructura
- Modelos SQLModel
- Migraciones Alembic
- Google OAuth (login con cuenta institucional)
- Workflow n8n para obtener OU → asignación de roles
- CRUD de programas, materias, políticas

### Fase 2: Inscripciones
- Períodos de inscripción
- Validación de previaturas
- Inscripción a materias (portal + Moodle)
- Sync con Moodle

### Fase 3: Calificaciones
- Carga de notas por docentes
- Motor de cálculo de estado
- Equipos para evaluaciones grupales
- Marcado de inasistencia y abandono
- Vista de escolaridad del alumno

### Fase 4: Exámenes
- Períodos de examen
- Inscripción a exámenes
- Carga de notas de examen
- Cálculo de nota final

### Fase 5: Notificaciones
- WhatsApp para inscripciones
- WhatsApp para disponibilidad de notas
- Notificaciones por email (ya tenemos n8n)

---

*Documento de planificación v2 — CTC Salto, Marzo 2026*
