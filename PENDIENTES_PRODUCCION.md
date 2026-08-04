# Pendientes de producción

> **Estado (Julio 2026):** las migraciones 1–12 ya se aplicaron. Las **13, 14 y 15 se
> aplicaron y verificaron en DEVELOP** (ver abajo), pero **siguen pendientes en
> PRODUCCIÓN**. El histórico de las aplicadas está al final, como referencia de rollback.
>
> **Corrida en develop (13 + 14):** partió de `e578594a9f4b` y llegó a `b7e2c9f14a30`
> sin abortar. Verificado: las 5 columnas renombradas, 0 huérfanos, **0 filas perdidas**
> (6 inscripciones / 2 miembros de equipo / 1 asignación docente / 8 calificaciones /
> 12 usuarios intactos), backfill creó 2 alumnos y 1 profesor, `usuario.email` acepta
> NULL, los 8 índices presentes, y el ORM + el endpoint `/v2/portal/proximos-eventos`
> responden bien contra el esquema migrado para los tres roles.
>
> Esto era el dry-run contra un Postgres real que faltaba: la migración 13 ya no es
> código sin probar. Para producción vale el mismo checklist, con sus propios counts
> previos (prod tiene más datos que develop).

---

## 🔴 URGENTE — El scheduler NO corre en producción

**Verificado el 31/07/2026 contra producción:**

```bash
curl -s https://backend-backend-ctc.vtu0xl.easypanel.host/scheduler/status
# {"status":"error","error":"No module named 'apscheduler'"}
```

El módulo no está instalado en el servidor. **Ningún job programado corre desde el
4 de mayo de 2026**, fecha del commit `7c14b08` ("Add: portal academico v2 completo"),
que borró `apscheduler==3.11.2` de `requirements.txt` — con toda probabilidad al
regenerar el archivo desde un venv que no lo tenía.

Pasó desapercibido porque `main.py` atrapa el error y lo loguea como **"no crítico"**:

```
[WARN] [STARTUP] Error iniciando scheduler (no crítico): No module named 'apscheduler'
```

La app levanta sana (`/health` responde 200) con el scheduler muerto.

**Jobs caídos desde entonces:**

| Job | Frecuencia | Impacto |
|---|---|---|
| `supabase_keepalive` | Diario 00:30 | Existe **específicamente** para que Supabase no pause el proyecto free |
| `actualizar_fotos_perfil_moodle` | Domingos 02:00 | Fotos de perfil desactualizadas |
| `prefetch_analytics_data` | Cada 4 h | Analytics sin cache precalentado |
| `recordatorio_examenes` | Diario 08:00 | Ningún alumno recibió recordatorio de examen |
| `recordatorio_cierre_inscripcion` | Diario 09:00 | Ningún aviso de cierre de inscripción |

**Arreglo:** ya está en el repo (`apscheduler==3.11.2` y su transitiva `tzlocal==5.4.4`
restauradas en `requirements.txt`). **Solo tiene efecto al redeployar**, porque el
servidor instala desde ese archivo.

- [ ] Redeployar producción con el `requirements.txt` corregido
- [ ] Verificar: `curl -s https://backend-backend-ctc.vtu0xl.easypanel.host/scheduler/status`
      debe devolver `"status": "running"` con **7 jobs**
- [ ] Revisar el estado del proyecto en Supabase por si el keepalive ausente lo pausó
- [x] ~~Evaluar que el `except` de `main.py` no siga llamando "no crítico" a un scheduler
      caído~~ — **RESUELTO.** Ya no dice "no crítico": loguea un bloque de error
      inconfundible explicando qué queda sin correr, y **`GET /health` ahora expone el
      estado del scheduler**, que es donde el monitoreo lo va a ver.

  ```json
  "scheduler": { "estado": "corriendo", "error": null }
  ```

  `estado` distingue `corriendo` / `deshabilitado` (fuera de producción no arranca a
  propósito) / `error` / `sin_iniciar`. Se consulta el scheduler real en vez de asumir
  que "no hubo excepción" significa "está corriendo": en desarrollo `start_scheduler()`
  sale sin hacer nada y sin error, y un booleano habría reportado OK sin ningún job.

  **`status` sigue en `"OK"` aunque el scheduler falle**, a propósito: si devolviera
  error, el health check de Easypanel reiniciaría el contenedor en loop por algo que no
  impide servir la API.

