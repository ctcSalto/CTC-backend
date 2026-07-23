# Pendientes de producción

> **Estado (Julio 2026):** las migraciones 1–12 (portal académico bedelía: tablas
> v2, faltas, previaturas, columnas de usuario, documentos, Fase 2, notificaciones,
> videoUrl en testimonios) ya se aplicaron. Quedan **dos migraciones pendientes** de
> aplicar en producción: la 13 (refactor alumno/profesor) y la 14 (índices de fecha).
> El histórico de las aplicadas está al final, como referencia de rollback.

---

## PENDIENTE de aplicar en producción

```bash
# 1. DATABASE_URL apuntando a produccion (puerto 5432)
# 2. Correr alembic current para confirmar en que revision esta
# 3. alembic upgrade head
```

### 13. `9a3f7c1e5b28_refactor_alumno_profesor` — Sujeto académico: alumno/profesor

> ⚠️ **Esta migración todavía NO corrió contra un Postgres real.** Antes de aplicarla
> en producción, correrla sobre una copia de la base de prod y verificar el checklist.
> Usa `gen_random_uuid()` (requiere PG13+). Alembic la envuelve en una transacción,
> así que si aborta no deja la base a medias.

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

### Auth / tokens (nuevas, opcionales)
```bash
# Duracion de los tokens del portal v2, separada de la del CMS v1.
# Si no se setea, cae a ACCESS_TOKEN_EXPIRE_MINUTES (compartida) o al default 480.
V2_ACCESS_TOKEN_EXPIRE_MINUTES=480
```

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
