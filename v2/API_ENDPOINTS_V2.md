# API v2 - Portal Academico CTC Salto

**Base URL:** `/v2`
**Swagger:** `/docs` | **Scalar:** `/docs-scalar`
**Autenticacion:** Bearer Token JWT (header `Authorization: Bearer <token>`)

---

## Tabla de contenidos

1. [Autenticacion](#1-autenticacion)
2. [Portal Estudiante](#2-portal-estudiante)
3. [Portal Docente](#3-portal-docente)
4. [Admin - Programas](#4-admin---programas)
5. [Admin - Materias](#5-admin---materias)
6. [Admin - Instancias de Cursado](#6-admin---instancias-de-cursado)
7. [Admin - Instancias de Evaluacion](#7-admin---instancias-de-evaluacion)
8. [Admin - Instancias de Examen](#8-admin---instancias-de-examen)
9. [Admin - Politicas de Calificacion](#9-admin---politicas-de-calificacion)
10. [Admin - Politicas de Examen](#10-admin---politicas-de-examen)
11. [Admin - Previaturas](#11-admin---previaturas)
12. [Admin - Periodos de Inscripcion](#12-admin---periodos-de-inscripcion)
13. [Admin - Docentes por Materia](#13-admin---docentes-por-materia)
14. [Admin - Inscripciones](#14-admin---inscripciones)
15. [Admin - Examenes](#15-admin---examenes)
16. [Admin - Documentos](#16-admin---documentos)
17. [Admin - Usuarios](#17-admin---usuarios)
18. [Enums y valores posibles](#18-enums-y-valores-posibles)

---

## 1. Autenticacion

**Prefijo:** `/v2/auth`

### POST `/v2/auth/google/login`
Inicia el flujo OAuth. Redirige a Google.
- **Auth:** No requiere
- **Response:** Redirect a Google

### GET `/v2/auth/google/callback`
Callback de Google. Recibe el code, valida dominio @ctcsalto.edu.uy, obtiene OU, crea/actualiza usuario.
- **Auth:** No requiere
- **Response 200:**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "usuario": {
    "id": 1,
    "google_id": "google123",
    "moodle_id": 45,
    "email": "juan@ctcsalto.edu.uy",
    "nombre": "Juan",
    "apellido": "Perez",
    "foto_url": "https://lh3.google.com/foto.jpg",
    "ou_google": "/Alumnos",
    "rol": "estudiante",
    "activo": true,
    "google_activo": true,
    "moodle_activo": true,
    "fecha_creacion": "2026-03-01T10:00:00",
    "ultimo_acceso": "2026-05-04T15:30:00"
  }
}
```

### POST `/v2/auth/logout`
Revoca el token JWT (blacklist en Redis).
- **Auth:** Bearer Token
- **Response 200:** `{ "message": "Sesion cerrada exitosamente" }`

### GET `/v2/auth/me`
Datos del usuario autenticado.
- **Auth:** Bearer Token
- **Response 200:** Objeto `UsuarioRead` (ver seccion callback arriba)

---

## 2. Portal Estudiante

**Prefijo:** `/v2/portal/estudiante`
**Auth:** Bearer Token (rol `estudiante`)

### GET `/mi-perfil`
Perfil del estudiante con datos de alumno.
- **Response 200:**
```json
{
  "id": 1,
  "email": "juan@ctcsalto.edu.uy",
  "nombre": "Juan",
  "apellido": "Perez",
  "rol": "estudiante",
  "foto_url": "https://...",
  "activo": true,
  "perfil_alumno": {
    "alumno_id": 1,
    "fecha_ingreso": "2026-03-01"
  }
}
```

### GET `/mis-programas`
Programas donde el alumno esta inscripto.
- **Response 200:**
```json
[
  {
    "inscripcion_id": 1,
    "programa_id": 1,
    "nombre": "Tecnologo en Informatica",
    "tipo": "carrera",
    "area": "informatica",
    "estado": "activa",
    "anio_ingreso": 2026,
    "fecha_inscripcion": "2026-03-01T10:00:00"
  }
]
```

### GET `/programa/{programa_id}`
Info de un programa con sus materias. Valida que el alumno este inscripto.
- **Params:** `programa_id` (path, int)
- **Response 200:** Programa con lista de materias (nombre, codigo, semestre, creditos)
- **Error 403:** `"No estas inscripto en este programa"`

### GET `/programa/{programa_id}/previaturas`
Mapa de previaturas con estado del alumno en cada materia.
- **Params:** `programa_id` (path, int)
- **Response 200:**
```json
[
  {
    "materia_id": 1,
    "nombre": "Programacion 1",
    "codigo": "P1",
    "semestre": 1,
    "estado_alumno": "aprobada",
    "previaturas": []
  },
  {
    "materia_id": 2,
    "nombre": "Programacion 2",
    "codigo": "P2",
    "semestre": 2,
    "estado_alumno": "cursando",
    "previaturas": [
      { "materia_previa_id": 1, "nombre": "Programacion 1", "tipo_requerido": "aprobada" }
    ]
  }
]
```

### GET `/mis-materias?anio_lectivo={anio}`
Materias inscriptas en un ano lectivo.
- **Query params:** `anio_lectivo` (int, requerido)
- **Response 200:**
```json
[
  {
    "inscripcion_id": 1,
    "materia_id": 1,
    "nombre": "Programacion 1",
    "codigo": "P1",
    "semestre": 1,
    "estado": "cursando",
    "nota_curso": null,
    "faltas": 2,
    "instancia_cursado_id": 1
  }
]
```

### GET `/mi-materia/{inscripcion_id}`
Detalle completo de una materia inscripta (notas, faltas, calificaciones).
- **Params:** `inscripcion_id` (path, int)
- **Response 200:**
```json
{
  "inscripcion_id": 1,
  "materia": { "nombre": "Programacion 1", "codigo": "P1", "semestre": 1, "creditos": 10 },
  "estado": "cursando",
  "nota_curso": 75.5,
  "nota_final": null,
  "faltas": 2,
  "faltas_maximas": 10,
  "calificaciones": [
    {
      "instancia_evaluacion_id": 1,
      "nombre": "Parcial 1",
      "peso_maximo": 50,
      "nota": 38.5,
      "fecha": "2026-04-15T10:00:00"
    }
  ]
}
```

### GET `/mi-escolaridad?programa_id={id}`
Escolaridad completa del alumno en un programa: **todas** las materias del plan,
agrupadas por semestre, esten cursadas o no.
- **Query params:** `programa_id` (int, requerido)
- **Response 200:**
```json
{
  "alumno_id": 42,
  "programa_id": 3,
  "semestres": [
    {
      "semestre": 1,
      "materias": [
        {
          "inscripcion_id": 1,
          "materia_nombre": "Programacion 1",
          "materia_codigo": "P1",
          "semestre": 1,
          "anio_lectivo": 2026,
          "estado": "exonerado",
          "nota_curso": 92.0,
          "nota_final": 92.0,
          "creditos_obtenidos": 10,
          "faltas": 1
        }
      ]
    },
    {
      "semestre": 2,
      "materias": [
        {
          "inscripcion_id": null,
          "materia_nombre": "Base de Datos",
          "materia_codigo": "BD1",
          "semestre": 2,
          "anio_lectivo": null,
          "estado": "sin_inscripcion",
          "nota_curso": null,
          "nota_final": null,
          "creditos_obtenidos": 0,
          "faltas": 0
        }
      ]
    }
  ],
  "total_creditos": 10,
  "total_creditos_posibles": 30
}
```

**Notas para el cliente:**
- `semestres` es una **lista ordenada** por numero de semestre, no un objeto indexado.
- Todas las filas de `materias` tienen las mismas claves. Las materias en las que
  el alumno nunca se inscribio traen `estado: "sin_inscripcion"` y los campos de
  inscripcion en `null` (o `0` en los contadores).
- `estado` es un valor de `EstadoInscripcionMateria` (`cursando`, `exonerado`,
  `a_examen`, `aprobado`, `reprobado`, `perdido_inasistencia`, `abandono`,
  `revalidada`) o el pseudo-estado `sin_inscripcion`.
- Si el alumno recurso una materia, se devuelve **solo** la inscripcion del
  `anio_lectivo` mas alto; las anteriores no aparecen.
- `total_creditos_posibles` suma los creditos de todas las materias del plan,
  no solo de las cursadas.

### GET `/materias-habilitadas?programa_id={id}`
Materias a las que el alumno puede inscribirse **en el semestre activo**.

El semestre activo lo define el periodo de inscripcion abierto del programa: de
ahi salen `anio_lectivo` y `semestre`, por eso el cliente no los manda. Aplica
las mismas validaciones que el POST de inscripcion, asi que `puede_inscribirse`
no deberia contradecir al alta.

- **Query params:** `programa_id` (int, requerido)
- **Response 200:**
```json
{
  "programa_id": 3,
  "periodo_inscripcion": {
    "abierto": true,
    "periodo_id": 5,
    "anio_lectivo": 2026,
    "semestre": 1,
    "fecha_inicio": "2026-02-01T00:00:00-03:00",
    "fecha_fin": "2026-03-15T23:59:00-03:00"
  },
  "materias": [
    {
      "materia_id": 2,
      "nombre": "Programacion 2",
      "codigo": "P2",
      "semestre_plan": 2,
      "creditos": 10,
      "instancia_cursado_id": 5,
      "anio_lectivo": 2026,
      "semestre": 1,
      "horario": "Lunes 18-21",
      "salon": "Lab 2",
      "cupo_maximo": 30,
      "inscriptos": 12,
      "puede_inscribirse": true,
      "motivos": [],
      "previaturas_faltantes": []
    }
  ]
}
```

Sin periodo abierto la respuesta es `{"programa_id": 3, "periodo_inscripcion": {"abierto": false}, "materias": []}`.

**Notas para el cliente:**
- Chequea `periodo_inscripcion.abierto` antes de interpretar una lista vacia: sin
  periodo abierto no hay nada habilitado, y es distinto de "no te queda nada por cursar".
- `semestre_plan` es la posicion de la materia en el plan de estudios;
  `semestre` es el semestre calendario en que se dicta la instancia. No son lo mismo.
- Una materia aparece solo si se dicta en el semestre activo, con instancia en
  estado `planificada` o `en_curso`. Las instancias con `semestre: null` se
  consideran dictadas en cualquier semestre.
- Se excluyen las materias ya `aprobado`, `exonerado`, `revalidada` o `cursando`.
  Una `reprobado` si aparece, para recursar.
- `motivos` acumula todo lo que impide inscribirse: previaturas faltantes y cupo
  completo. `previaturas_faltantes` es el subconjunto de previaturas.
- **403** si el alumno no tiene inscripcion activa al programa.

### GET `/materias-disponibles?programa_id={id}&anio_lectivo={anio}`
Version anterior, **superada por `/materias-habilitadas`**. No chequea el periodo
de inscripcion ni el estado de la instancia, asi que puede devolver
`puede_inscribirse: true` para una materia cuyo POST falla con
`"No hay un periodo de inscripcion activo"`. Se mantiene por compatibilidad.

- **Query params:** `programa_id` (int), `anio_lectivo` (int) - ambos requeridos
- **Response 200:**
```json
[
  {
    "materia_id": 2,
    "nombre": "Programacion 2",
    "codigo": "P2",
    "semestre": 2,
    "creditos": 10,
    "puede_inscribirse": true,
    "previaturas_faltantes": [],
    "instancia_cursado_id": 5
  }
]
```

### POST `/inscribirse-materia`
Inscribirse a una materia. Valida previaturas y periodo activo.
- **Body:**
```json
{ "instancia_cursado_id": 5 }
```
- **Response 200:** Objeto `InscripcionMateriaRead`
```json
{
  "id": 1,
  "usuario_id": 1,
  "instancia_cursado_id": 5,
  "estado": "cursando",
  "nota_curso": null,
  "nota_final": null,
  "faltas": 0,
  "creditos_obtenidos": 0,
  "fecha_inscripcion": "2026-03-15T10:00:00"
}
```
- **Error 400:** `"Previaturas no cumplidas: ..."` / `"No hay periodo de inscripcion activo"`

### GET `/mis-calificaciones/{inscripcion_id}`
Calificaciones del alumno en una inscripcion.
- **Params:** `inscripcion_id` (path, int)
- **Response 200:**
```json
[
  {
    "id": 1,
    "inscripcion_id": 1,
    "instancia_evaluacion_id": 1,
    "nota": 85.0,
    "docente_id": 3,
    "fecha": "2026-04-15T10:00:00",
    "observaciones": null
  }
]
```

### POST `/inscribirse-examen`
Inscribirse a un examen. Valida estado A_EXAMEN, periodo de inscripcion abierto, y que no se hayan agotado las oportunidades (`max_oportunidades` de la politica de examen). Asigna `numero_rendicion` automaticamente.
- **Body:**
```json
{
  "inscripcion_materia_id": 1,
  "instancia_examen_id": 3
}
```
- **Response 201:** Objeto `InscripcionExamenRead`
```json
{
  "id": 1,
  "inscripcion_materia_id": 1,
  "instancia_examen_id": 3,
  "fecha_inscripcion": "2026-07-01T10:00:00",
  "nota_examen": null,
  "estado": "inscripto",
  "numero_rendicion": 1
}
```
- **Error 400:** `"Se agotaron las N oportunidades de examen para esta materia"`

### GET `/mis-examenes/{inscripcion_id}`
Historial de examenes de una inscripcion a materia.
- **Params:** `inscripcion_id` (path, int)
- **Response 200:** Lista de `InscripcionExamenRead`

### DELETE `/desinscribir-examen/{inscripcion_examen_id}`
Desinscribirse de un examen (solo si esta INSCRIPTO). Usa soft-delete: cambia estado a `baja` con `fecha_baja`. Valida plazo minimo de 72hs antes del examen.
- **Response 204:** Sin body
- **Error 400:** `"Solo se permite hasta 72 horas antes del examen"`

### DELETE `/desinscribir-materia/{inscripcion_id}`
Desinscribirse de una materia (solo si CURSANDO y dentro de periodo activo). Usa soft-delete: cambia estado a `abandono` con `fecha_baja` y `motivo_cierre`.
- **Response 204:** Sin body

### GET `/examenes-disponibles?programa_id={id}`
Examenes disponibles para el alumno (materias en A_EXAMEN con inscripcion abierta).
- **Query params:** `programa_id` (int, requerido)
- **Response 200:**
```json
[
  {
    "instancia_examen_id": 3,
    "inscripcion_materia_id": 1,
    "materia_id": 1,
    "materia_nombre": "Programacion 1",
    "materia_codigo": "P1",
    "nombre_examen": "Febrero 2026",
    "fecha_examen": "2026-02-15",
    "hora": "09:00",
    "salon": "Salon A",
    "modalidad": "presencial",
    "tipo": "ordinario",
    "ya_inscripto": false
  }
]
```

### GET `/examenes-habilitados?programa_id={id}`
Examenes a los que el alumno puede inscribirse. **Supera a
`/examenes-disponibles`**: aplica todas las validaciones del POST, no solo el
plazo, asi que `puede_inscribirse` no contradice al alta.

- **Query params:** `programa_id` (int, requerido)
- **Response 200:**
```json
[
  {
    "instancia_examen_id": 3,
    "inscripcion_materia_id": 1,
    "materia_id": 1,
    "materia_nombre": "Programacion 1",
    "materia_codigo": "P1",
    "nombre_examen": "Febrero 2026",
    "fecha_examen": "2026-02-15T09:00:00",
    "fecha_fin_inscripcion": "2026-02-10T23:59:00",
    "hora": "09:00",
    "salon": "Salon A",
    "modalidad": "presencial",
    "tipo": "ordinario",
    "ya_inscripto": false,
    "rendiciones_previas": 1,
    "max_oportunidades": 5,
    "puede_inscribirse": true,
    "motivos": []
  }
]
```

**Notas para el cliente:**
- Solo aparecen materias en estado `a_examen` con instancias habilitadas y dentro
  del plazo de inscripcion.
- `motivos` explica por que no se puede inscribir: oportunidades agotadas, materia
  sin politica de examen configurada, o ya inscripto a ese examen.
- `rendiciones_previas` cuenta las rendiciones consumidas (aprobado, reprobado o
  ausente; no cuentan las bajas ni las inscripciones pendientes).
- **Las previaturas no se validan aca a proposito.** Para llegar a `a_examen` el
  alumno tuvo que cursar la materia, y esa inscripcion ya las valido.
- **403** si el alumno no tiene inscripcion activa al programa.

### GET `/todos-mis-examenes`
Todos los examenes del alumno, todas las materias, ordenados por fecha.
- **Response 200:**
```json
[
  {
    "inscripcion_examen_id": 1,
    "inscripcion_materia_id": 1,
    "materia_nombre": "Programacion 1",
    "materia_codigo": "P1",
    "nombre_examen": "Febrero 2026",
    "fecha_examen": "2026-02-15",
    "estado": "aprobado",
    "nota_examen": 78.0
  }
]
```

### GET `/mi-egreso?programa_id={id}`
Verificar progreso de egreso en un programa.
- **Query params:** `programa_id` (int, requerido)
- **Response 200:**
```json
{
  "cumple": false,
  "programa_id": 3,
  "programa_nombre": "Analista en Informatica",
  "creditos_obtenidos": 20,
  "creditos_requeridos": 30,
  "creditos_totales_plan": 30,
  "materias_aprobadas": 2,
  "materias_pendientes": 1,
  "materias_totales": 3,
  "porcentaje_avance": 66.67,
  "detalle_aprobadas": [
    {
      "materia_id": 1,
      "nombre": "Programacion 1",
      "codigo": "P1",
      "semestre": 1,
      "creditos": 10,
      "estado": "exonerado",
      "anio_lectivo": 2025,
      "nota_final": 95.0,
      "nota_curso": 95.0
    },
    {
      "materia_id": 2,
      "nombre": "Base de Datos",
      "codigo": "BD1",
      "semestre": 2,
      "creditos": 10,
      "estado": "revalidada",
      "anio_lectivo": 2024,
      "nota_final": null,
      "nota_curso": null
    }
  ],
  "detalle_pendientes": [
    {
      "materia_id": 3,
      "nombre": "Programacion 2",
      "codigo": "P2",
      "semestre": 3,
      "creditos": 10
    }
  ]
}
```

**Notas para el cliente:**
- Una materia cuenta como cumplida si esta `aprobado`, `exonerado` o `revalidada`
  — los tres otorgan creditos. `a_examen` **no** cuenta: el curso no esta cerrado.
- El campo `estado` de `detalle_aprobadas` dice cual de los tres es. Importa
  porque una `revalidada` no tiene notas y vendria con `null` en ambas.
- Las entradas de `detalle_pendientes` **no** traen `estado`, `anio_lectivo` ni
  notas: son materias del plan que el alumno todavia no cumplio, con o sin
  intentos previos.
- Si el alumno recurso una materia, el detalle reporta la inscripcion del
  `anio_lectivo` mas alto, y los creditos se cuentan **una sola vez**.
- `cumple` exige las dos cosas: llegar a `creditos_requeridos` **y** no tener
  materias pendientes.

---

## 3. Portal Docente

**Prefijo:** `/v2/portal/docente`
**Auth:** Bearer Token (rol `docente` o `administrativo`)

### GET `/mi-perfil`
Perfil del docente con datos de profesor.
- **Response 200:**
```json
{
  "id": 3,
  "email": "profe@ctcsalto.edu.uy",
  "nombre": "Maria",
  "apellido": "Lopez",
  "rol": "docente",
  "activo": true,
  "perfil_profesor": {
    "profesor_id": 1,
    "cargo": "titular",
    "dedicacion": "tiempo_completo",
    "especialidad": "Programacion",
    "activo": true
  }
}
```

**Cuidado con los dos `activo`:** el de la raiz es `usuario.activo` y controla el
acceso al sistema (en `false` no puede iniciar sesion). El de `perfil_profesor`
es `profesor.activo` e indica si dicta actualmente. Un profesor retirado queda
con `perfil_profesor.activo: false` y `activo: true`, para poder seguir
consultando su historico.

### GET `/mis-programas`
Programas donde el docente es coordinador.
- **Response 200:**
```json
[
  {
    "programa_id": 1,
    "nombre": "Tecnologo en Informatica",
    "tipo": "carrera",
    "area": "informatica",
    "cantidad_materias": 25
  }
]
```

### GET `/mis-materias?anio_lectivo={anio}`
Materias asignadas al docente en un ano lectivo.
- **Query params:** `anio_lectivo` (int, requerido)
- **Response 200:**
```json
[
  {
    "asignacion_id": 1,
    "instancia_cursado_id": 5,
    "materia_id": 1,
    "nombre": "Programacion 1",
    "codigo": "P1",
    "semestre": 1,
    "anio_lectivo": 2026,
    "salon": "Salon A",
    "horario": "Lunes 18-21",
    "estado": "en_curso",
    "rol_docente": "titular"
  }
]
```

### GET `/mi-historico-materias?anio_lectivo={anio}`
Historico completo de materias dictadas, de la mas reciente a la mas antigua.
A diferencia de `/mis-materias`, el año es **opcional**: sin el parametro
devuelve todos los años.

- **Query params:** `anio_lectivo` (int, opcional)
- **Response 200:**
```json
[
  {
    "asignacion_id": 12,
    "instancia_cursado_id": 40,
    "materia_id": 1,
    "materia_nombre": "Programacion 1",
    "materia_codigo": "P1",
    "programa_id": 3,
    "programa_nombre": "Analista en Informatica",
    "semestre_plan": 1,
    "anio_lectivo": 2026,
    "semestre": 1,
    "salon": "Lab 2",
    "horario": "Lunes 18-21",
    "estado_instancia": "en_curso",
    "rol_docente": "titular",
    "total_inscriptos": 27
  }
]
```

Devuelve `[]` si el usuario no tiene perfil de profesor (por ejemplo un
administrativo, que accede con el mismo rol permitido en este router).

### GET `/mi-historico-examenes?anio={anio}`
Historico de examenes en los que el docente integro el tribunal, del mas
reciente al mas antiguo.

- **Query params:** `anio` (int, opcional) - filtra por año de `fecha_examen`
- **Response 200:**
```json
[
  {
    "asignacion_id": 8,
    "instancia_examen_id": 15,
    "materia_id": 1,
    "materia_nombre": "Programacion 1",
    "materia_codigo": "P1",
    "programa_id": 3,
    "programa_nombre": "Analista en Informatica",
    "nombre_examen": "Febrero 2026 - Programacion 1",
    "fecha_examen": "2026-02-15T09:00:00",
    "hora": "09:00",
    "salon": "Salon A",
    "modalidad": "presencial",
    "tipo": "ordinario",
    "estado_instancia": "programado",
    "total_inscriptos": 14
  }
]
```

### GET `/instancia-cursado/{id}/alumnos`
Lista de alumnos inscriptos en una instancia.
- **Params:** `instancia_cursado_id` (path, int)
- **Response 200:**
```json
[
  {
    "inscripcion_id": 1,
    "usuario_id": 1,
    "nombre": "Juan",
    "apellido": "Perez",
    "estado": "cursando",
    "nota_curso": null
  }
]
```

### GET `/instancia-cursado/{id}/detalle`
Detalle completo: info materia, alumnos, evaluaciones, faltas maximas.
- **Response 200:** Objeto con toda la info de la instancia

### GET `/instancia-cursado/{id}/resultados`
Tabla de resultados (acta). Todos los alumnos con notas por evaluacion.
- **Response 200:** Tabla con alumnos, notas, estados

### GET `/instancia-cursado/{id}/estadisticas`
Estadisticas de aprobacion y asistencia.
- **Response 200:**
```json
{
  "total_inscriptos": 30,
  "aprobados": 15,
  "reprobados": 5,
  "exonerados": 8,
  "a_examen": 7,
  "abandonos": 2,
  "perdidos_inasistencia": 1,
  "promedio_notas": 68.5,
  "tasa_aprobacion": 76.7
}
```

### GET `/instancia-cursado/{id}/calificaciones?instancia_evaluacion_id={id}`
Notas de todos los alumnos en una evaluacion especifica.
- **Query params:** `instancia_evaluacion_id` (int, requerido)
- **Response 200:** Lista con nota por alumno

### POST `/instancia-cursado/{id}/calificaciones`
Cargar nota individual.
- **Body:**
```json
{
  "inscripcion_id": 1,
  "instancia_evaluacion_id": 1,
  "nota": 85.5,
  "equipo_id": null,
  "observaciones": "Buen trabajo"
}
```
- **Response 200:** Objeto `CalificacionRead`

### POST `/instancia-cursado/{id}/calificaciones/batch`
Carga masiva de notas para una evaluacion.
- **Body:**
```json
{
  "instancia_evaluacion_id": 1,
  "calificaciones": [
    { "inscripcion_id": 1, "nota": 85.0 },
    { "inscripcion_id": 2, "nota": 72.0 },
    { "inscripcion_id": 3, "nota": 90.0, "observaciones": "Excelente" }
  ]
}
```
- **Response 200:**
```json
{
  "exitosos": 3,
  "errores": [],
  "calificaciones": [ ... ]
}
```

### POST `/instancia-cursado/{id}/nota-final-directa`
Cargar nota final sin parciales (promedio ya calculado).
- **Body:**
```json
{
  "inscripcion_id": 1,
  "nota": 78.0
}
```
- **Response 200:** Objeto `InscripcionMateriaRead` (estado recalculado automaticamente)

### GET `/instancia-cursado/{id}/equipos?instancia_evaluacion_id={id}`
Equipos de una evaluacion grupal.
- **Query params:** `instancia_evaluacion_id` (int, requerido)
- **Response 200:** Lista de equipos con miembros

### POST `/instancia-cursado/{id}/equipos`
Crear equipo para evaluacion grupal.
- **Body:**
```json
{
  "instancia_evaluacion_id": 1,
  "nombre": "Equipo A",
  "miembros_ids": [1, 2, 3]
}
```
- **Response 200:** `{ "id": 1, "nombre": "Equipo A", "instancia_evaluacion_id": 1 }`

### DELETE `/instancia-cursado/{id}/equipos/{equipo_id}`
Eliminar equipo.
- **Response 204:** Sin body

### POST `/instancia-cursado/{id}/faltas`
Registrar una falta a un alumno. Si alcanza `faltas_maximas`, cambia estado a `perdido_inasistencia` automaticamente.
- **Body:**
```json
{ "inscripcion_id": 1 }
```
- **Response 200:** Objeto `InscripcionMateriaRead` (con faltas actualizado)

### DELETE `/instancia-cursado/{id}/faltas`
Quitar una falta a un alumno (minimo 0).
- **Body:**
```json
{ "inscripcion_id": 1 }
```
- **Response 200:** Objeto `InscripcionMateriaRead`

### GET `/materia/{materia_id}/examenes?instancia_examen_id={id}`
Lista de inscriptos a examen para una instancia de examen.
- **Query params:** `instancia_examen_id` (int, requerido)
- **Response 200:** Lista con alumnos inscriptos, notas, estados

### POST `/materia/{materia_id}/examenes/{inscripcion_examen_id}/calificar`
Calificar un examen.
- **Body:**
```json
{ "nota_examen": 78.5 }
```
- **Response 200:** Objeto `InscripcionExamenRead` (estado actualizado)

### POST `/materia/{materia_id}/examenes/{inscripcion_examen_id}/ausente`
Marcar como ausente en un examen.
- **Response 200:** Objeto `InscripcionExamenRead` con `estado: "ausente"`

---

## 4. Admin - Programas

**Prefijo:** `/v2/admin/programas`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/`
Crear programa. **Body:**
```json
{
  "nombre": "Tecnologo en Informatica",
  "tipo": "carrera",
  "area": "informatica",
  "duracion_semestres": 6,
  "total_creditos": 240,
  "descripcion": "Programa de 3 anos...",
  "coordinador_id": 1
}
```
**Response 201:** `ProgramaRead`

### GET `/{programa_id}` - Obtener programa por ID
### GET `/{programa_id}/con-materias` - Programa con lista de materias por semestre
### GET `/` - Listar con paginacion (`?offset=0&limit=10`)
### POST `/filters` - Filtros avanzados (body `Filter`)
### PUT `/{programa_id}` - Actualizar (body parcial)
### DELETE `/{programa_id}` - Eliminar (204)

---

## 5. Admin - Materias

**Prefijo:** `/v2/admin/materias`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/`
Crear materia. **Body:**
```json
{
  "programa_id": 1,
  "nombre": "Programacion 1",
  "codigo": "P1",
  "semestre": 1,
  "creditos": 10,
  "descripcion": "Introduccion a la programacion",
  "horas_semanales": 4,
  "activa": true
}
```
**Response 201:** `MateriaRead`

### GET `/por-programa/{programa_id}` - Materias de un programa (ordenadas por semestre)
### GET `/{materia_id}` - Obtener por ID
### GET `/` - Listar con paginacion
### POST `/filters` - Filtros avanzados
### PUT `/{materia_id}` - Actualizar
### DELETE `/{materia_id}` - Eliminar (204)

---

## 6. Admin - Instancias de Cursado

**Prefijo:** `/v2/admin/instancias-cursado`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/`
Crear instancia de cursado. **Body:**
```json
{
  "materia_id": 1,
  "anio_lectivo": 2026,
  "semestre": 1,
  "fecha_inicio": "2026-03-01T00:00:00",
  "fecha_fin": "2026-07-15T00:00:00",
  "salon": "Salon A",
  "horario": "Lunes 18-21",
  "cupo_maximo": 35,
  "faltas_maximas": 10,
  "estado": "planificada"
}
```
**Response 200:** `InstanciaCursadoRead`

**Sobre `semestre`:** es el semestre calendario en que se dicta esta instancia
(1 o 2), distinto de `materia.semestre`, que es la posicion en el plan de
estudios. Es opcional y `null` significa "no declarado": esas instancias se
consideran dictadas en cualquier semestre y por eso siguen apareciendo en
`/materias-habilitadas`. **Cargalo** en las instancias nuevas, o el filtro por
semestre activo no discrimina nada.

### GET `/?materia_id={id}&anio_lectivo={anio}` - Listar (filtros opcionales)
### GET `/{instancia_id}` - Obtener por ID
### PUT `/{instancia_id}` - Actualizar
### DELETE `/{instancia_id}` - Eliminar

---

## 7. Admin - Instancias de Evaluacion

**Prefijo:** `/v2/admin/instancias-evaluacion`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/`
Crear instancia de evaluacion. **Body:**
```json
{
  "instancia_cursado_id": 5,
  "nombre": "Parcial 1",
  "peso_maximo": 50,
  "orden": 1,
  "es_grupal": false,
  "fecha": "2026-04-15T10:00:00",
  "descripcion": "Primer parcial"
}
```
**Response 201:** `InstanciaEvaluacionRead`

### GET `/instancia-cursado/{instancia_cursado_id}` - Evaluaciones de una instancia de cursado
### POST `/filters` - Filtros avanzados
### PUT `/{instancia_id}` - Actualizar
### DELETE `/{instancia_id}` - Eliminar (204)

---

## 8. Admin - Instancias de Examen

**Prefijo:** `/v2/admin/instancias-examen`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/`
Crear instancia de examen. **Body:**
```json
{
  "materia_id": 1,
  "nombre": "Febrero 2026 - Programacion 1",
  "fecha_inicio_inscripcion": "2026-01-15T00:00:00",
  "fecha_fin_inscripcion": "2026-02-10T23:59:59",
  "fecha_examen": "2026-02-15T09:00:00",
  "hora": "09:00",
  "salon": "Salon A",
  "modalidad": "presencial",
  "tipo": "ordinario",
  "habilitado": true
}
```
**Response 201:** `InstanciaExamenRead`

### GET `/materia/{materia_id}` - Instancias de examen de una materia
### GET `/activas` - Instancias con inscripcion abierta
### GET `/{instancia_id}` - Obtener por ID
### PUT `/{instancia_id}` - Actualizar
### DELETE `/{instancia_id}` - Eliminar
### POST `/{instancia_id}/profesores` - Asignar profesor (`{ "docente_id": 3 }`)
### GET `/{instancia_id}/inscriptos` - Lista de inscriptos al examen

---

## 9. Admin - Politicas de Calificacion

**Prefijo:** `/v2/admin/politicas-calificacion`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/`
Crear politica. **Body:**
```json
{
  "nombre": "Estandar 100 puntos",
  "escala_max": 100,
  "umbral_exoneracion": 86,
  "umbral_examen": 25,
  "umbral_aprobacion": 60,
  "cantidad_instancias": 2,
  "tipo_nota": "numerica",
  "descripcion": "Politica estandar del CTC"
}
```
**Response 201:** `PoliticaCalificacionRead`

### GET `/{politica_id}` | GET `/` | POST `/filters` | PUT `/{id}` | DELETE `/{id}`

**Logica de estados automaticos:**
- `nota_curso >= 86` → `exonerado`
- `nota_curso >= 25 y < 86` → `a_examen`
- `nota_curso < 25` → `reprobado`

---

## 10. Admin - Politicas de Examen

**Prefijo:** `/v2/admin/politicas-examen`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/`
Crear politica de examen. **Body:**
```json
{
  "nombre": "Estandar examen",
  "nota_maxima": 100,
  "umbral_aprobacion": 60,
  "max_oportunidades": 5
}
```
**Response 201:** `PoliticaExamenRead`

**Nota:** `max_oportunidades` controla cuantas veces un alumno puede rendir el examen de una materia. Default: 5. Cuando se agotan las oportunidades y la ultima es reprobada, la materia pasa a estado `reprobado` automaticamente.

### GET `/{politica_id}` | GET `/` | POST `/filters` | PUT `/{id}` | DELETE `/{id}`

---

## 11. Admin - Previaturas

**Prefijo:** `/v2/admin/previaturas`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/`
Crear previatura. Valida ciclos y que ambas materias pertenezcan al mismo programa.
- **Body:**
```json
{
  "materia_id": 2,
  "materia_previa_id": 1,
  "tipo_requerido": "aprobada"
}
```
- **Response 201:** `PreviaturaRead`
- **Error 400:** `"Se detectó un ciclo de previaturas"` / `"Las materias deben pertenecer al mismo programa"`

### GET `/materia/{materia_id}`
Previaturas de una materia con nombres.
- **Response 200:**
```json
[
  {
    "id": 1,
    "materia_id": 2,
    "materia_nombre": "Programacion 2",
    "materia_previa_id": 1,
    "materia_previa_nombre": "Programacion 1",
    "tipo_requerido": "aprobada"
  }
]
```

### GET `/malla/{programa_id}`
Malla curricular completa agrupada por semestre con previaturas.

### DELETE `/{previatura_id}` - Eliminar (204)

---

## 12. Admin - Periodos de Inscripcion

**Prefijo:** `/v2/admin/periodos-inscripcion`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/`
Crear periodo de inscripcion. **Body:**
```json
{
  "nombre": "Inscripciones Marzo 2026",
  "fecha_inicio": "2026-02-15T00:00:00",
  "fecha_fin": "2026-03-15T23:59:59",
  "anio_lectivo": 2026,
  "habilitado": true
}
```
**Response 201:** `PeriodoInscripcionMateriaRead`

### GET `/{id}` | GET `/` | POST `/filters` | PUT `/{id}` | DELETE `/{id}`

---

## 13. Admin - Docentes por Materia

**Prefijo:** `/v2/admin/docentes-materia`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/`
Asignar docente a instancia de cursado. **Body:**
```json
{
  "docente_id": 3,
  "instancia_cursado_id": 5,
  "rol_docente": "titular"
}
```
**Response 201:** `DocenteMateriaRead`

### GET `/instancia-cursado/{instancia_cursado_id}` - Docentes asignados
### PUT `/{asignacion_id}` - Cambiar rol
### DELETE `/{asignacion_id}` - Desasignar (204)

---

## 14. Admin - Inscripciones

**Prefijo:** `/v2/admin/inscripciones`
**Auth:** Bearer Token (rol `docente` o `administrativo`)

### POST `/inscribir`
Inscripcion manual (admin, salta validacion de periodo). **Body:**
```json
{
  "usuario_id": 1,
  "instancia_cursado_id": 5
}
```
**Response 200:** `InscripcionMateriaRead`

### POST `/marcar-inasistencia`
Marcar alumno como perdido por inasistencia. **Body:**
```json
{ "inscripcion_id": 1, "motivo": "Supero las faltas maximas" }
```

### POST `/marcar-abandono`
Marcar alumno como abandono. **Body:**
```json
{ "inscripcion_id": 1, "motivo": "No se presento mas" }
```

### GET `/escolaridad/{alumno_id}?programa_id={id}`
Consultar escolaridad de cualquier alumno.
- **Params:** `alumno_id` (path, int) - es el id del **perfil de alumno**, no el de usuario
- **Query params:** `programa_id` (int, requerido)
- **Response 200:** identica a
  [`GET /v2/portal/estudiante/mi-escolaridad`](#get-mi-escolaridadprograma_idid)
  (mismo servicio). Ver ahi la forma completa y las notas para el cliente.

### GET `/verificar-egreso/{alumno_id}?programa_id={id}`
Verificar si un alumno cumple requisitos de egreso.
- **Params:** `alumno_id` (path, int) - id del perfil de alumno
- **Response 200:** identica a
  [`GET /v2/portal/estudiante/mi-egreso`](#get-mi-egresoprograma_idid)
  (mismo servicio). Ver ahi la forma completa y las notas para el cliente.

### POST `/{inscripcion_id}/revalidar`
Revalidar (convalidar) una materia. Cambia estado a `revalidada`, otorga creditos.
- **Body:**
```json
{
  "motivo": "Aprobada en UTEC - 2025"
}
```
- **Response 200:** `InscripcionMateriaRead` con `estado: "revalidada"`, `motivo_revalida` y `creditos_obtenidos`
- **Error 400:** `"La inscripcion no esta en estado cursando o a_examen"`

---

## 15. Admin - Examenes

**Prefijo:** `/v2/admin/examenes`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/inscribir`
Inscribir estudiante a examen (sin validar periodo). **Body:**
```json
{
  "inscripcion_materia_id": 1,
  "instancia_examen_id": 3
}
```
**Response 201:** `InscripcionExamenRead`

### POST `/{inscripcion_examen_id}/calificar`
Calificar examen. **Body:**
```json
{ "nota_examen": 78.5 }
```
**Response 200:** `InscripcionExamenRead` - Si aprueba, la inscripcion materia pasa a `aprobado`

### POST `/{inscripcion_examen_id}/ausente`
Marcar como ausente. La materia queda en `a_examen`.

### GET `/instancia/{instancia_examen_id}` - Lista de inscripciones a examen

### DELETE `/{inscripcion_examen_id}` - Desinscribir (solo estado `inscripto`, soft-delete con estado `baja`) (204)

---

## 16. Admin - Documentos

**Prefijo:** `/v2/admin/documentos`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/{usuario_id}`
Subir documento para cualquier usuario. **multipart/form-data:**
- `archivo` (file, requerido): Archivo PDF o imagen
- `tipo` (string, requerido): Tipo de documento (`formula_69a`, `escolaridad`, `constancia_convenio`, `cedula`, `titulo`, `otro`)
- `descripcion` (string, opcional): Descripcion del documento

**Response 201:**
```json
{
  "id": 1,
  "usuario_id": 5,
  "tipo": "escolaridad",
  "nombre_original": "escolaridad.pdf",
  "mime_type": "application/pdf",
  "tamanio_bytes": 45000,
  "descripcion": "Escolaridad 2026",
  "subido_por": 1,
  "fecha_subida": "2026-05-17T10:00:00",
  "activo": true,
  "id_rastreo": "uuid..."
}
```

### GET `/{usuario_id}`
Listar documentos de un usuario. **Query params:**
- `tipo` (opcional): Filtrar por tipo de documento

**Response 200:** `DocumentoUsuarioRead[]`

### GET `/descargar/{documento_id}`
Descargar cualquier documento. **Response 200:** Archivo binario

### DELETE `/{documento_id}`
Eliminar documento (soft delete). **Response 204**

---

### Endpoints de documentos en Portal Estudiante

**Prefijo:** `/v2/portal/estudiante`

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/documentos` | Subir documento propio (multipart/form-data: archivo, tipo, descripcion) |
| GET | `/mis-documentos?tipo=X` | Listar mis documentos (filtro opcional por tipo) |
| GET | `/documentos/{id}` | Descargar mi documento |

### Endpoints de documentos en Portal Docente

**Prefijo:** `/v2/portal/docente`

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/documentos` | Subir documento propio |
| GET | `/mis-documentos?tipo=X` | Listar mis documentos |
| GET | `/documentos/{id}` | Descargar mi documento |

**Tipos de documento disponibles:** `formula_69a`, `escolaridad`, `constancia_convenio`, `cedula`, `titulo`, `otro`

**Procesamiento automatico de imagenes:**
- Conversion a WebP (85% calidad)
- Correccion de rotacion EXIF
- Redimensionado a max 2000px
- PDFs se guardan sin modificar

---

## 17. Admin - Usuarios

**Prefijo:** `/v2/admin/usuarios`
**Auth:** Bearer Token (rol `administrativo`)

### POST `/manual`
Crear usuario y su perfil sin cuenta de Google. Sirve para ponentes de una charla
puntual o asistentes que deben quedar registrados sin necesitar login. Si esa
persona luego inicia sesion con Google usando el mismo email, el sistema vincula
la cuenta automaticamente. Se crea con `activo=false` (sin acceso al portal).

- **Body:** `email` es opcional (un oyente puede no tener cuenta institucional).
  Del bloque `perfil` solo se leen los campos que aplican al `rol` enviado.
```json
{
  "nombre": "Ana",
  "apellido": "Gomez",
  "rol": "docente",
  "email": "ponente@ejemplo.com",
  "documento": "1234567-8",
  "telefono": "099111222",
  "email_personal": "ana@gmail.com",
  "perfil": {
    "cargo": "titular",
    "dedicacion": "tiempo_completo",
    "especialidad": "Programacion",
    "carga_horaria_semanal": 20
  }
}
```

### GET `/alumnos`
Lista paginada de alumnos para el dashboard.
- **Query params:** `page` (default 1), `per_page` (default 50, max 200),
  `search` (nombre, apellido o email), `activo` (bool)
- **Response 200:** `{ "items": [...], "total": 120, "page": 1, "per_page": 50, "pages": 3 }`

### GET `/docentes`
Lista paginada de docentes para el dashboard.
- **Query params:** `page`, `per_page`, `search`, `activo`, `activo_docente`
- **Response 200:**
```json
{
  "items": [
    {
      "id": 1,
      "usuario_id": 3,
      "nombre": "Maria",
      "apellido": "Lopez",
      "email": "profe@ctcsalto.edu.uy",
      "documento": "1234567-8",
      "telefono": "099111222",
      "activo": true,
      "activo_docente": true,
      "tiene_login": true,
      "cargo": "titular",
      "dedicacion": "tiempo_completo",
      "especialidad": "Programacion",
      "carga_horaria_semanal": 20
    }
  ],
  "total": 12,
  "page": 1,
  "per_page": 50,
  "pages": 1
}
```

**Los dos filtros de actividad no son lo mismo:**
- `activo` -> `usuario.activo`: si puede iniciar sesion.
- `activo_docente` -> `profesor.activo`: si dicta actualmente.

Para listar los docentes que estan dictando hoy, usa `activo_docente=true`.

### PATCH `/docentes/{usuario_id}/activo`
Activar o desactivar a un docente. Cambia **solo** `profesor.activo`: el docente
desactivado sigue pudiendo iniciar sesion y consultar su historico. Para cortar
el acceso al sistema hay que cambiar `usuario.activo`.

- **Body:** `{ "activo": false }`
- **Response 200:** `ProfesorRead`
- **Error 404:** `"No existe perfil de docente para el usuario {id}"`

### GET `/docentes/{usuario_id}/historico-materias?anio_lectivo={anio}`
Historico de materias dictadas por cualquier docente. Misma respuesta que
`/v2/portal/docente/mi-historico-materias`, pero para el docente indicado.
- **Params:** `usuario_id` (path, int) - id de **usuario**, no de profesor
- **Error 404:** si ese usuario no tiene perfil de docente

### GET `/docentes/{usuario_id}/historico-examenes?anio={anio}`
Historico de examenes tomados por cualquier docente. Misma respuesta que
`/v2/portal/docente/mi-historico-examenes`.
- **Params:** `usuario_id` (path, int) - id de **usuario**, no de profesor

---

## 18. Enums y valores posibles

### RolUsuario
`"estudiante"` | `"docente"` | `"administrativo"`

### EstadoInscripcionMateria
`"cursando"` | `"exonerado"` | `"a_examen"` | `"aprobado"` | `"reprobado"` | `"perdido_inasistencia"` | `"abandono"` | `"revalidada"`

### EstadoInscripcionExamen
`"inscripto"` | `"aprobado"` | `"reprobado"` | `"ausente"` | `"baja"`

### TipoPrograma
`"carrera"` | `"curso_corto"` | `"taller"` | `"diploma"`

### AreaPrograma
`"administracion"` | `"comunicacion"` | `"cultura"` | `"general"` | `"informatica"`

### TipoPreviatura
`"aprobada"` | `"exonerada"`

| Tipo requerido | Estados de la materia previa que lo cumplen |
|---|---|
| `aprobada` | `aprobado`, `exonerado`, `revalidada` |
| `exonerada` | `exonerado`, `revalidada` |

`revalidada` cumple **ambos** tipos: una materia convalidada de otra institucion
otorga creditos y cuenta para el egreso, asi que tambien habilita la siguiente. Y
como el alumno no puede volver a cursar lo que ya revalido, exigirle la
exoneracion lo dejaria trabado sin salida — el control academico ya lo hizo
administracion al otorgar la revalida.

Con varias inscripciones en la materia previa (recursadas) alcanza con que
**alguna** llegue al estado requerido.

### RolDocente
`"titular"` | `"adjunto"` | `"asistente"`

### EstadoInstanciaCursado
`"planificada"` | `"en_curso"` | `"finalizada"` | `"cancelada"`

### EstadoInscripcionPrograma
`"activa"` | `"suspendida"` | `"completada"` | `"baja"`

### ModalidadExamen
`"presencial"` | `"virtual"` | `"hibrido"`

### TipoExamen
`"ordinario"` | `"extraordinario"`

### EstadoInstanciaExamen
`"programado"` | `"en_curso"` | `"finalizado"` | `"cancelado"`

### TipoNota
`"numerica"` | `"letra"` | `"escala_custom"`

### CargoDocente
`"titular"` | `"interino"` | `"contrato"`

### DedicacionDocente
`"tiempo_completo"` | `"medio_tiempo"` | `"horas"`

### TipoDocumento
`"formula_69a"` | `"escolaridad"` | `"constancia_convenio"` | `"cedula"` | `"titulo"` | `"otro"`

---

## Errores comunes

Todos los errores siguen este formato:
```json
{
  "detail": "Mensaje descriptivo del error"
}
```

| Codigo | Significado |
|--------|-------------|
| 400 | Validacion fallida (previaturas, periodo, datos invalidos) |
| 401 | Token invalido, expirado o revocado |
| 403 | Rol insuficiente o recurso no propio |
| 404 | Recurso no encontrado |
| 422 | Error de validacion de Pydantic (campos faltantes o tipos incorrectos) |

---

## Diagrama de Entidades

**Ver archivo `diagrama_entidades.html`** — Diagrama interactivo con las 22 tablas, relaciones y campos. Abrir en Chrome para arrastrar tablas y hacer zoom. Campos nuevos de Fases 1+2 marcados en verde.

---

*Generado: Mayo 2026 - CTC Salto*