---

## Estado de V2 en producción

**`V2_ENABLED=false` en producción** (verificado el 31/07/2026: `GET /v2/auth/me`
devuelve `404`, o sea que las rutas v2 no están montadas).

**Esto es intencional.** El portal académico todavía no se usa en producción; el
frontend está integrando contra el backend de **develop**. Se habilita cuando esté
todo listo.

Consecuencia práctica: **todos los arreglos de lógica de negocio de v2 son
preventivos, no incendios activos.** Nada de v2 está expuesto en producción hoy.
Los únicos problemas que golpean producción ahora mismo son de v1: el scheduler.

**Orden obligatorio para habilitar v2 en producción:**

1. Aplicar las migraciones 13, 14 y 15 en la BD de producción (5432)
2. Verificar el esquema con el checklist de cada migración
3. Recién entonces poner `V2_ENABLED=true` y redeployar

> ⚠️ Si se prende `V2_ENABLED` **antes** de aplicar las migraciones, la app crashea
> al importar los modelos v2 contra un esquema que no los soporta. El orden no es
> una recomendación.

---

## PENDIENTE de aplicar en producción

```bash
# 1. DATABASE_URL apuntando a produccion (puerto 5432)
# 2. Correr alembic current para confirmar en que revision esta
# 3. alembic upgrade head
```

### 13. `9a3f7c1e5b28_refactor_alumno_profesor` — Sujeto académico: alumno/profesor

> ✅ **Ya corrió y se verificó en develop** (Postgres real, sin pérdida de datos).
> Sigue pendiente en producción, donde hay más datos: correr los counts previos del
> checklist antes de aplicarla. Usa `gen_random_uuid()` (requiere PG13+, confirmado
> OK en develop). Alembic la envuelve en una transacción: si aborta, no deja la base
> a medias.

Cambia 4 claves foráneas para que las entidades académicas apunten al perfil y no a
la persona:
- `inscripcion_materia.usuario_id` → `alumno_id` (FK `alumno.id`)
- `equipo_miembro.usuario_id` → `alumno_id` (FK `alumno.id`)
- `docente_materia.docente_id` → `profesor_id` (FK `profesor.id`)
- `docente_instancia_examen.docente_id` → `profesor_id` (FK `profesor.id`)

Además:
- Renombra `calificacion.docente_id` → `cargado_por_id` (sigue apuntando a `usuario.id`:
  es auditoría, y bedelía también carga notas sin tener fila en `profesor`).
- `usuario.email` pasa a ser **nullable** (oyentes registrados sin cuenta institucional).
  El constraint unique se mantiene: Postgres admite múltiples NULL.
- **Backfill con creación de perfiles faltantes:** antes de resolver las FKs, crea las
  filas de `alumno`/`profesor` que falten para cualquier usuario referenciado. Si aún
  así queda alguna fila sin resolver, **aborta con RuntimeError** con la cantidad, en
  vez de dejar la tabla inconsistente.
- **Downgrade funcional**, salvo que existan usuarios sin email creados después del
  upgrade: en ese caso corta con un mensaje explícito.

**Cambios de comportamiento (no requieren migración):**
- `POST /v2/admin/usuarios/manual` acepta `email` opcional y un bloque `perfil` opcional.
- Los usuarios manuales se crean con `activo=false`. Al iniciar sesión con Google por
  primera vez se vinculan (se guarda `google_id`, se completa el email) y se activan.
  Un usuario que YA tenía `google_id` y está inactivo fue desactivado a propósito: **no**
  se reactiva.
- `update_on_login` ahora crea el perfil correspondiente si el rol cambió de OU.

