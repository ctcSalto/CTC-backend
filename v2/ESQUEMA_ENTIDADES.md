# Esquema de Entidades - Portal Institucional CTC v2

**Fecha:** Marzo 2026

---

## 1. Autenticación y Roles

### Login con Google OAuth 2.0

El login se realiza exclusivamente con cuentas institucionales `@ctcsalto.edu.uy`.

**Datos que devuelve Google al hacer login:**

| Campo | Ejemplo | Uso |
|---|---|---|
| `sub` | "110254783901..." | ID único permanente de Google |
| `email` | "nombre.apellido@ctcsalto.edu.uy" | Identificador del usuario |
| `name` | "Nombre Apellido" | Nombre completo |
| `given_name` | "Nombre" | Nombre |
| `family_name` | "Apellido" | Apellido |
| `picture` | "https://lh3.google..." | Foto de perfil |
| `hd` | "ctcsalto.edu.uy" | Dominio (valida que sea institucional) |

**Google OAuth NO devuelve la Unidad Organizativa** (OU). Para obtener la OU usamos **n8n**, que sí tiene acceso al Admin SDK de Google Workspace.

### Asignación de roles vía n8n (consultando OU de Google)

n8n tiene acceso al Admin SDK de Google, lo que nos permite consultar la OU de cualquier usuario. Esto es más confiable que inferir roles desde Moodle y cubre todos los roles incluyendo ADMINISTRATIVO.

```
Usuario hace login con Google
        │
        ▼
Backend recibe email + google_id
        │
        ▼
Consultar n8n: GET /google-user-ou?email=...
        │
        ▼
n8n consulta Admin SDK → devuelve orgUnitPath
        │
        ▼
¿Existe en nuestra BD?
   ┌────┴────┐
   NO        SI
   │         │
   ▼         ▼
Crear usuario     ¿Cambió la OU?
con rol según OU     │
   │            SI → Actualizar rol
   │            NO → Mantener rol
   │                │
   ▼                ▼
Generar JWT con rol
```

**Mapeo OU → Rol:**

| OU de Google | Rol en el sistema |
|---|---|
| `/Alumnos` | `ESTUDIANTE` |
| `/Equipo Docente` | `DOCENTE` |
| `/Administración y Ventas` | `ADMINISTRATIVO` |

**Ventajas sobre el enfoque anterior (Moodle):**
- La OU es la fuente de verdad real del rol
- Cubre ADMINISTRATIVO (antes no se podía detectar)
- Re-sync automático en cada login
- Una sola llamada a n8n

---

## 2. Diagrama de Entidades

