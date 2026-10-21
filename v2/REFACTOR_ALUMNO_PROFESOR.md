# Refactor: Alumno / Profesor como sujeto academico

**Fecha:** Julio 2026
**Rama:** `develop`
**Audiencia:** equipo de frontend + backend
**Estado:** implementado en `develop` — migracion `9a3f7c1e5b28_refactor_alumno_profesor`

---

## 1. El modelo conceptual (lo que hay que entender primero)

En el portal academico v2 hay una distincion que no siempre es obvia leyendo la API:

> **`Usuario` no es una cuenta de acceso. Es una persona.**

La cuenta de Google es un atributo *opcional* de esa persona (`usuario.google_id`, nullable).
Una persona puede existir en el sistema sin haber iniciado sesion nunca, y de hecho es un caso
de negocio real y frecuente:

- Un **oyente** que se inscribe a una charla: hay que registrar que asistio, pero no se le da
  cuenta institucional y nunca va a entrar al portal.
- Un **ponente** externo que dicta una charla puntual: tiene que figurar como docente de esa
  instancia, pero tampoco tiene cuenta.

Sobre esa persona se cuelgan **perfiles de rol**, que son tablas aparte:

```
                    ┌─────────────┐
                    │   Usuario   │  ← la PERSONA
                    │             │    nombre, apellido, documento,
                    │ google_id?  │    email, telefono, domicilio,
                    │ moodle_id?  │    fecha_nacimiento
                    └──────┬──────┘
                           │ 1:1 (opcional cada uno)
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌──────────┐    ┌───────────┐    ┌────────────────┐
    │  Alumno  │    │ Profesor  │    │ Administrativo │
    │          │    │           │    │                │
    │ fecha_   │    │ cargo,    │    │ departamento   │
    │ ingreso  │    │ dedicacion│    │                │
    └──────────┘    └───────────┘    └────────────────┘
```

**`Alumno` y `Profesor` son el sujeto academico.** Cuando el dominio dice "este alumno se
inscribio a esta materia", la entidad correcta es `Alumno`, no `Usuario`.

---

## 2. El problema actual

El modelo quedo **inconsistente**: unas entidades apuntan al perfil y otras a la persona.

| Entidad | Hoy apunta a | Deberia apuntar a |
|---|---|---|
| `InscripcionPrograma.alumno_id` | `alumno.id` | correcto |
| `InscripcionMateria.usuario_id` | `usuario.id` | **`alumno.id`** |
| `EquipoMiembro.usuario_id` | `usuario.id` | **`alumno.id`** |
| `DocenteMateria.docente_id` | `usuario.id` | **`profesor.id`** |
| `DocenteInstanciaExamen.docente_id` | `usuario.id` | **`profesor.id`** |

Es decir: para inscribirse a un **programa** el sistema pide un `Alumno`, pero para inscribirse
a una **materia** pide un `Usuario`. Dos caminos distintos para llegar al mismo estudiante, sin
nada que garantice que sean coherentes entre si.

Ademas, apuntar a `usuario.id` en una inscripcion permite estados invalidos a nivel base de
datos: nada impide inscribir a materia a un usuario cuyo rol es `ADMINISTRATIVO` y que no tiene
fila en `alumno`. Con la FK a `alumno.id`, ese error se vuelve imposible — lo garantiza el motor
de base de datos, no una validacion que alguien puede olvidarse de escribir.

---

## 3. Que cambia

Cuatro claves foraneas:

```
inscripcion_materia.usuario_id       →  inscripcion_materia.alumno_id      → alumno.id
equipo_miembro.usuario_id            →  equipo_miembro.alumno_id           → alumno.id
docente_materia.docente_id           →  docente_materia.profesor_id        → profesor.id
docente_instancia_examen.docente_id  →  docente_instancia_examen.profesor_id → profesor.id
```

---

## 4. Que NO cambia (y por que)

Esto es tan importante como lo anterior. No se trata de reemplazar `usuario` por `alumno` en
todos lados — hay lugares donde `Usuario` es exactamente la referencia correcta:

### `Calificacion.docente_id` → sigue apuntando a `usuario.id`, pero se renombra