**Checklist:**
- [ ] **ANTES de migrar:** contar usuarios referenciados sin perfil (cuántas filas creará el backfill):
  ```sql
  SELECT count(DISTINCT im.usuario_id) FROM inscripcion_materia im
    LEFT JOIN alumno a ON a.usuario_id = im.usuario_id WHERE a.id IS NULL;
  SELECT count(DISTINCT dm.docente_id) FROM docente_materia dm
    LEFT JOIN profesor p ON p.usuario_id = dm.docente_id WHERE p.id IS NULL;
  ```
- [ ] Verificar que no abortó: `SELECT count(*) FROM inscripcion_materia WHERE alumno_id IS NULL` debe dar 0
- [ ] `\d inscripcion_materia` tiene `alumno_id` (no `usuario_id`)
- [ ] `\d docente_materia` tiene `profesor_id` (no `docente_id`)
- [ ] `\d calificacion` tiene `cargado_por_id` (no `docente_id`)
- [ ] `\d usuario` — `email` acepta NULL
- [ ] **Avisar al frontend:** cambia el contrato de `POST /v2/admin/inscripciones/inscribir`,
  `GET /escolaridad/{id}`, `GET /verificar-egreso/{id}`, `POST /v2/admin/docentes-materia` y
  `POST /v2/admin/instancias-examen/{id}/profesores` (ver `v2/REFACTOR_ALUMNO_PROFESOR.md`)

### 14. `b7e2c9f14a30_indices_fechas_proximos_eventos` — Índices de fecha

Índices para el endpoint `GET /v2/portal/proximos-eventos`, que corre en cada carga de
la pantalla de inicio y filtra por fecha sobre tres tablas:
- `periodo_inscripcion_materia`: `fecha_inicio`, `fecha_fin`, `programa_id` (FK del join, sin índice antes)
- `instancia_examen`: `fecha_inicio_inscripcion`, `fecha_fin_inscripcion`, `fecha_examen`
- `instancia_cursado`: `fecha_inicio`, `fecha_fin`

Solo crea índices, no toca datos ni esquema de columnas. **Idempotente:** chequea si el
índice ya existe antes de crearlo (en dev `create_all` los crea con los mismos nombres).
SQL estándar, sin nada específico de Postgres. Impacto en datos existentes: **cero**.

**Checklist:**
- [ ] `\di ix_instancia_examen_fecha_examen` (y demás) existen tras `alembic upgrade head`
- [ ] `SELECT count(*) FROM pg_indexes WHERE indexname LIKE 'ix_%fecha%'` devuelve 8

### 15. `c1d2e3f4a5b6_semestre_instancia_y_profesor_activo` — Semestre de la instancia y actividad del docente

> ✅ **Ya corrió y se verificó en develop** (`b7e2c9f14a30` → `c1d2e3f4a5b6`).

Dos columnas para las consultas de disponibilidad del semestre activo y para poder
distinguir a un docente que dejó de dictar de uno sin acceso al sistema:

- `instancia_cursado.semestre` (int, **nullable**) — semestre calendario en que se dicta
  la instancia. Distinto de `materia.semestre`, que es la posición en el plan de estudios.
  `NULL` significa "no declarado", y esas instancias se consideran dictadas en cualquier
  semestre para no ocultar oferta ya cargada.
- `profesor.activo` (bool, NOT NULL, `server_default true`) — si el docente dicta
  actualmente. Los profesores existentes quedan activos por el default.

Impacto en datos existentes: **cero**. Una columna nullable y una con server_default;
no renombra ni borra nada.

**Verificado en develop:** `instancia_cursado.semestre` = `integer / YES / sin default`,
`profesor.activo` = `boolean / NO / true`, 1 profesor quedó activo, 3 instancias con
`semestre IS NULL` (la degradación esperada). Suite v2 completa: 193 tests en verde.

**Checklist:**
- [ ] `SELECT semestre FROM instancia_cursado LIMIT 1` no da error
- [ ] `SELECT count(*) FROM profesor WHERE activo` = total de profesores (default aplicado)
- [ ] **Empezar a cargar `instancia_cursado.semestre` en las instancias nuevas.** Si queda
      todo en NULL, el filtro por semestre activo de `/materias-habilitadas` no discrimina
      nada y se comporta como si no existiera.

