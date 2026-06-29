# Sistema de Bedelía - CTC Salto

## Propuesta Técnica para Gestión Académica

**Versión:** 1.0
**Fecha:** Marzo 2026
**Proyecto:** Backend CTC - Rama `bedelia`

---

## 1. Resumen Ejecutivo

El presente documento describe la propuesta técnica para implementar un **sistema de bedelía digital** integrado con la plataforma Moodle del CTC Salto. El sistema gestionará calificaciones, previaturas, inscripciones a exámenes y el estado académico de los estudiantes.

El sistema se construirá como una **API REST (backend)** que cualquier frontend podrá consumir, aprovechando Moodle como fuente de datos de calificaciones y gestionando la lógica académica institucional en un motor propio.

---

## 2. Análisis de la Plataforma Moodle

### 2.1 Capacidades disponibles vía API REST

La API de Moodle (Web Services) ofrece las siguientes funcionalidades que el sistema aprovechará:

| Capacidad | Función API | Descripción |
|---|---|---|
| **Leer calificaciones** | `gradereport_user_get_grade_items` | Obtiene las notas de un alumno en un curso específico (parciales, obligatorio, concepto) |
| **Escribir calificaciones** | `core_grades_update_grades` | Permite publicar notas calculadas (nota de curso, nota de examen) de vuelta a Moodle |
| **Listar cursos** | `core_course_get_courses` | Obtiene todos los cursos con sus propiedades y campos personalizados |
| **Categorías jerárquicas** | `core_course_get_categories` | Permite mapear la estructura: Carrera > Semestre > Materia |
| **Inscripción a cursos** | `enrol_manual_enrol_users` | Inscribe un alumno en un curso tras validar previaturas |
| **Verificar inscripción** | `core_enrol_get_users_courses` | Consulta en qué cursos está inscripto un alumno |
| **Usuarios inscriptos** | `core_enrol_get_enrolled_users` | Lista todos los alumnos de un curso |
| **Estado de completitud** | `core_completion_get_course_completion_status` | Verifica si un alumno completó un curso |
| **Campos personalizados** | `core_course_update_courses` (customfields) | Permite agregar metadata a cursos (tipo de evaluación, umbrales) |

### 2.2 Limitaciones de Moodle (lo que NO puede hacer)

Estas funcionalidades **no existen en Moodle** y deben ser construidas en el sistema propio:

| Funcionalidad | Limitación en Moodle |
|---|---|
| **Previaturas entre cursos** | Moodle no tiene un sistema nativo de prerequisitos entre cursos. La funcionalidad fue removida en Moodle 2.x. Existen plugins de terceros pero no exponen API REST. |
| **Lógica de exoneración/examen** | El gradebook de Moodle calcula promedios simples pero no puede modelar reglas como "si suma >= 86 exonera, si >= 70 va a examen". |
| **Inscripción a exámenes** | No existe concepto de períodos de examen, registro de inscripción ni gestión de mesas examinadoras. |
| **Reglas de calificación por tipo de programa** | Moodle no diferencia la lógica de evaluación entre una carrera y un curso corto. |
| **Creación de ítems de calificación por API** | No se pueden crear programáticamente los ítems "Parcial 1", "Parcial 2", etc. Deben configurarse manualmente en Moodle o mediante plantillas de curso. |
| **Períodos académicos** | Moodle no tiene concepto de semestres ni años lectivos como entidades estructuradas. |

### 2.3 Configuración requerida en Moodle

Para que el sistema funcione, cada curso en Moodle deberá tener configurado su **gradebook** con los ítems de calificación correspondientes:

**Para carreras (ej: Analista Programador):**
- Parcial 1 (máximo según peso definido)
- Parcial 2 (máximo según peso definido)
- Obligatorio (máximo según peso definido)
- Concepto del docente (máximo según peso definido)

**Para cursos cortos:**
- Prueba única (máximo 100)

> **Nota:** Esta configuración se hace una vez por curso en Moodle (o usando plantillas de curso para replicar la estructura). Los docentes luego cargan las notas directamente en el gradebook de Moodle.

---

## 3. Arquitectura del Sistema

### 3.1 Diagrama General

