# Portal Academico v2 — Guia de endpoints para frontend

Cubre los endpoints trabajados en esta tanda: escolaridad, disponibilidad de
materias y examenes, egreso, e historico y estado de los docentes.

Todo lo que sigue es HTTP y JSON. No hay codigo de framework: los ejemplos usan
`fetch` y los tipos son TypeScript plano, que sirve igual con cualquier stack.

---

## 1. Antes de empezar

### El backend tiene que tener V2 habilitado

Las rutas `/v2/*` solo se montan si el backend corre con `V2_ENABLED=true`. Si
esta en `false`, **todos** los endpoints v2 responden `404` — no es un error de
tu request. Si te da 404 en todo `/v2`, avisale al backend antes de debuguear.

### Autenticacion

Google OAuth con dominio restringido a `@ctcsalto.edu.uy`, y despues un JWT que
va en todas las requests.

| Paso | Endpoint |
|---|---|
| 1. Redirigir al usuario | `GET /v2/auth/google/login?redirect_to={tu_url}` |
| 2. Google vuelve al callback | `GET /v2/auth/google/callback` (lo maneja el backend) |
| 3. Verificar sesion | `GET /v2/auth/me` |
| 4. Cerrar sesion | `POST /v2/auth/logout` |

El `redirect_to` tiene que estar en la whitelist `OAUTH_ALLOWED_REDIRECT_ORIGINS`
del backend, si no lo rechaza. Todas las demas requests llevan:

```
Authorization: Bearer <token>
```

### Los tres ids que no hay que confundir

Esta es la fuente de bugs mas comun de esta API.

| Id | Que es | Donde sale |
|---|---|---|
| `usuario_id` | La persona. Lo identifica el JWT | `GET /v2/auth/me` → campo `id` |
| `alumno_id` | El perfil academico de estudiante | `GET /v2/portal/estudiante/mi-perfil` → `perfil_alumno.alumno_id` |
| `profesor_id` | El perfil academico de docente | `GET /v2/portal/docente/mi-perfil` → `perfil_profesor.profesor_id` |

**Son secuencias distintas y pueden dar el mismo numero por casualidad.** Un
`alumno_id` usado donde va un `usuario_id` no falla con error: devuelve los datos
de otra persona o una respuesta vacia.

Regla practica:
- Los endpoints del **portal** (`/v2/portal/*`) no piden ningun id: sale del token.
- Los de **admin sobre alumnos** piden `alumno_id`.
- Los de **admin sobre docentes** piden `usuario_id`, y el backend resuelve el perfil.

### Errores

Todos los errores vienen como `{"detail": "..."}`, salvo el `422`, donde `detail`
es un array de objetos de validacion — no lo muestres crudo en pantalla.

| Codigo | `detail` | Cuando | Que hacer |
|---|---|---|---|
| `403` | `Not authenticated` | Falta el header `Authorization` | Mandar a login |
| `403` | `Invalid authentication credentials` | El header no dice `Bearer` | Bug del cliente |
| `401` | `Error de autenticacion` | Token invalido, expirado o revocado | Refrescar / mandar a login |
| `401` | `Usuario no encontrado` | El email del token no existe en la base | Mandar a login |
| `403` | `Usuario inactivo` | Usuario dado de baja | Mostrar mensaje, no reintentar |
| `403` | `Rol de estudiante requerido` | Rol equivocado para ese endpoint | Mostrar mensaje, no reintentar |
| `403` | `No estas inscripto en este programa` | Pediste un `programa_id` ajeno | Mostrar mensaje |
| `404` | `No tenes perfil de alumno...` | Usuario sin perfil academico | Derivar a administracion |
| `422` | array de validacion | Falta un query param o tiene tipo invalido | Bug del cliente |

**Ojo con el 403 sin token.** Es un comportamiento de FastAPI: la falta del header
da `403`, no `401`. Si tu interceptor de "sesion expirada" mira solo el `401`, se
le escapa el caso mas comun.