---

### 16. `d2e3f4a5b6c7_excepciones_de_previatura` — Excepciones de previatura

> ✅ **Ya corrió y se verificó en develop** (`c1d2e3f4a5b6` → `d2e3f4a5b6c7`).

Tabla nueva `excepcion_previatura`: permiso de bedelía para que un alumno curse
una materia sin tener aprobada una previatura puntual. **Tabla nueva, impacto en
datos existentes: cero.**

Regla pedida por administración, con su ejemplo textual: si un alumno no tiene
Programación 1 y bedelía le permite cursar Programación 2, aprobar Programación 2
**no** lo habilita para Programación 3 mientras siga debiendo Programación 1. El
día que la apruebe, la cadena se completa y Programación 3 se habilita sola.

Eso **no se guarda en ningún lado**: sale de la regla de cumplimiento pleno, que
exige que toda la cadena de previaturas esté cumplida, no solo la previatura
directa. Por eso no hay ninguna columna nueva en `inscripcion_materia`, y por eso
el desbloqueo posterior es automático sin que nadie tenga que revisar nada.

Alcance de cada excepción, según lo definido con administración:
- **Por previatura puntual**, no por materia: si mañana se agrega otra previatura
  a esa materia, la excepción vieja no la cubre.
- **Solo para el año lectivo** en que se otorgó. No se traslada al siguiente.
- Motivo obligatorio, con registro de quién la otorgó y quién la revocó.

**Checklist:**
- [ ] `\d excepcion_previatura` existe con sus 4 foreign keys
- [ ] `SELECT count(*) FROM pg_indexes WHERE tablename='excepcion_previatura'` = 6

> **Ciclos de previaturas — resuelto.** `previatura_service.create` ahora
> recorre el grafo del programa y rechaza también los ciclos **indirectos**
> (A→B→C→A), no solo los directos. El error dice cuál es la cadena, para poder
> encontrar el arco a sacar en una malla grande. La guarda de visitados en la
> regla recursiva se mantiene igual, por si hay algún ciclo cargado antes de
> esta validación. Para descartarlo, contra la base de producción:
>
> ```bash
> python -m v2.scripts.verificar_ciclos_previaturas
> ```
>
> Solo lee. Sale con código 1 y lista las cadenas si encuentra alguno, así que
> se puede encadenar en el deploy.

---

## Verificación general post-deploy

- [ ] `alembic current` ANTES de `upgrade head` (confirmar revisión de partida)
- [ ] `alembic upgrade head` con DATABASE_URL de producción
- [ ] `/health` responde OK (la app levanta sin errores)
- [ ] Endpoint `GET /v2/portal/proximos-eventos` en Swagger (`/docs`)

---

## Variables de entorno

### Documentos (ya requerida en prod)
```bash
DOCUMENTOS_BASE_PATH=/var/ctc/documentos
DOCUMENTOS_MAX_SIZE_MB=10
```

### Notificaciones por email
```bash
N8N_EMAIL_WEBHOOK_URL=https://automatizaciones-n8n.vtu0xl.easypanel.host/webhook/webhook/ctc-email-send
```

### Control de rendiciones (opcional)
```bash
PLAZO_BAJA_EXAMEN_HORAS=72   # default 72
```

### Auth / tokens (opcional)
```bash
# Duracion de los tokens del portal v2, en minutos. Default: 480 (8 horas).
# Solo hace falta setearla para usar un valor distinto.
V2_ACCESS_TOKEN_EXPIRE_MINUTES=480
```

> **Ya no cae a `ACCESS_TOKEN_EXPIRE_MINUTES`.** Ese fallback existia para no
> romper entornos con una sola variable seteada, pero tenia el efecto de
> gobernar la sesion del portal con un valor pensado para el CMS: en develop,
> donde `ACCESS_TOKEN_EXPIRE_MINUTES=4000`, los tokens de alumnos y docentes
> duraban **66 horas**. Ahora v2 usa su propia variable o su propio default.
>
> `ACCESS_TOKEN_EXPIRE_MINUTES` sigue rigiendo **solo** al CMS v1 (default 30).
> Vale revisar aparte si 4000 minutos es lo que se quiere para las sesiones de
> administracion del sitio publico.