```
┌──────────────────────────────────────────────────────────┐
│                      MOODLE LMS                          │
│                                                          │
│   Docentes cargan notas en el gradebook de cada curso    │
│   Ítems: Parcial 1 | Parcial 2 | Obligatorio | Concepto │
│                                                          │
└────────────────────────┬─────────────────────────────────┘
                         │
                         │ API REST (bajo demanda)
                         │
┌────────────────────────▼─────────────────────────────────┐
│                CTC BACKEND (FastAPI)                      │
│                                                          │
│  ┌──────────────────┐  ┌──────────────────────────────┐  │
│  │  Sync Service    │  │  Motor de Reglas Académicas  │  │
│  │                  │  │                              │  │
│  │  Lee notas de    │  │  Evalúa por tipo de programa │  │
│  │  Moodle cuando   │  │  Calcula: nota de curso,     │  │
│  │  se consulta     │  │  estado (exonera/examen/     │  │
│  │  un alumno       │  │  reprueba)                   │  │
│  └──────────────────┘  └──────────────────────────────┘  │
│                                                          │
│  ┌──────────────────┐  ┌──────────────────────────────┐  │
│  │  Previaturas     │  │  Gestión de Exámenes         │  │
│  │                  │  │                              │  │
│  │  Valida cadena   │  │  Períodos de inscripción,    │  │
│  │  de requisitos   │  │  registro de alumnos,        │  │
│  │  antes de        │  │  carga de notas de examen    │  │
│  │  inscribir       │  │                              │  │
│  └──────────────────┘  └──────────────────────────────┘  │
│                                                          │
│                   PostgreSQL                             │
│           (tablas paralelas de bedelía)                   │
└────────────────────────┬─────────────────────────────────┘
                         │
                         │ API REST (endpoints protegidos)
                         │
┌────────────────────────▼─────────────────────────────────┐
│              FRONTEND (cualquier cliente)                 │
│                                                          │
│   Portal Alumno:                                         │
│   - Ver estado académico por materia                     │
│   - Inscribirse a exámenes (cuando está habilitado)      │
│   - Consultar notas y estado en cada carrera             │
│                                                          │
│   Panel Bedelía (admin):                                 │
│   - Gestionar períodos de examen                         │
│   - Configurar previaturas                               │
│   - Consultar y modificar registros académicos           │
│   - Cargar notas de examen                               │
│                                                          │
│   Autenticación: Google OAuth                            │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Flujo de Datos

1. **Docente** carga notas en Moodle (Parcial 1, Parcial 2, Obligatorio, Concepto)
2. **Alumno o Admin** consulta estado académico → el backend consulta Moodle bajo demanda
3. **Backend** trae las calificaciones via `gradereport_user_get_grade_items`
4. **Motor de reglas** aplica la lógica según el tipo de programa
5. **Resultado** se almacena en PostgreSQL y se devuelve al cliente
6. Si el alumno debe rendir examen → puede inscribirse durante el período habilitado
7. Admin carga nota de examen → se calcula estado final

### 3.3 Sincronización bajo demanda

En lugar de un cron periódico, las calificaciones se sincronizan **cuando se consultan**:

- Cuando un alumno consulta su estado → se traen sus notas de Moodle en ese momento
- Se aplica un **caché corto** (ej: 15 minutos) para evitar consultas excesivas
- Los admin pueden forzar una re-sincronización manual si es necesario

**Ventaja:** No consume recursos innecesariamente. Solo se consulta Moodle cuando hay interés real en los datos.

---

## 4. Modelo de Datos

### 4.1 Diagrama de Tablas

```
┌─────────────┐       ┌──────────────────┐
│  programa   │       │     materia      │
│─────────────│       │──────────────────│
│ programa_id │◄──────│ programa_id (FK) │
│ nombre      │       │ materia_id       │
│ tipo        │       │ nombre           │
│ moodle_     │       │ moodle_course_id │
│ category_id │       │ semestre         │
│ activo      │       │ regla_calif      │
└─────────────┘       │ peso_parcial1    │
                      │ peso_parcial2    │
                      │ peso_obligatorio │
                      │ peso_concepto    │
                      │ nota_exoneracion │
                      │ nota_examen_min  │
                      │ activo           │
                      └───────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