```
                            CONFIGURACIÓN
    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │  ┌──────────────────────┐  ┌──────────────────────────┐ │
    │  │ politica_calificacion│  │    politica_examen        │ │
    │  │──────────────────────│  │──────────────────────────│ │
    │  │ id (PK)              │  │ id (PK)                  │ │
    │  │ nombre               │  │ nombre                   │ │
    │  │ nota_maxima           │  │ nota_maxima              │ │
    │  │ tipo_nota (ENUM)     │  │ umbral_aprobacion        │ │
    │  │ umbral_aprobacion    │  │ activo                   │ │
    │  │ umbral_examen (null) │  └──────────────────────────┘ │
    │  │ umbral_exoneracion   │                               │
    │  │   (nullable)         │                               │
    │  │ activo               │                               │
    │  └──────────┬───────────┘                               │
    │             │ (referenciada por materia)                 │
    └─────────────┼───────────────────────────────────────────┘
                  │
                  │
    ┌─────────────┼──── ESTRUCTURA ACADÉMICA ──────────────────┐
    │             │                                            │
    │  ┌──────────┴───────────┐                                │
    │  │      programa        │                                │
    │  │──────────────────────│                                │
    │  │ id (PK)              │                                │
    │  │ nombre               │                                │
    │  │ tipo (ENUM)          │  CARRERA | CURSO_CORTO         │
    │  │ moodle_category_id   │  | TALLER | DIPLOMA            │
    │  │ duracion_semestres   │                                │
    │  │ activo               │                                │
    │  └──────────┬───────────┘                                │
    │             │ 1:N                                        │
    │             │                                            │
    │  ┌──────────▼───────────┐     ┌────────────────────────┐ │
    │  │      materia         │     │     previatura         │ │
    │  │──────────────────────│     │────────────────────────│ │
    │  │ id (PK)              │◄────│ materia_id (FK)        │ │
    │  │ programa_id (FK)     │◄────│ materia_previa_id (FK) │ │
    │  │ nombre               │     │ tipo_requerido (ENUM)  │ │
    │  │ codigo               │     │  APROBADA | EXONERADA  │ │
    │  │ moodle_course_id     │     └────────────────────────┘ │
    │  │ semestre             │                                │
    │  │ creditos             │                                │
    │  │ politica_id (FK) ────┼──► politica_calificacion       │
    │  │ politica_examen_id   │──► politica_examen             │
    │  │ activo               │                                │
    │  └──────────┬───────────┘                                │
    │             │ 1:N (por año)                              │
    │             │                                            │
    │  ┌──────────▼──────────────────┐                         │
    │  │ materia_instancia_evaluacion│                         │
    │  │─────────────────────────────│                         │
    │  │ id (PK)                     │                         │
    │  │ materia_id (FK)             │                         │
    │  │ nombre                      │  "Primer Parcial"      │
    │  │ peso_maximo                 │  15, 30, 40...         │
    │  │ orden                       │  1, 2, 3, 4            │
    │  │ es_grupal                   │  true/false            │
    │  │ anio_lectivo                │  2026, 2027...         │
    │  │ activo                      │                         │
    │  └─────────────────────────────┘                         │
    │                                                          │
    │  ┌─────────────────────────┐                             │
    │  │   docente_materia       │                             │
    │  │─────────────────────────│                             │
    │  │ docente_id (FK usuario) │                             │
    │  │ materia_id (FK)         │                             │
    │  │ anio_lectivo            │                             │
    │  │ rol_docente (ENUM)      │  TITULAR | ADJUNTO         │
    │  └─────────────────────────┘                             │
    └──────────────────────────────────────────────────────────┘


    ┌──────── USUARIOS ────────────────────────────────────────┐
    │                                                          │
    │  ┌──────────────────────────────┐                        │
    │  │         usuario              │                        │
    │  │──────────────────────────────│                        │
    │  │ id (PK)                      │                        │
    │  │ google_id (unique, nullable) │  Sub de Google OAuth   │
    │  │ moodle_id (unique, nullable) │  ID en Moodle          │
    │  │ email (unique, indexed)      │  Email institucional   │
    │  │ nombre                       │                        │
    │  │ apellido                     │                        │
    │  │ documento (nullable)         │  Cédula                │
    │  │ telefono (nullable)          │  Para WhatsApp         │
    │  │ foto_url (nullable)          │  De Google             │
    │  │ ou_google (nullable)         │  "/Alumnos" etc.       │
    │  │ rol (ENUM)                   │  ESTUDIANTE | DOCENTE  │
    │  │                              │  | ADMINISTRATIVO      │
    │  │ activo                       │                        │
    │  │ google_activo                │  false si se borró     │
    │  │ moodle_activo                │  false si se borró     │
    │  │ fecha_creacion               │  Primer login          │
    │  │ ultimo_acceso                │                        │
    │  └──────────────────────────────┘                        │
    │                                                          │
    │  Cuando se elimina la cuenta de Google o Moodle,         │
    │  el usuario se marca como inactivo pero su               │
    │  escolaridad y calificaciones se MANTIENEN.              │
    └──────────────────────────────────────────────────────────┘


    ┌──────── REGISTRO ACADÉMICO ──────────────────────────────┐
    │                                                          │
    │  ┌──────────────────────────────────┐                    │
    │  │      inscripcion_materia         │                    │
    │  │──────────────────────────────────│                    │
    │  │ id (PK)                          │                    │
    │  │ usuario_id (FK)                  │                    │
    │  │ materia_id (FK)                  │                    │
    │  │ anio_lectivo                     │  2026              │
    │  │ estado (ENUM)                    │                    │
    │  │    CURSANDO                      │  Activo            │
    │  │    EXONERADO                     │  Aprobó sin examen │
    │  │    A_EXAMEN                      │  Derecho a examen  │
    │  │    APROBADO                      │  Aprobó            │
    │  │    REPROBADO                     │  No alcanzó nota   │
    │  │    PERDIDO_INASISTENCIA          │  Exceso de faltas  │
    │  │    ABANDONO                      │  Dejó de asistir   │
    │  │ nota_curso (calculada)           │                    │
    │  │ nota_final                       │                    │
    │  │ creditos_obtenidos               │  0 si no aprobó   │
    │  │ snapshot_politica (JSONB)        │  ◄── Histórico     │
    │  │ snapshot_instancias (JSONB)      │  ◄── Histórico     │
    │  │ fecha_inscripcion                │                    │
    │  │ fecha_cierre (nullable)          │                    │
    │  │ motivo_cierre (nullable)         │  Para inasist/aband│
    │  └──────────┬───────────────────────┘                    │
    │             │ 1:N                                        │
    │             │                                            │
    │  ┌──────────▼───────────────────────┐                    │
    │  │       calificacion               │                    │
    │  │──────────────────────────────────│                    │
    │  │ id (PK)                          │                    │
    │  │ inscripcion_id (FK)              │                    │
    │  │ instancia_evaluacion_id (FK)     │                    │
    │  │ nota                             │                    │
    │  │ equipo_id (FK, nullable)         │  Si es grupal     │
    │  │ docente_id (FK usuario)          │  Quién calificó   │
    │  │ fecha                            │                    │
    │  │ observaciones (nullable)         │                    │
    │  └──────────────────────────────────┘                    │
    │                                                          │
    │                                                          │
    │  ┌──────────────────────┐    ┌────────────────────────┐  │
    │  │      equipo          │    │   equipo_miembro       │  │
    │  │──────────────────────│    │────────────────────────│  │
    │  │ id (PK)              │◄───│ equipo_id (FK)         │  │
    │  │ instancia_eval_id FK │    │ usuario_id (FK)        │  │
    │  │ nombre               │    └────────────────────────┘  │
    │  └──────────────────────┘                                │
    │                                                          │
    └──────────────────────────────────────────────────────────┘


    ┌──────── EXÁMENES ────────────────────────────────────────┐
    │                                                          │
    │  ┌──────────────────────────────┐                        │
    │  │     periodo_examen           │                        │
    │  │──────────────────────────────│                        │
    │  │ id (PK)                      │                        │
    │  │ nombre                       │  "Febrero 2026"       │
    │  │ fecha_inicio_inscripcion     │                        │
    │  │ fecha_fin_inscripcion        │                        │
    │  │ fecha_consulta (nullable)    │  Clase de consulta    │
    │  │ fecha_examen                 │  Día de la prueba     │
    │  │ habilitado                   │  Control del admin    │
    │  └──────────┬───────────────────┘                        │
    │             │ 1:N                                        │
    │             │                                            │
    │  ┌──────────▼───────────────────────┐                    │
    │  │    inscripcion_examen            │                    │
    │  │──────────────────────────────────│                    │
    │  │ id (PK)                          │                    │
    │  │ inscripcion_materia_id (FK)      │  ◄── Link al curso│
    │  │ periodo_examen_id (FK)           │                    │
    │  │ fecha_inscripcion                │                    │
    │  │ nota_examen (nullable)           │                    │
    │  │ estado (ENUM)                    │  INSCRIPTO         │
    │  │    INSCRIPTO | APROBADO          │  APROBADO          │
    │  │    REPROBADO | AUSENTE           │  REPROBADO         │
    │  │ snapshot_politica_examen (JSONB) │  AUSENTE           │
    │  └──────────────────────────────────┘                    │
    │                                                          │
    └──────────────────────────────────────────────────────────┘


    ┌──────── PERÍODOS DE INSCRIPCIÓN ─────────────────────────┐
    │                                                          │
    │  ┌──────────────────────────────────┐                    │
    │  │  periodo_inscripcion_materia     │                    │
    │  │──────────────────────────────────│                    │
    │  │ id (PK)                          │                    │
    │  │ programa_id (FK)                 │                    │
    │  │ anio_lectivo                     │                    │
    │  │ semestre (nullable)              │                    │
    │  │ fecha_inicio                     │                    │
    │  │ fecha_fin                        │                    │
    │  │ habilitado                       │  Control del admin │
    │  └──────────────────────────────────┘                    │
    │                                                          │
    └──────────────────────────────────────────────────────────┘
```