```ts
async function api<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : res.statusText;
    throw Object.assign(new Error(detail), { status: res.status });
  }
  return res.json();
}
```

---

## 2. Portal Estudiante

**Prefijo:** `/v2/portal/estudiante` · **Rol:** `estudiante`

Casi todos piden un `programa_id`. No lo hardcodees: sacalo de `/mis-programas`,
que devuelve los programas en los que el alumno tiene inscripcion activa. Si hay
mas de uno, ofrecele un selector.

```http
GET /v2/portal/estudiante/mis-programas
```
```json
[
  {
    "inscripcion_id": 8,
    "programa_id": 3,
    "nombre": "Analista en Informatica",
    "tipo": "carrera",
    "area": "informatica",
    "estado": "activa",
    "anio_ingreso": 2024,
    "fecha_inscripcion": "2024-02-10T09:15:00-03:00"
  }
]
```

---

### GET `/mi-escolaridad?programa_id={id}`

**Todas las materias del plan del programa**, agrupadas por semestre, esten
cursadas o no. Sirve directo para pintar la malla curricular con el progreso
encima: no hace falta cruzarla con el plan de estudios.

```json
{
  "alumno_id": 42,
  "programa_id": 3,
  "semestres": [
    {
      "semestre": 1,
      "materias": [
        {
          "inscripcion_id": 17,
          "materia_nombre": "Programacion 1",
          "materia_codigo": "P1",
          "semestre": 1,
          "anio_lectivo": 2025,
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

```ts
export interface EscolaridadMateria {
  inscripcion_id: number | null;   // null si estado === "sin_inscripcion"
  materia_nombre: string;
  materia_codigo: string | null;   // puede faltar, no lo uses como key
  semestre: number;
  anio_lectivo: number | null;     // null si estado === "sin_inscripcion"
  estado: EstadoMateria;
  nota_curso: number | null;
  nota_final: number | null;
  creditos_obtenidos: number;
  faltas: number;
}

export interface Escolaridad {
  alumno_id: number;
  programa_id: number;
  semestres: { semestre: number; materias: EscolaridadMateria[] }[];
  total_creditos: number;
  total_creditos_posibles: number;
}
```

**Cuatro cosas a tener en cuenta:**

1. **`semestres` es una lista ordenada, no un objeto indexado.** Es
   `[{semestre: 1, materias: [...]}]`, no `{"1": [...]}`. Si necesitas acceso por
   numero, indexalo vos:
   ```ts
   const porSemestre = new Map(esc.semestres.map(g => [g.semestre, g.materias]));
   ```
2. **Todas las filas tienen las mismas claves.** Las materias nunca cursadas traen
   `estado: "sin_inscripcion"` y los campos de inscripcion en `null` (o `0` en los
   contadores). No hace falta chequear si la clave existe, si su valor.
3. **Las recursadas se colapsan:** si el alumno curso la misma materia varias
   veces, viene **solo** la del `anio_lectivo` mas alto. Este endpoint **no sirve
   para mostrar historial de intentos**.
4. **`total_creditos_posibles` es todo el plan**, no lo que curso. Sirve directo
   para la barra de avance:
   ```ts
   const avance = esc.total_creditos_posibles > 0
     ? esc.total_creditos / esc.total_creditos_posibles
     : 0;
   ```

---

### GET `/materias-habilitadas?programa_id={id}`

Materias a las que el alumno **puede inscribirse ahora**, en el semestre activo.

El semestre activo lo define el periodo de inscripcion abierto del programa: de
ahi salen el año lectivo y el semestre, por eso no los mandas vos. Aplica las
mismas validaciones que el POST de inscripcion, asi que `puede_inscribirse` no
deberia contradecir al alta.

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
      "previaturas_faltantes": [],
      "excepciones_aplicadas": []
    }
  ]
}
```

Sin periodo abierto la respuesta es:

```json
{ "programa_id": 3, "periodo_inscripcion": { "abierto": false }, "materias": [] }
```