┌──────────────────┐ ┌───────────────┐ ┌──────────────────────┐
│   previatura     │ │ inscripcion   │ │  periodo_examen      │
│──────────────────│ │  _materia     │ │──────────────────────│
│ previatura_id    │ │───────────────│ │ periodo_id           │
│ materia_id (FK)  │ │ inscripcion_id│ │ nombre               │
│ materia_previa   │ │ alumno_moodle │ │ fecha_inicio_inscr   │
│   _id (FK)       │ │   _id         │ │ fecha_fin_inscr      │
│ tipo_requerido   │ │ materia_id FK │ │ fecha_examen         │
│ (APROBADA|       │ │ anio_lectivo  │ │ habilitado           │
│  EXONERADA)      │ │ parcial_1     │ │ activo               │
└──────────────────┘ │ parcial_2     │ └──────────┬───────────┘
                     │ obligatorio   │            │
                     │ concepto      │            │
                     │ nota_curso    │            ▼
                     │ estado_curso  │ ┌──────────────────────┐
                     │ nota_examen   │ │ inscripcion_examen   │
                     │ estado_final  │ │──────────────────────│
                     │ fecha_sync    │ │ inscripcion_examen_id│
                     └───────┬───────┘ │ inscripcion_id (FK)  │
                             │         │ periodo_id (FK)      │
                             └────────►│ fecha_inscripcion    │
                                       │ estado               │
                                       │ nota_examen          │
                                       └──────────────────────┘
```

### 4.2 Detalle de Tablas

#### `programa`
Representa un programa educativo (carrera, curso corto, taller, diploma).

| Campo | Tipo | Descripción |
|---|---|---|
| `programa_id` | Integer, PK | Identificador único |
| `nombre` | String(100) | Ej: "Analista Programador", "Marketing Digital" |
| `tipo` | Enum | `CARRERA`, `CURSO_CORTO`, `TALLER`, `DIPLOMA` |
| `moodle_category_id` | Integer | ID de la categoría correspondiente en Moodle |
| `descripcion` | Text, opcional | Descripción del programa |
| `activo` | Boolean | Si el programa está vigente |
| `fecha_creacion` | Date | Fecha de creación del registro |

#### `materia`
Cada materia/asignatura dentro de un programa, vinculada a un curso de Moodle.

| Campo | Tipo | Descripción |
|---|---|---|
| `materia_id` | Integer, PK | Identificador único |
| `programa_id` | Integer, FK | Programa al que pertenece |
| `nombre` | String(100) | Ej: "Programación 1", "Base de Datos" |
| `moodle_course_id` | Integer | ID del curso en Moodle |
| `semestre` | Integer | Número de semestre (1, 2, 3...) |
| `regla_calificacion` | Enum | `PARCIALES_OBLIGATORIO_CONCEPTO`, `PRUEBA_UNICA`, `PROYECTO` |
| `peso_parcial1` | Integer | Peso máximo del Parcial 1 (ej: 20) |
| `peso_parcial2` | Integer | Peso máximo del Parcial 2 (ej: 30) |
| `peso_obligatorio` | Integer | Peso máximo del Obligatorio (ej: 30) |
| `peso_concepto` | Integer | Peso máximo del Concepto (ej: 10) |
| `nota_exoneracion` | Integer | Mínimo para exonerar (ej: 86) |
| `nota_examen_min` | Integer | Mínimo para ir a examen (ej: 70) |
| `nota_aprobacion_examen` | Integer | Mínimo para aprobar en examen (ej: 70) |
| `activo` | Boolean | Si la materia está vigente |

#### `previatura`
Define relaciones de prerequisitos entre materias.

| Campo | Tipo | Descripción |
|---|---|---|
| `previatura_id` | Integer, PK | Identificador único |
| `materia_id` | Integer, FK | La materia que tiene el requisito |
| `materia_previa_id` | Integer, FK | La materia que es prerequisito |
| `tipo_requerido` | Enum | `APROBADA` (examen o exoneración) o `EXONERADA` (solo exoneración) |

> **Ejemplo:** Si Programación 2 requiere tener Programación 1 aprobada:
> `materia_id = Prog2, materia_previa_id = Prog1, tipo_requerido = APROBADA`

#### `inscripcion_materia`
Registro académico de cada alumno en cada materia. Es la tabla central del sistema.

| Campo | Tipo | Descripción |
|---|---|---|
| `inscripcion_id` | Integer, PK | Identificador único |
| `alumno_moodle_id` | Integer | ID del alumno en Moodle |
| `materia_id` | Integer, FK | Materia cursada |
| `anio_lectivo` | Integer | Año lectivo (ej: 2026) |
| `parcial_1` | Decimal, nullable | Nota del Parcial 1 |
| `parcial_2` | Decimal, nullable | Nota del Parcial 2 |
| `obligatorio` | Decimal, nullable | Nota del Obligatorio |
| `concepto` | Decimal, nullable | Nota de Concepto del docente |
| `nota_curso` | Decimal, nullable | Suma calculada de las notas |
| `estado_curso` | Enum | `CURSANDO`, `EXONERADO`, `A_EXAMEN`, `REPROBADO` |
| `nota_examen` | Decimal, nullable | Nota obtenida en el examen |
| `estado_final` | Enum | `APROBADO`, `REPROBADO`, `PENDIENTE` |
| `fecha_sync` | DateTime | Última sincronización con Moodle |

#### `periodo_examen`
Períodos habilitados para inscripción a exámenes.

| Campo | Tipo | Descripción |
|---|---|---|
| `periodo_id` | Integer, PK | Identificador único |
| `nombre` | String(50) | Ej: "Febrero 2026", "Julio 2026" |
| `fecha_inicio_inscripcion` | Date | Cuándo abre la inscripción |
| `fecha_fin_inscripcion` | Date | Cuándo cierra la inscripción |
| `fecha_examen` | Date | Fecha del examen |
| `habilitado` | Boolean | Control manual (admin puede habilitar/deshabilitar) |
| `activo` | Boolean | Si el período está vigente |

#### `inscripcion_examen`
Registro de alumnos inscriptos a exámenes.

| Campo | Tipo | Descripción |
|---|---|---|
| `inscripcion_examen_id` | Integer, PK | Identificador único |
| `inscripcion_id` | Integer, FK | Referencia al registro académico |
| `periodo_id` | Integer, FK | Período de examen |
| `fecha_inscripcion` | DateTime | Cuándo se inscribió |
| `estado` | Enum | `INSCRIPTO`, `APROBADO`, `REPROBADO`, `AUSENTE` |
| `nota_examen` | Decimal, nullable | Nota obtenida |

---

## 5. Lógica de Calificaciones

### 5.1 Carreras (ej: Analista Programador)

La calificación se compone de **4 instancias** con pesos que suman 100:

| Componente | Peso (ejemplo) | Descripción |
|---|---|---|
| Parcial 1 | 20 puntos | Primera prueba parcial |
| Parcial 2 | 30 puntos | Segunda prueba parcial |
| Obligatorio | 30 puntos | Proyecto práctico a lo largo del curso |
| Concepto | 10 puntos | Evaluación del docente (participación, asistencia) |
| **Total máximo** | **90 puntos** | *(Los pesos son configurables por materia)* |

> **Nota:** Los pesos son configurables por materia. El ejemplo suma 90, pero cada materia puede tener su propia distribución.

**Reglas de evaluación:**

```
Nota de Curso = Parcial1 + Parcial2 + Obligatorio + Concepto