### Bootstrap del primer admin (nuevas)
```bash
# Reemplazan las credenciales que antes estaban hardcodeadas (admin@gmail.com/Admin@123).
# create-first-user responde 503 si no estan seteadas.
FIRST_ADMIN_EMAIL=
FIRST_ADMIN_PASSWORD=
FIRST_ADMIN_DOCUMENT=    # opcional
FIRST_ADMIN_PHONE=       # opcional
```

### Google OAuth 2.0
```bash
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=
GOOGLE_ALLOWED_DOMAIN=ctcsalto.edu.uy
# Whitelist anti open-redirect: origenes del frontend Next.js (NO la URL del backend)
OAUTH_ALLOWED_REDIRECT_ORIGINS=https://portal.ctcsalto.edu.uy,https://frontend-develop.vtu0xl.easypanel.host
```

---

## Deuda abierta de v2 (no bloquea el deploy, sí conviene resolver antes de habilitar)

Encontrado en la revisión de lógica de negocio del 31/07/2026. Nada de esto está
arreglado; se documenta para que no se pierda.

### Datos sucios en develop

- [x] ~~**Evaluaciones duplicadas en Programación 1**~~ — **RESUELTO 31/07/2026.** Había
  tres generaciones de evaluaciones: ev 1-4 (ya borradas antes, pero el snapshot de
  `insc=6` todavía las referencia), ev 5-8 y ev 9-12. Se borró el set 5-8 con sus 3
  calificaciones, 1 equipo y 1 miembro de equipo, en una transacción con guarda previa:
  0 calificaciones pertenecían a inscripciones abiertas. Quedan 4 evaluaciones sumando
  exactamente 100. Verificado después: 0 calificaciones huérfanas, 0 equipos huérfanos,
  0 calificaciones fuera del snapshot de su inscripción.
  > `insc=6` (APROBADO por examen) conserva un snapshot que apunta a las evaluaciones
  > 1-4, que ya no existen. Es daño previo e irreparable: esas evaluaciones se borraron
  > antes de esta sesión. Como la inscripción está cerrada, `_recalcular_estado` nunca
  > corre sobre ella y no molesta. Se deja como artefacto histórico en vez de reescribir
  > datos académicos.

### Reglas de negocio

- [x] ~~**Nadie valida que los `peso_maximo` sumen `nota_maxima`**~~ — **RESUELTO.**
  `InstanciaEvaluacionService` valida en `create` y en `update` que la suma de pesos
  activos no supere la `nota_maxima` de la política de la materia. En `update` se excluye
  el peso viejo de la evaluación editada para no contarlo dos veces.
- [x] ~~**Las evaluaciones grupales no propagan la nota**~~ — **RESUELTO.** Calificar una
  instancia `es_grupal` ahora aplica la nota a todos los integrantes del equipo y
  recalcula el estado de cada uno. Valida que el equipo pertenezca a esa evaluación y que
  el alumno la integre. Un equipo puede tener un solo integrante. Los integrantes con la
  materia ya cerrada se saltean sin abortar al resto.
- [x] ~~**La baja de un alumno de un programa no existe**~~ — **RESUELTO.**
  `InscripcionProgramaService.dar_de_baja()` + `POST /v2/admin/inscripciones/programa/{id}/baja`.
  Registra fecha y motivo (obligatorio), y por defecto cierra como abandono las materias
  EN CURSO **de ese programa** — las de otros programas no se tocan. Se puede desactivar
  con `cerrar_materias=false`. Conecta `notificar_baja_procesada`, que ya no está huérfana.