**Chequea `periodo_inscripcion.abierto` antes de interpretar una lista vacia.**
"No hay periodo de inscripcion abierto" y "no te queda nada por cursar" son
mensajes distintos para el usuario, y la respuesta los distingue.

**`semestre_plan` vs `semestre`:** el primero es la posicion de la materia en el
plan de estudios (1..N de la carrera); el segundo es el semestre calendario en que
se dicta esa instancia. No son lo mismo y pueden no coincidir.

**`motivos` es lo que mostras al usuario.** Acumula todo lo que impide
inscribirse: previaturas faltantes y cupo completo. `previaturas_faltantes` es el
subconjunto de previaturas, por si queres tratarlas aparte.

**`excepciones_aplicadas` es lo contrario:** previaturas que el alumno **debe**
pero que bedelia le exceptuo. Casi siempre viene vacio. Cuando no lo esta,
mostralo en la ficha de la materia, o el alumno ve habilitada una materia que
sabe que no le corresponde y lo lee como un error del sistema:

```json
"excepciones_aplicadas": [
  {
    "previatura_id": 7,
    "materia_previa_id": 1,
    "materia_previa": "Programacion 1",
    "motivo": "Autorizado por direccion, ultimo semestre de carrera"
  }
]
```

Sirve un cartel del tipo *"Cursas sin Programacion 1 por excepcion de bedelia:
{motivo}"*.