Si Nota de Curso >= 86  →  EXONERADO
   El alumno aprueba la materia con nota = Nota de Curso
   No necesita rendir examen

Si Nota de Curso >= 70 y < 86  →  A EXAMEN
   El alumno debe rendir examen en un período habilitado
   Si Nota de Examen >= 70  →  APROBADO con nota = Nota de Examen
   Si Nota de Examen < 70   →  REPROBADO

Si Nota de Curso < 70  →  REPROBADO
   El alumno no aprueba y debe recursar la materia
```

**Diagrama de flujo:**

```
          ┌─────────────────┐
          │ Docente carga   │
          │ notas en Moodle │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Sistema calcula │
          │ Nota de Curso   │
          │ (P1+P2+Ob+Co)  │
          └────────┬────────┘
                   │
         ┌─────────┼──────────┐
         │         │          │
    >= 86│    70-85│     < 70 │
         │         │          │
         ▼         ▼          ▼
    EXONERADO  A EXAMEN   REPROBADO
    (aprobado) │          (debe recursar)
               │
               ▼
          ┌──────────┐
          │ Rinde    │
          │ examen   │
          └────┬─────┘
               │
          ┌────┴────┐
          │         │
     >= 70│    < 70 │
          │         │
          ▼         ▼
      APROBADO  REPROBADO
      (nota =   (debe recursar)
       nota examen)