- [x] ~~**El docente no podía definir las evaluaciones de sus cursos**~~ — **RESUELTO.**
  Las cinco rutas de `/v2/admin/instancias-evaluacion` eran solo para administrativo, así
  que los parciales y pesos de cada semestre los tenía que cargar bedelía. Ahora crear,
  listar, editar y borrar aceptan **docente o administrativo**: el docente solo sobre las
  cursadas que dicta, bedelía sobre todas.
  > `POST /filters` queda solo para administrativo: es una consulta libre sobre todas las
  > cursadas y no hay forma de acotarla a las del docente que la llama.
  >
  > El prefijo sigue siendo `/v2/admin/...` para no romper lo que el frontend ya está
  > integrando; lo único que cambió es el rol requerido.

- [ ] **Materias sin política de examen**: "Base de Datos 1" no tiene `politica_examen_id`,
  así que sus alumnos no se pueden inscribir a examen (`inscribir_examen` los rechaza).
  Revisar si es intencional.
- [x] ~~**Programación 2 y Base de Datos 1 sin evaluaciones**~~ — **RESUELTO en develop
  con datos inventados.** Se cargó en las dos el plan estándar: Primer Parcial 25,
  Segundo Parcial 25, Obligatorio 30 (grupal) y Nota de clase 20 = 100. Los pesos
  replican los de Programación 1, que ya estaban en la base. **Son datos de develop:
  confirmar los pesos reales con la institución antes de producción.**
  > Efecto colateral atendido: `insc=55` y `insc=56` (ambas CURSANDO) se habían creado
  > cuando esas cursadas no tenían evaluaciones, así que quedaron con
  > `snapshot_instancias` vacío y **no se podían calificar nunca** —
  > `_recalcular_estado` corta antes de empezar con snapshot vacío. Se les cargó el
  > snapshot con el builder del propio servicio. Solo se tocaron inscripciones
  > CURSANDO y sin notas; `insc=5` (ABANDONO) se dejó como estaba.

### Comportamiento corregido

- [x] ~~**Una inscripción cerrada no se puede corregir**~~ — **RESUELTO.** Ahora se
  pueden corregir las notas de una inscripción cerrada por el curso (EXONERADO,
  APROBADO, REPROBADO) y el estado se recalcula solo. Aplica tanto a las notas por
  instancia como a la nota final directa, y en una evaluación grupal la corrección
  alcanza a todo el equipo.
  > **Tres casos siguen bloqueados a propósito**, porque no los decidió el curso:
  > `revalidada` (decisión administrativa), `perdido_inasistencia` (se corrige con las
  > faltas) y `abandono` (baja). Y una materia **aprobada rindiendo examen** tampoco se
  > edita por esta vía: recalcular desde las notas de curso pisaría el resultado del
  > examen y dejaría la inscripción a examen colgada. El error deriva a corregir la nota
  > del examen.
  >
  > Al reabrirse una inscripción (por ejemplo de REPROBADO a A_EXAMEN) se limpia
  > `fecha_cierre`; si sigue cerrada, se conserva la fecha original del cierre.

### Decisión de producto pendiente

- [ ] **Ni un administrativo puede forzar una inscripción sin previaturas.**
  `inscribir_materia` valida previaturas siempre; `skip_periodo=True` de la inscripción
  manual saltea **solo** el período. Es lo correcto según el requerimiento actual, pero
  si algún día bedelía necesita una excepción documentada, hoy no existe la palanca.

### Revisado el 31/07/2026 — documentos y CRUD

- [x] ~~**El MIME de los archivos subidos se tomaba del cliente**~~ — **RESUELTO.** El
  `content-type` de un multipart lo elige quien sube, así que la whitelist no validaba
  nada: se guardaban `.html` y `.php` declarando `application/pdf` (verificado
  ejecutando). Ahora se detecta el tipo real por las firmas del contenido y se rechaza
  si no coincide con lo declarado.
- [x] ~~**La extensión del archivo salía del nombre del cliente**~~ — **RESUELTO.** Sale
  del tipo detectado. Un nombre con barras (`a.b/../../evil`) terminaba en un
  `FileNotFoundError` sin manejar (500); nada escapaba del directorio base —lo bloqueaba
  el prefijo `{fecha}_{tipo}.` por accidente, no una validación— pero era frágil.