---

## 3. Estados de inscripcion_materia

| Estado | Significado | Obtiene créditos | Quién lo asigna |
|---|---|---|---|
| `CURSANDO` | Activo en el curso | - | Automático al inscribirse |
| `EXONERADO` | Nota >= umbral exoneración | Sí | Motor de calificaciones |
| `A_EXAMEN` | Nota entre umbral_examen y umbral_exoneración | - | Motor de calificaciones |
| `APROBADO` | Aprobó (examen o directo en curso corto) | Sí | Motor de calificaciones |
| `REPROBADO` | Nota < umbral mínimo | No | Motor de calificaciones |
| `PERDIDO_INASISTENCIA` | Exceso de faltas | No | Docente o Admin (manual) |
| `ABANDONO` | Dejó de asistir / baja voluntaria | No | Docente o Admin (manual) |

**Sobre inasistencia y abandono:**
- El docente o admin marca manualmente al alumno desde nuestro portal
- Las asistencias se gestionan desde el **plugin Attendance de Moodle** (futuro)
- Estos estados son **independientes de la nota**: aunque tenga buenas calificaciones, pierde la materia
- El motor de calificaciones **no recalcula** si el estado es PERDIDO_INASISTENCIA o ABANDONO
- El campo `motivo_cierre` permite registrar el motivo específico