```

### 5.2 Cursos Cortos

Evaluación simplificada con una sola instancia:

```
Nota = Prueba Única (sobre 100)

Si Nota >= 70  →  APROBADO
Si Nota < 70   →  REPROBADO

(No hay instancia de examen)
```

### 5.3 Nota Final

| Escenario | Nota Final |
|---|---|
| Exonera con nota de curso 90 | **90** |
| Va a examen y saca 95 | **95** (la nota del examen es la nota final) |
| Va a examen y saca 65 | **Reprobado** |
| Reprueba el curso (nota < 70) | **Reprobado** |

---

## 6. Sistema de Previaturas

### 6.1 Concepto

Una **previatura** es una materia que debe estar aprobada antes de poder inscribirse en otra. Esto genera una cadena de dependencias que el sistema debe validar.

### 6.2 Ejemplo

```
Semestre 1                    Semestre 2                  Semestre 3
┌─────────────────┐          ┌─────────────────┐        ┌─────────────────┐
│ Programación 1  │─────────►│ Programación 2  │───────►│ Programación 3  │
└─────────────────┘          └─────────────────┘        └─────────────────┘

┌─────────────────┐          ┌─────────────────┐
│ Base de Datos 1 │─────────►│ Base de Datos 2 │
└─────────────────┘          └─────────────────┘
```

Un alumno que **no aprobó** Programación 1 (ni por exoneración ni por examen) **no puede inscribirse** a Programación 2.

### 6.3 Flujo de Validación

```
Alumno quiere inscribirse en Materia X
    │
    ▼
¿Materia X tiene previaturas?
    │
    ├── NO → Inscribir directamente
    │
    └── SI → Para cada materia previa:
              │
              ¿Alumno tiene estado APROBADO?
              │
              ├── SI → Continuar verificando otras previas
              │
              └── NO → RECHAZAR inscripción
                       Informar qué materias le faltan aprobar
```

> **Nota:** La malla curricular (qué materia es previa de cuál) debe definirse con el cliente antes de implementar esta funcionalidad. El sistema soportará cualquier configuración de previaturas.

---

## 7. Sistema de Exámenes

### 7.1 Flujo Completo

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Admin de   │     │   Alumno se  │     │   Docente    │     │   Sistema    │
│   bedelía    │     │  inscribe al │     │   carga nota │     │   calcula    │
│   crea       │────►│   examen     │────►│   del examen │────►│   estado     │
│   período    │     │  (si cumple  │     │              │     │   final      │
│              │     │   condición) │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

### 7.2 Condiciones para inscribirse a examen

1. El período de examen debe estar **habilitado** (campo `habilitado = true`)
2. La fecha actual debe estar entre `fecha_inicio_inscripcion` y `fecha_fin_inscripcion`
3. El alumno debe tener `estado_curso = A_EXAMEN` en esa materia
4. El alumno no debe estar ya inscripto en ese período para esa materia

### 7.3 Gestión por Admin (Bedelía)

El funcionario de bedelía puede:
- Crear períodos de examen con nombre, fechas e interruptor de habilitación
- Habilitar/deshabilitar la inscripción manualmente (independiente de las fechas)
- Ver la lista de inscriptos por materia/período
- Cargar notas de examen
- Consultar el estado académico de cualquier alumno

---

## 8. Endpoints API Propuestos

### 8.1 Programas y Materias (Admin)

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/bedelia/programas` | Listar programas |
| `POST` | `/bedelia/programas` | Crear programa |
| `PUT` | `/bedelia/programas/{id}` | Editar programa |
| `GET` | `/bedelia/programas/{id}/materias` | Materias de un programa |
| `POST` | `/bedelia/materias` | Crear materia |
| `PUT` | `/bedelia/materias/{id}` | Editar materia (pesos, umbrales) |

### 8.2 Previaturas (Admin)

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/bedelia/materias/{id}/previaturas` | Ver previaturas de una materia |
| `POST` | `/bedelia/previaturas` | Crear relación de previatura |
| `DELETE` | `/bedelia/previaturas/{id}` | Eliminar previatura |
| `GET` | `/bedelia/programas/{id}/malla` | Ver malla curricular completa |

### 8.3 Estado Académico

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/bedelia/alumnos/{moodle_id}/estado` | Estado académico completo del alumno |
| `GET` | `/bedelia/alumnos/{moodle_id}/materia/{id}` | Detalle de una materia específica |
| `POST` | `/bedelia/alumnos/{moodle_id}/sync` | Forzar sincronización con Moodle |
| `GET` | `/bedelia/materias/{id}/alumnos` | Todos los alumnos de una materia |