- [x] ~~**`DELETE /v2/admin/materias/{id}` tiraba 500 siempre**~~ — **RESUELTO.** El guard
  consultaba `InscripcionMateria.materia_id`, columna que dejó de existir cuando las
  inscripciones pasaron a colgar de `instancia_cursado`: era `AttributeError` con o sin
  inscripciones. Ahora navega el join, y además bloquea si la materia tiene instancias de
  cursado o participa en previaturas.
- [x] ~~**`DELETE /v2/admin/programas/{id}` fallaba con violación de FK**~~ — **RESUELTO.**
  Solo miraba materias; un programa sin materias pero con alumnos inscriptos o períodos
  cargados reventaba con un 500. Ahora da un mensaje claro.

**Autorización de documentos: correcta.** Las descargas de alumno y docente validan
`doc.usuario_id == current_usuario.id`; las de admin exigen rol administrativo.

### Revisado el 31/07/2026 — equipos, exámenes y auth

- [x] ~~**Un alumno podía integrar dos equipos de la misma evaluación**~~ — **RESUELTO.**
  La calificación es única por inscripción + evaluación, así que calificar el segundo
  equipo le pisaba la nota del primero, en silencio. Verificado ejecutando.
- [x] ~~**Se podían armar equipos con alumnos que no cursan la materia**~~ — **RESUELTO.**
  La nota grupal no les llegaba a ningún lado (no tienen inscripción donde escribirla) y
  el equipo mentía sobre quiénes lo integran. Ahora se valida antes de crear nada, así
  que un id inválido no deja el equipo a medio armar.
- [x] ~~**Borrar un equipo con notas dejaba las calificaciones huérfanas**~~ — **RESUELTO.**
  En Postgres habría sido una violación de FK (500); en SQLite pasaba en silencio.
- [x] ~~**Aprobar por examen dejaba otras inscripciones a examen pendientes**~~ —
  **RESUELTO.** Al aprobar la materia, las demás inscripciones en INSCRIPTO pasan a BAJA
  con fecha: si no, apuntaban a una materia cerrada, salían en las listas del docente y
  contaban como rendición al calificarlas. No afecta a otras materias del alumno, y las
  bajas no consumen oportunidades.

**`auth/` v2 está en buen estado.** El fail-open de la blacklist de Redis y el TTL
compartido con los tokens de v1 ya estaban corregidos por una auditoría previa. Los dos
controles de OAuth existen **y se ejecutan**: validación de dominio institucional en el
callback (vía claim `hd`, que las cuentas personales no traen) y whitelist anti
open-redirect sobre `redirect_to`.

### Clave de firma con default público — RESUELTO

`SECRET_KEY` cae al literal `"your-secret-key-change-in-production"` en **tres** lugares
(`v2/auth/security.py`, `database/services/auth/security.py`, `main.py`). Producción la
tiene configurada, así que nunca hubo problema activo, pero un despliegue futuro sin esa
variable habría arrancado normal firmando los JWT con una cadena publicada en el repo.

- [x] **`utils/config_guard.py`**: si `ENVIRONMENT=production` y `SECRET_KEY` falta o es
  el placeholder, la aplicación **no arranca** y el mensaje dice exactamente qué corregir.
  Se ejecuta al principio del lifespan, antes de tocar la base.

  No puede romper producción, donde la variable está seteada — verificado con tests que
  cubren ausente / vacía / placeholder / clave real, dentro y fuera de producción.

  Deliberadamente **no** valida el largo de la clave: una regla así podría rechazar una
  clave real corta y tirar abajo un despliegue que venía funcionando.

### Sin revisar

Con esto queda cubierto todo v2. **De v1 solo se miró el scheduler.**

---

## Seguridad — acción operativa pendiente

Ver `AUDITORIA_SEGURIDAD.md` para el detalle completo. La única que no se arregla con
código y hay que hacer en producción:

- [ ] **Rotar / eliminar el usuario `admin@gmail.com`** si se usó alguna vez para
  bootstrapear producción. La contraseña `Admin@123` estuvo hardcodeada en el repo y
  sigue siendo válida hasta que se rote. El código ya no la usa, pero eso no cambia la
  fila que pueda existir en la base.