Ojo con un caso que va a llegar como reporte de bug si no lo contemplas: una
materia puede quedar bloqueada **aunque su previatura directa figure aprobada**.
Pasa cuando esa previatura se aprobo bajo excepcion y la deuda original sigue
abierta. El `motivo` lo explica (*"Programacion 2 esta aprobada por excepcion:
primero hay que regularizar sus propias previaturas"*); mostralo tal cual. Se
resuelve solo cuando el alumno aprueba la materia que debe.

Una materia aparece solo si se dicta en el semestre activo, con instancia en
estado `planificada` o `en_curso`. Se excluyen las que el alumno ya tiene
`aprobado`, `exonerado`, `revalidada` o `cursando`; una `reprobado` si aparece,
para recursar.

Para inscribirse, con el `instancia_cursado_id` de la fila:

```http
POST /v2/portal/estudiante/inscribirse-materia
Content-Type: application/json

{ "instancia_cursado_id": 5 }
```

---

### GET `/examenes-habilitados?programa_id={id}`

Examenes a los que el alumno puede inscribirse. Aplica todas las validaciones del
POST, no solo el plazo.

```json
[
  {
    "instancia_examen_id": 3,
    "inscripcion_materia_id": 1,
    "materia_id": 1,
    "materia_nombre": "Programacion 1",
    "materia_codigo": "P1",
    "nombre_examen": "Febrero 2026 - Programacion 1",
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

Solo aparecen materias en estado `a_examen` con instancias habilitadas y dentro
del plazo. `motivos` explica por que no se puede inscribir: oportunidades
agotadas, materia sin politica de examen configurada, ya inscripto, o alguno de
los dos topes de abajo.

`rendiciones_previas` cuenta las rendiciones consumidas — aprobado, reprobado o
ausente. Las bajas y las inscripciones pendientes no cuentan. Cuando llega a
`max_oportunidades`, el alumno tiene que recursar la materia.

#### Dos topes que hacen que un examen aparezca bloqueado

**Maximo 4 examenes por periodo.** El periodo es el **mes calendario** de
`fecha_examen`. El motivo que llega es:

> `"Ya estas anotado a 4 examenes en 07/2026. El maximo es 4 por periodo."`

**No dos examenes el mismo dia.** Aunque sean a distinta hora:

> `"Ya tenes un examen el 10/07/2026. No se puede rendir mas de uno por dia."`

Las dos cuentan las inscripciones que el alumno **ya tiene** y que no estan de
baja. Una baja libera el lugar; una rendida —aprobada, reprobada o ausente— lo
sigue ocupando, para que no se pueda pasar el tope rindiendo y volviendo a
anotarse dentro del mismo mes.

Dos consecuencias para la UI:

- Un examen puede pasar de habilitado a bloqueado **sin que el alumno toque esa
  fila**: le alcanza con anotarse a otro el mismo dia o completar el cuarto del
  mes. Si la pantalla muestra varios examenes a la vez, **recarga la lista
  despues de cada inscripcion exitosa** en vez de solo marcar la fila que se
  inscribio.
- Estos dos topes **no tienen excepcion**: ni bedelia los puede saltear. Es
  distinto del plazo de inscripcion, que admin si puede pasar por alto. No
  ofrezcas un "solicitar excepcion" para estos casos.

**Las previaturas no se validan aca, y es correcto:** para llegar a `a_examen` el
alumno tuvo que cursar la materia, y esa inscripcion ya las valido. No las
muestres como requisito en esta pantalla.

Para inscribirse:

```http
POST /v2/portal/estudiante/inscribirse-examen
Content-Type: application/json

{ "inscripcion_materia_id": 1, "instancia_examen_id": 3 }
```

---

### GET `/mi-egreso?programa_id={id}`

Progreso hacia el egreso del programa.

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

Una materia cuenta como cumplida si esta `aprobado`, `exonerado` o `revalidada`:
los tres otorgan creditos. `a_examen` **no** cuenta, el curso no esta cerrado.

**Las dos ramas del detalle tienen forma distinta.** `detalle_pendientes` trae
solo los datos de la materia; `detalle_aprobadas` agrega `estado`, `anio_lectivo`
y las notas. No las trates con el mismo componente sin chequear.

**Mira el `estado` antes de mostrar notas.** Una materia `revalidada` viene con
`nota_final` y `nota_curso` en `null` — no es un dato faltante, es que una
convalidacion de otra institucion no tiene nota. Mostrala como "Revalidada", no
como un guion vacio.

Con recursadas, el detalle reporta la inscripcion del `anio_lectivo` mas alto, y
los creditos se cuentan **una sola vez**.

`cumple` exige las dos cosas: llegar a `creditos_requeridos` **y** no tener
materias pendientes.

---

## 3. Portal Docente

**Prefijo:** `/v2/portal/docente` · **Rol:** `docente` o `administrativo`

### GET `/mi-perfil`

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

**Hay dos `activo` y significan cosas distintas:**

| Campo | Significa | Si esta en `false` |
|---|---|---|
| `activo` (raiz) | `usuario.activo`: acceso al sistema | No puede iniciar sesion |
| `perfil_profesor.activo` | `profesor.activo`: si dicta actualmente | Entra igual, pero no esta dictando |

Un profesor retirado queda con `perfil_profesor.activo: false` y `activo: true`,
para poder seguir consultando su historico. Si vas a mostrar un badge de
"activo/inactivo" en el perfil docente, el que corresponde es el de
`perfil_profesor`.

`perfil_profesor` es `null` si el usuario no tiene perfil de docente — pasa con un
administrativo, que este router tambien admite.

---

### GET `/mi-historico-materias?anio_lectivo={anio}`

Todas las materias que dicto, de la mas reciente a la mas antigua. A diferencia
de `/mis-materias`, el año es **opcional**: sin el parametro devuelve todos.

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

Viene ordenado por `anio_lectivo` descendente y despues por semestre, asi que
podes agrupar por año recorriendo la lista en orden. Devuelve `[]` si el usuario
no tiene perfil de profesor.

---

### GET `/mi-historico-examenes?anio={anio}`

Examenes en los que integro el tribunal, del mas reciente al mas antiguo. `anio`
es opcional y filtra por año de `fecha_examen`.

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

---

## 4. Admin

**Rol:** `administrativo` (la escolaridad y el egreso tambien aceptan `docente`)

### Escolaridad y egreso de cualquier alumno

```http
GET /v2/admin/inscripciones/escolaridad/{alumno_id}?programa_id={id}
GET /v2/admin/inscripciones/verificar-egreso/{alumno_id}?programa_id={id}
```

**Respuestas identicas** a `/mi-escolaridad` y `/mi-egreso` — mismo servicio,
mismo schema. Los tipos y los componentes se reusan tal cual.

Ese `{alumno_id}` es el id del **perfil de alumno**, no el de usuario. Sale de
`GET /v2/admin/usuarios/alumnos` (campo `id` del item; `usuario_id` es el otro).

### GET `/v2/admin/usuarios/docentes`

Lista paginada para el dashboard.

- **Query params:** `page` (default 1), `per_page` (default 50, max 200),
  `search` (nombre, apellido o email), `activo`, `activo_docente`

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

Los dos filtros de actividad no son lo mismo: `activo` es acceso al sistema,
`activo_docente` es si dicta actualmente. **Para listar los docentes que estan
dictando hoy, usa `activo_docente=true`.**

`id` es el `profesor_id`; `usuario_id` es el otro. Los endpoints de docentes de
esta seccion piden **`usuario_id`**.

### PATCH `/v2/admin/usuarios/docentes/{usuario_id}/activo`

```http
PATCH /v2/admin/usuarios/docentes/3/activo
Content-Type: application/json

{ "activo": false }
```

Cambia **solo** `profesor.activo`. El docente desactivado sigue pudiendo iniciar
sesion y ver su historico. Si en la UI esto se presenta como "dar de baja", aclara
que no corta el acceso: para eso hay que tocar `usuario.activo`.

- **200:** el perfil de profesor actualizado
- **404:** `"No existe perfil de docente para el usuario {id}"`

### Historico de cualquier docente

```http
GET /v2/admin/usuarios/docentes/{usuario_id}/historico-materias?anio_lectivo={anio}
GET /v2/admin/usuarios/docentes/{usuario_id}/historico-examenes?anio={anio}
```

Respuestas identicas a las del portal docente. Devuelven `404` si ese usuario no
tiene perfil de docente (a diferencia de las del portal, que devuelven `[]`).

### POST `/v2/admin/instancias-cursado`

Al crear una instancia de cursado hay un campo nuevo, **`semestre`**:

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

Es el semestre calendario en que se dicta, distinto de `materia.semestre` (la
posicion en el plan). Es opcional, pero **si lo dejas en `null`, esa instancia se
considera dictada en cualquier semestre** y aparece en `/materias-habilitadas`
sin importar el semestre activo. Si el formulario de alta no lo pide, el filtro
por semestre no discrimina nada.

---

## 5. Reglas de negocio que se ven en la UI

### Estados de una materia

| `estado` | Significado | Otorga creditos |
|---|---|---|
| `sin_inscripcion` | Materia del plan, nunca inscripta | — |
| `cursando` | Cursando ahora, sin cerrar | No (todavia) |
| `exonerado` | Aprobo por nota de curso, sin examen | Si |
| `a_examen` | Cerro el curso, debe rendir examen | No (todavia) |
| `aprobado` | Aprobada (curso corto o examen rendido) | Si |
| `reprobado` | No alcanzo la nota | No |
| `perdido_inasistencia` | Paso el limite de faltas | No |
| `abandono` | Marcada como abandono | No |
| `revalidada` | Convalidada de otra institucion | Si |

`sin_inscripcion` es un pseudo-estado que arman los endpoints de escolaridad;
**no existe en la base**. No lo mandes de vuelta en ningun request.

### Previaturas y excepciones

Una previatura exige que la materia anterior este en cierto estado:

| Tipo requerido | Estados que lo cumplen |
|---|---|
| `aprobada` | `aprobado`, `exonerado`, `revalidada` |
| `exonerada` | `exonerado`, `revalidada` |

`revalidada` cumple ambos tipos. Con varias inscripciones en la materia previa
(recursadas), alcanza con que **alguna** llegue al estado requerido.

#### Regla 1: no alcanza con la previatura directa

Para que una materia habilite a la siguiente, tiene que estar aprobada **y toda
su propia cadena de previaturas tiene que estar cumplida**.

Esto es lo unico contraintuitivo de todo el sistema, asi que vale la pena
entenderlo antes de escribir la UI: **una materia puede estar bloqueada aunque su
previatura directa figure como `aprobado`.**

Pasa cuando esa previatura se aprobo por una excepcion de bedelia y la deuda
original sigue abierta. Ejemplo real:

1. El alumno no tiene Programacion 1.
2. Bedelia le concede una excepcion y cursa Programacion 2.
3. Aprueba Programacion 2. Reprueba Programacion 1.
4. **Programacion 3 sigue bloqueada**, aunque su previatura (Programacion 2)
   figure aprobada, porque Programacion 1 sigue sin aprobar.
5. El dia que apruebe Programacion 1, Programacion 3 se habilita **sola**.

El backend lo explica en texto, dentro de `motivos`:

> `"Programacion 2 esta aprobada por excepcion: primero hay que regularizar sus
> propias previaturas"`

Mostralo tal cual. Si en vez de eso pones un generico *"no cumplis las
previaturas"*, el alumno mira la malla, ve Programacion 2 en verde, y lo reporta
como bug.

#### Regla 2: la excepcion habilita a inscribirse, nada mas

Bedelia puede permitirle a un alumno cursar una materia sin tener la previatura.
Eso habilita **esa inscripcion puntual** y no convalida la materia adeudada — de
ahi sale la regla 1.

Alcance de cada excepcion:

- **Por previatura puntual**, no por materia. Si una materia tiene dos
  previaturas y se exceptua una, la otra se sigue exigiendo.
- **Solo para el año lectivo** en que se otorgo. No se traslada al siguiente.

Cuando una materia aparece habilitada gracias a una excepcion, viene en
`excepciones_aplicadas`:

```json
"excepciones_aplicadas": [
  {
    "previatura_id": 7,
    "materia_previa_id": 1,
    "materia_previa": "Programacion 1",
    "motivo": "Autorizado por direccion, ultimo semestre de carrera"
  }
]
```

Casi siempre viene vacio. Cuando no lo esta, mostralo (*"Cursas sin Programacion
1 por excepcion de bedelia: {motivo}"*), o el alumno ve habilitada una materia
que sabe que no le corresponde y desconfia del sistema.

#### Que endpoint mirar

**Para saber si el alumno puede inscribirse, solo `/materias-habilitadas`.**
Aplica las mismas validaciones que el POST de inscripcion, asi que
`puede_inscribirse` no deberia contradecir al alta.

| Campo | Para que sirve |
|---|---|
| `puede_inscribirse` | el booleano; habilita o no el boton |
| `motivos` | todo lo que lo bloquea, en texto para mostrar |
| `previaturas_faltantes` | el subconjunto de `motivos` que son previaturas |
| `excepciones_aplicadas` | por que puede, cuando debe una previatura |

Para dibujar la malla con el estado del alumno en cada materia:

```http
GET /v2/portal/estudiante/programa/{programa_id}/previaturas
```

Ojo: ese endpoint devuelve **estructura y estado, sin veredicto**. Trae
`previaturas` y `estado_alumno` de cada materia, pero no sabe nada de la regla 1
ni de las excepciones. **No calcules "puede cursar" del lado del cliente
cruzando esos datos**: te va a dar distinto que el backend en los casos de
excepcion, que son justamente los que el alumno va a consultar.

Sirve para pintar el arbol de la carrera. El veredicto lo da
`/materias-habilitadas`.

### Fechas y zona horaria

Todas las fechas salen en `America/Montevideo`. Las de los periodos de
inscripcion vienen con offset (`-03:00`); las de examen e instancias de cursado
pueden venir sin offset — parsealas como hora local de Uruguay, no como UTC.

### Paginacion

Los listados de admin devuelven `{ items, total, page, per_page, pages }`. Los
demas endpoints devuelven la lista completa sin paginar.