### 8.4 Exámenes (Admin/Bedelía)

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/bedelia/examenes/periodos` | Listar períodos de examen |
| `POST` | `/bedelia/examenes/periodos` | Crear período |
| `PUT` | `/bedelia/examenes/periodos/{id}` | Editar período (incluye habilitar/deshabilitar) |
| `GET` | `/bedelia/examenes/periodos/{id}/inscriptos` | Ver inscriptos en un período |
| `POST` | `/bedelia/examenes/{periodo_id}/notas` | Cargar notas de examen (batch) |

### 8.5 Inscripción a Exámenes (Alumno)

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/bedelia/examenes/disponibles` | Períodos abiertos para inscripción |
| `POST` | `/bedelia/examenes/inscribirse` | Inscribirse a un examen |
| `GET` | `/bedelia/examenes/mis-inscripciones` | Ver mis inscripciones a exámenes |

### 8.6 Inscripción a Materias (Alumno)

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/bedelia/materias/disponibles` | Materias a las que puede inscribirse (valida previaturas) |
| `POST` | `/bedelia/materias/inscribirse` | Inscribirse a una materia (valida previaturas, inscribe en Moodle) |

---

## 9. Autenticación

- **Alumnos:** Google OAuth (mismas cuentas institucionales @ctcsalto.edu.uy)
- **Admin/Bedelía:** Google OAuth con validación de rol en el sistema
- Los endpoints de alumno identifican al usuario por su email de Google y lo mapean al `alumno_moodle_id` correspondiente

---

## 10. Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Backend | FastAPI (Python) - proyecto existente |
| Base de datos | PostgreSQL (Supabase) - proyecto existente |
| ORM | SQLModel/SQLAlchemy - proyecto existente |
| Integración Moodle | API REST de Moodle - ya implementada |
| Caché | Redis - ya configurado |
| Autenticación | Google OAuth |
| Deploy | Heroku |

---

## 11. Fases de Implementación

### Fase 1: Estructura Base
- Modelos SQLModel para las nuevas tablas
- Migraciones de base de datos
- CRUD de programas y materias
- Vinculación con cursos/categorías de Moodle

### Fase 2: Calificaciones
- Servicio de sincronización con Moodle (bajo demanda)
- Motor de reglas de calificación
- Cálculo automático de nota de curso y estado
- Endpoints de consulta de estado académico

### Fase 3: Previaturas
- CRUD de relaciones de previatura
- Motor de validación de previaturas
- Integración con inscripción (bloqueo automático)
- Visualización de malla curricular

### Fase 4: Exámenes
- CRUD de períodos de examen
- Inscripción a exámenes (con validaciones)
- Carga de notas de examen
- Cálculo de estado final

### Fase 5: Portal Alumno
- Endpoints para consulta personal de estado académico
- Inscripción a exámenes por parte del alumno
- Inscripción a materias con validación de previaturas

---

## 12. Puntos Pendientes de Definición con el Cliente

1. **Malla curricular:** Definir qué materia es previa de cuál para cada carrera
2. **Pesos exactos por materia:** Confirmar si todas las materias de una carrera tienen los mismos pesos (20+30+30+10) o varían
3. **Talleres y diplomados:** ¿Tienen lógica de exoneración/examen o son como cursos cortos?
4. **Regla del total:** Los pesos del ejemplo suman 90 (20+30+30+10). ¿El máximo es 90 o 100? ¿Hay un componente faltante?
5. **Recursado:** ¿Un alumno que reprueba puede inscribirse nuevamente? ¿Hay límite de veces?
6. **Períodos de examen:** ¿Cuántos períodos hay por año típicamente? (Febrero, Julio, Diciembre?)
7. **Nota mínima por componente:** ¿Existe un mínimo por parcial/obligatorio o solo importa la suma?
8. **Asistencia:** ¿Hay un requisito de asistencia mínima que afecte la evaluación?

---

*Documento generado para presentación al cliente - CTC Salto, Marzo 2026*