---

## 4. Sobre los Snapshots JSONB (Histórico)

Cuando un alumno se inscribe a una materia, se toma una "foto" de las reglas vigentes:

**`snapshot_politica`** — Cómo se evaluaba en ese momento:
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

**`snapshot_instancias`** — Qué instancias de evaluación tenía:
```json
[
  {"id": 1, "nombre": "Primer Parcial", "peso_maximo": 15, "orden": 1},
  {"id": 2, "nombre": "Segundo Parcial", "peso_maximo": 30, "orden": 2},
  {"id": 3, "nombre": "Proyecto Obligatorio", "peso_maximo": 40, "orden": 3},
  {"id": 4, "nombre": "Valoración Docente", "peso_maximo": 15, "orden": 4}
]
```

Si en 2027 cambia la política a base 12 y se eliminan instancias, los registros de 2026 **mantienen su snapshot original**. Al consultar la escolaridad histórica, el sistema usa el snapshot del año correspondiente.

---

## 5. Ejemplo: Escolaridad de un Estudiante

```
 ╔══════════════════════════════════════════════════════════════════════╗
 ║  ESCOLARIDAD — Juan Pérez                                          ║
 ║  Programa: Analista Programador                                     ║
 ║  Créditos acumulados: 20 / 180                                      ║
 ╠══════════════════════════════════════════════════════════════════════╣
 ║                                                                     ║
 ║  SEMESTRE 1 — 2026                                                  ║
 ║  ┌───────────────────┬──────────────────────┬────────┬────────────┐ ║
 ║  │ Materia           │ Estado               │ Nota   │ Créditos   │ ║
 ║  ├───────────────────┼──────────────────────┼────────┼────────────┤ ║
 ║  │ Programación 1    │ EXONERADO            │ 92/100 │ 10 ✓       │ ║
 ║  │ Base de Datos 1   │ APROBADO (examen)    │ 75/100 │ 10 ✓       │ ║
 ║  │ Matemática 1      │ PERDIDO_INASISTENCIA │   --   │  0 ✗       │ ║
 ║  │ Inglés 1          │ ABANDONO             │   --   │  0 ✗       │ ║
 ║  │ Lógica            │ REPROBADO            │ 55/100 │  0 ✗       │ ║
 ║  └───────────────────┴──────────────────────┴────────┴────────────┘ ║
 ║                                                                     ║
 ║  Detalle Programación 1 (Política: Base 100, Exoneración: 86):      ║
 ║  ┌────────────────────────┬──────────┬───────────┐                  ║
 ║  │ Instancia              │ Máximo   │ Nota      │                  ║
 ║  ├────────────────────────┼──────────┼───────────┤                  ║
 ║  │ Primer Parcial         │ 15       │ 13        │                  ║
 ║  │ Segundo Parcial        │ 30       │ 28        │                  ║
 ║  │ Proyecto Obligatorio   │ 40       │ 38        │                  ║
 ║  │ Valoración Docente     │ 15       │ 13        │                  ║
 ║  ├────────────────────────┼──────────┼───────────┤                  ║
 ║  │ TOTAL                  │ 100      │ 92        │                  ║
 ║  └────────────────────────┴──────────┴───────────┘                  ║
 ║  Resultado: 92 >= 86 → EXONERA ✓                                   ║
 ║                                                                     ║
 ║  SEMESTRE 2 — 2026 (inscripción)                                    ║
 ║  ┌───────────────────┬──────────────────────────────────────────┐   ║
 ║  │ Materia           │ Disponibilidad                           │   ║
 ║  ├───────────────────┼──────────────────────────────────────────┤   ║
 ║  │ Programación 2    │ ✓ Disponible (Prog 1 aprobada)           │   ║
 ║  │ Base de Datos 2   │ ✓ Disponible (BD 1 aprobada)             │   ║
 ║  │ Matemática 2      │ ✗ Requiere Matemática 1 aprobada         │   ║
 ║  │ Inglés 2          │ ✗ Requiere Inglés 1 aprobada             │   ║
 ║  └───────────────────┴──────────────────────────────────────────┘   ║
 ╚═════════════════════════════════════════════════════════════════════╝
```