Es un campo de **auditoria**: registra quien cargo la nota. Y bedelia (rol `ADMINISTRATIVO`)
tambien carga notas. Los administrativos no tienen fila en `profesor`, asi que apuntar esta FK
a `profesor.id` romperia la carga de notas por parte de administracion.

Se renombra a **`cargado_por_id`** porque el nombre viejo mentia: decia "docente" y podia estar
guardando un administrativo. Misma FK, nombre honesto.

### `DocumentoUsuario.usuario_id` y `subido_por` → siguen siendo `usuario.id`

La cedula y el titulo pertenecen a la **persona**, no al rol. Alguien que es docente y ademas
cursa una carrera no deberia tener que subir su documento dos veces.

### `NotificacionLog.usuario_id` → sigue siendo `usuario.id`

La notificacion necesita un canal de contacto (email, telefono), y eso vive en `Usuario`.

### `Alumno.usuario_id` → sigue siendo obligatorio (`NOT NULL`)

Esta es la decision de diseno menos obvia, asi que vale explicarla.

La alternativa seria hacerlo nullable, para que un oyente pueda ser un `Alumno` "suelto" sin
`Usuario`. **No lo hacemos**, porque obligaria a duplicar `nombre`, `apellido`, `documento`,
`telefono` y `fecha_nacimiento` dentro de `Alumno`. Y entonces, el dia que ese oyente se
matricula en serio y saca su cuenta `@ctcsalto.edu.uy`, quedan dos registros de la misma persona
que hay que fusionar a mano.

Con el diseno actual ese caso es trivial: la persona **ya existe** como `Usuario` (creado
manualmente, sin `google_id`), y "promoverla" es simplemente que inicie sesion. El callback de
OAuth la encuentra por email y le vincula la cuenta. Cero migracion de datos, cero fusion de
registros.

---

## 5. Impacto en la API

### Endpoints de admin — **cambia el contrato**

| Endpoint | Cambio |
|---|---|
| `POST /v2/admin/inscripciones/inscribir` | body: `usuario_id` → `alumno_id` |
| `GET /v2/admin/inscripciones/escolaridad/{usuario_id}` | path: → `/escolaridad/{alumno_id}` |
| `GET /v2/admin/inscripciones/verificar-egreso/{usuario_id}` | path: → `/verificar-egreso/{alumno_id}` |
| `POST /v2/admin/docentes-materia` | body: `docente_id` → `profesor_id` |
| `PUT /v2/admin/docentes-materia/{id}` | response: `docente_id` → `profesor_id` |
| `POST /v2/admin/instancias-examen/{id}/profesores` | body: `docente_id` → `profesor_id` |
| `POST /v2/admin/usuarios/manual` | `email` pasa a ser **opcional**; se agrega bloque `perfil` opcional |

Ademas, en cualquier response que incluya una calificacion, el campo `docente_id` pasa a
llamarse **`cargado_por_id`**.

### Endpoints del portal (`/v2/portal/estudiante/*`, `/v2/portal/docente/*`) — **request no cambia**

Estos endpoints derivan el sujeto del JWT, no de un parametro. El frontend **no tiene que
cambiar como los llama**. Lo unico que cambia son los campos que vienen de vuelta en las
respuestas: donde hoy lees `usuario_id`, vas a leer `alumno_id`.

### Regla practica para el frontend

> Cuando el dato es **academico** (una inscripcion, una nota, un equipo, una asignacion docente),
> el identificador es `alumno_id` o `profesor_id`.
> Cuando el dato es **de la persona** (perfil, documentos, notificaciones, contacto), es `usuario_id`.

`GET /v2/portal/estudiante/mi-perfil` ya devuelve ambos: el `id` del usuario y
`perfil_alumno.alumno_id`. Ese es el que hay que usar contra los endpoints academicos.

---

## 6. Alta de personas: como se crea un alumno

**No hay ni va a haber un `POST /alumnos` separado.** Un `Alumno` no puede existir sin su
`Usuario`, asi que crearlos por separado seria siempre un flujo de dos pasos con un estado
intermedio invalido.

El alta es un solo endpoint, ya existente:

```
POST /v2/admin/usuarios/manual        (requiere rol ADMINISTRATIVO)
```

Crea el `Usuario` y, segun el `rol` que se le pase, auto-crea el perfil correspondiente
(`Alumno`, `Profesor` o `Administrativo`) en la misma transaccion.

**Extension prevista:** hoy el endpoint crea el perfil vacio y hay que editarlo despues. Se le
va a agregar un bloque `perfil` opcional para poder mandar todo junto:

```jsonc
POST /v2/admin/usuarios/manual
{
  "email": "juan.perez@ejemplo.com",
  "nombre": "Juan",
  "apellido": "Perez",
  "documento": "12345678",
  "rol": "estudiante",
  "perfil": {                          // opcional, forma segun el rol
    "fecha_ingreso": "2026-03-01"
  }
}
```

Para `rol: "docente"` el bloque `perfil` acepta `cargo`, `dedicacion`, `especialidad`,
`carga_horaria_semanal`.

### Como distinguir quien tiene login

Los listados `GET /v2/admin/usuarios/alumnos` y `/docentes` devuelven un campo **`tiene_login`**
(booleano, es `google_id != null`). Eso permite mostrar en el dashboard quien es un alumno del
portal y quien es un registro administrativo sin acceso.

### Email opcional y activacion diferida

`usuario.email` ahora es **nullable**. Un oyente de una charla que no tiene cuenta institucional
ni email que queramos almacenar ya no obliga a inventar direcciones falsas. El constraint
`unique` se mantiene (Postgres admite multiples `NULL`), y `get_by_email()` tiene un guard para
que un `None` no matchee filas sin email.

Las personas creadas manualmente se dan de alta con **`activo=false`**: no tienen acceso al
portal. Cuando alguna de ellas inicia sesion con Google por primera vez:

1. El callback la encuentra por email
2. Se le guarda el `google_id` y se le completa el email si faltaba
3. Se la **activa** automaticamente

Un usuario que **ya** tenia `google_id` y esta inactivo fue desactivado a proposito por un
administrador: **no** se reactiva al iniciar sesion. Esa distincion es lo que hace que
desactivar una cuenta siga significando algo.

> Bug corregido de paso: `update_on_login()` nunca guardaba el `google_id` al vincular una
> cuenta creada manualmente. El vinculo se rehacia por email en cada login, `tiene_login` se
> quedaba en `false` para siempre en los dashboards, y con `activo=false` la persona hubiera
> quedado bloqueada de por vida.

### Un usuario sin email no recibe notificaciones

`_enviar_y_loguear()` es el unico punto de salida de emails y ahora chequea que haya direccion.
Si no la hay, omite el envio en silencio en lugar de romper el flujo academico que lo disparo
(por ejemplo, una inscripcion). No se registra en `notificacion_log` porque no hubo intento.

---

## 7. Decisiones cerradas

### Una persona con dos roles → dos cuentas de Google

`Usuario.rol` es un enum unico: una persona es `ESTUDIANTE`, `DOCENTE` **o** `ADMINISTRATIVO`,
no varios a la vez.

Ya se presento el caso real (una administrativa que se inscribio como alumna) y la decision
institucional fue **darle dos cuentas de Google separadas**: una como administrativa y otra como
alumna. Son dos `Usuario` distintos en el sistema, con perfiles distintos.

**Para el frontend:** el `rol` del JWT es la unica fuente de verdad para decidir que menu y que
permisos mostrar. No hay que contemplar interfaces multi-rol ni selectores de "actuar como".

### Moodle no maneja calificaciones

Moodle se usa para gestion de cursos e inscripciones. Las notas viven **exclusivamente** en este
portal. No hay sincronizacion de notas en ninguna direccion.

---

## 8. Por que ahora

El refactor toca ~80 referencias en servicios y rutas, mas una migracion con backfill. No es
gratis. Pero el frontend recien arranca: **este es el momento mas barato en que se puede cambiar
el contrato de la API.** Hacerlo dentro de dos semanas, con pantallas ya construidas contra
`usuario_id`, cuesta varias veces mas.

---

*Documento de refactor v2 — CTC Salto, Julio 2026*