---

## Google OAuth — Consola de Google Cloud

- [ ] Orígenes de JS autorizados de develop y producción
- [ ] URI de callback de develop: `https://backend-backend-ctc-develop.vtu0xl.easypanel.host/v2/auth/google/callback`
- [ ] `OAUTH_ALLOWED_REDIRECT_ORIGINS` con los orígenes del frontend Next.js

## Proxy inverso (Easypanel / Traefik)

El backend corre detrás de un proxy que termina SSL. Ya aplicado: `--proxy-headers` y
`--forwarded-allow-ips='*'` en `Procfile` + `ProxyHeadersMiddleware` en `main.py` (evita
el "Redirect URI Mismatch" de OAuth). Pendiente:
- [ ] Verificar que Google OAuth funciona en develop y en producción (redirección HTTPS)

---

## Rollback

- Refactor alumno/profesor (13): `alembic downgrade 9a3f7c1e5b28` → estado previo. Ojo:
  el downgrade corta si hay usuarios sin email creados después del upgrade.
- Índices (14): `alembic downgrade 9a3f7c1e5b28` los quita (no afecta datos).
- Semestre + profesor.activo (15): `alembic downgrade b7e2c9f14a30` quita las dos columnas.
  Se pierde el semestre cargado en las instancias; los datos académicos no se tocan.
- Fase 2 (rendiciones): `alembic downgrade 4d769166125d`
- Fases 1+2 completas: `alembic downgrade f3g4h5i6j7k8`
- videoUrl en testimony: `alembic downgrade bad9dad1cc40`
- Todo v2: `alembic downgrade 055950855a1a` (elimina todas las tablas v2)

---

## Notas

- Las tablas v2 coexisten con las v1 (`user`, `career`, `testimony`, `news`). No hay FK entre v1 y v2.
- **`alembic/env.py`:** faltaban imports de `Career`, `Testimony`, `News` en `target_metadata`,
  lo que hacía que `--autogenerate` las marcara como "removidas" (riesgo de DROP TABLE si se
  aceptaba sin revisar). Corregido. **Todo autogenerate futuro debe revisarse a mano** — el diff
  todavía puede traer ruido de tablas legacy (`author`, `profile`, `post`, `example`).

---

## Apéndice — Migraciones 1–12 (ya aplicadas, referencia histórica)

| # | Revisión | Qué hizo |
|---|---|---|
| 1 | `c80c0cfd30d6` | Crea las 15 tablas iniciales del portal académico |
| 2 | `d1a2b3c4d5e6` | Refactor: `alumno`, `profesor`, `administrativo_perfil`, `inscripcion_programa`, `instancia_cursado`, `instancia_examen`, `docente_instancia_examen`. DROP `periodo_examen` |
| 3 | `e2f3g4h5i6j7` | Faltas: `instancia_cursado.faltas_maximas`, `inscripcion_materia.faltas` |
| 4 | `f3g4h5i6j7k8` | Seed de previaturas (Analista Programador + Técnico en Gestión) |
| 5 | `a1b2c3d4e5f6` | Columnas en `usuario`: `email_personal`, `fecha_nacimiento`, `domicilio`, `eliminado`, `fecha_eliminacion`, `id_rastreo` |
| 7 | `4d769166125d` | Fase 1: tabla `documento_usuario` + enum `TipoDocumento` + columnas de planilla admin |
| 8 | `087c21eff7fd` | Fase 2: `max_oportunidades`, `numero_rendicion`, `motivo_revalida` |
| 9 | `b2c3d4e5f6g7` | Fase 5: tabla `notificacion_log` + `inscripcion_materia.notificacion_calificacion_enviada` |
| 10 | `4fd4c9f395dd` | Merge de heads (no-op, ordena el historial de Alembic) |
| 11 | `bad9dad1cc40` | Tabla `testimony_video` (intermedia, la 12 la elimina) |
| 12 | `e578594a9f4b` | Reemplaza `testimony_video` por `testimony.videoUrl` |

> (No hay migración 6 en la numeración original; el salto 5→7 viene del documento previo.)