---

## 6. Integración con Moodle

### Funciones de Moodle que usaremos

| Función | Para qué |
|---|---|
| `core_user_get_users_by_field` | Buscar usuario por email al hacer login (obtener moodle_id) |
| `core_enrol_get_users_courses` | Saber en qué cursos está un usuario |
| `core_course_get_courses` | Sincronizar cursos → materias |
| `core_course_get_categories` | Sincronizar categorías → programas |
| `enrol_manual_enrol_users` | Inscribir alumno en Moodle cuando se inscribe en nuestro portal |
| `enrol_manual_unenrol_users` | Desinscribir si es necesario |
| `core_enrol_get_enrolled_users` | Listar alumnos de un curso |

### Funciones de Moodle que NO usaremos

| Función | Por qué no |
|---|---|
| `gradereport_user_get_grade_items` | Lee notas de Moodle. No la necesitamos porque las notas se gestionan en nuestro portal. |
| `core_grades_update_grades` | Escribe notas a Moodle. No la necesitamos porque Moodle no es nuestro sistema de calificaciones. |

**Decisión:** Moodle se usa para **gestión de cursos e inscripciones**. Las **calificaciones viven exclusivamente en nuestro sistema**.

### Obtención de OU vía n8n

| Función | Para qué |
|---|---|
| Workflow n8n: `GET /google-user-ou` | Recibe email, consulta Admin SDK, devuelve OU del usuario |

**Decisión:** Los roles se asignan por la OU de Google (consultada vía n8n), no por inferencia de Moodle.

---

## 7. Resumen de Tablas

| # | Tabla | Propósito |
|---|---|---|
| 1 | `usuario` | Usuarios (Google + Moodle + datos locales + OU) |
| 2 | `programa` | Carreras, cursos cortos, diplomas |
| 3 | `materia` | Materias de cada programa |
| 4 | `politica_calificacion` | Reglas de evaluación (flexible, base 100, 12, letras) |
| 5 | `politica_examen` | Reglas de aprobación de examen |
| 6 | `materia_instancia_evaluacion` | Parciales, obligatorios, etc. (por año) |
| 7 | `previatura` | Relaciones de prerequisitos entre materias |
| 8 | `inscripcion_materia` | Registro académico alumno/materia (7 estados posibles) |
| 9 | `calificacion` | Notas individuales por instancia |
| 10 | `equipo` | Grupos para evaluaciones grupales |
| 11 | `equipo_miembro` | Miembros de cada equipo |
| 12 | `periodo_inscripcion_materia` | Períodos de inscripción a materias |
| 13 | `periodo_examen` | Períodos de exámenes |
| 14 | `inscripcion_examen` | Alumnos inscriptos a exámenes |
| 15 | `docente_materia` | Vincula docentes a materias por año |

---

## 8. Puntos Pendientes

1. Malla curricular (qué materia es previa de cuál)
2. Crear workflow en n8n que reciba email y devuelva la OU del usuario
3. Proveedor de WhatsApp para notificaciones
4. Política de recursado (límite de veces)
5. Umbral de inasistencias para perder la materia (plugin Attendance de Moodle)
6. Requisitos de asistencia mínima por tipo de programa

---

*Esquema de entidades v2 — CTC Salto, Marzo 2026*
