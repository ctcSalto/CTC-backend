# Auditoria de seguridad — Backend CTC

**Fecha:** Julio 2026
**Alcance:** v1 (CMS del sitio publico) + v2 (Portal Academico)
**Metodo:** revision de lectura sobre tres ejes: superficie expuesta, ciclo de vida de
identidad/acceso, y fallas silenciosas.

**Origen:** la auditoria arranco despues de que el refactor de alumno/profesor destapara dos
bugs de ciclo de vida (`update_on_login` no guardaba el `google_id`, y no creaba el perfil al
cambiar de rol). Ninguno estaba en la logica de negocio dificil: los dos vivian en caminos de
estado que nadie testeaba. Ese patron guio donde buscar.

---

## Resumen

| Severidad | Arreglado | Pendiente |
|---|---|---|
| Critico | 4 | 0 |
| Alto | 3 | 3 |
| Medio | 1 | 6 |
| Bajo | 0 | 6 |

---

## Ya arreglado

| # | Hallazgo | Sev. | Commit |
|---|---|---|---|
| 1 | `GET /reset-database` sin autenticacion: `drop_all()` de todas las tablas por GET | Critico | `5a27c05` |
| 2 | `POST /auth/register` con `require_admin_role` comentado y `rol` settable por el cliente: cualquiera se hacia admin en un request | Critico | `44caa5a` |
| 3 | 21 endpoints `/moodle/*` sin ninguna autenticacion (listar/crear/eliminar usuarios, cursos, inscripciones) | Critico | `44caa5a` |
| 4 | Credenciales de admin hardcodeadas en `create-first-user` (`admin@gmail.com` / `Admin@123`) | Critico | `44caa5a` |
| 5 | Blacklist de tokens v2 fallaba abierto: con Redis caido, todo token revocado volvia a ser valido | Alto | `5a27c05` |
| 6 | `GET /api/analytics/debug-env` exponia sin auth un preview de las credenciales de la service account | Alto | `44caa5a` |
| 7 | v1 no validaba el claim `system`: un token v2 servia en v1 para cualquier email de la tabla `user` | Alto | pendiente de commit |
| 8 | `POST /test/users` y `/debug-modules` con auth comentada o ausente | Medio | `44caa5a` |

**Cadena que existia:** `GET /reset-database` (vaciar la base) → `POST /auth/create-first-user`
(crear admin de credenciales publicas) → login. Toma de control completa en dos requests sin
autenticacion. Cortada en los puntos 1 y 4.

---

## Pendiente — Alto

### A1. La blacklist de v1 tambien falla abierto

**Donde:** `database/services/auth/security.py:82`

Es el mismo bug que se arreglo en v2, en el otro sistema. `verify_token()` hace
`cache_service.exists(blacklist_key, session)`, y `RedisService.exists()` atrapa sus propias
excepciones y devuelve `False` (`database/services/redis/redis.py:204-211`). O sea que "Redis
caido" y "el token no esta revocado" son indistinguibles.

**Impacto:** con Redis caido, todo token de v1 revocado vuelve a ser valido hasta expirar. El
logout deja de tener efecto.

**Fix propuesto:** el mismo que en v2 — verificar conectividad con `test_connection()` antes de
confiar en `exists()`, y responder 503 si no se puede consultar. Reusar `_redis_disponible()`.

**Riesgo del fix:** con Redis caido, v1 deja de autenticar. Es el comportamiento correcto, pero
conviene deployarlo sabiendo que ata la disponibilidad del CMS a la de Redis.

### A2. Sin rate limiting en `/auth/login`

**Donde:** `routes/auth.py:115`

No hay `slowapi` ni equivalente en el proyecto. Intentos ilimitados, sin bloqueo por usuario ni
por IP. bcrypt hace cada intento lento, pero no impide un ataque sostenido.

**Fix propuesto:** `slowapi` con limite por IP en `/auth/login`, `/auth/register` y
`/v2/auth/google/login`. Contador de intentos fallidos por usuario con bloqueo temporal.

### A3. Rotar las credenciales `admin@gmail.com` (accion operativa, no de codigo)

Si ese usuario se uso alguna vez para bootstrapear produccion, la contraseña `Admin@123` estuvo
publicada en el repositorio y sigue siendo valida. **Verificar si existe en la base de
produccion y rotar o eliminar.** El codigo ya no las hardcodea, pero eso no cambia lo que ya
esta en la base.

---

## Pendiente — Medio

### M1. `/careers/{career_id}` publico no filtra por `published`

**Donde:** `routes/career.py:730` → `database/services/carrer_service.py:277`

`get_career_by_id()` es identico a `get_career_by_id_admin()`: ninguno filtra por `published`.
El endpoint hermano `get_careers_in_list()` si lo hace correctamente.

**Impacto:** con IDs secuenciales, cualquiera enumera carreras en borrador — ofertas no
lanzadas, precios, fechas. Anula el workflow de publicacion.

**Riesgo del fix:** si el panel admin usa el endpoint publico en vez de `/careers/admin/{id}`,
agregar el filtro lo rompe. **Verificar consumidores antes de tocar.**

### M2. Placeholders doble-escapados en 8 templates de email

**Donde:** `v2/templates/email_templates.py` — las 28 llamadas a `_row()`

Los alumnos reciben emails que dicen literalmente `Nota del curso: {nota}`. Afecta a
`inscripcion_materia`, `inscripcion_examen`, `recordatorio_examen`, `apertura_inscripcion`,
`apertura_examen`, `calificacion_disponible`, `exoneracion` y `baja_procesada`.

Los tests `TestTemplates::test_template_*` ya asertan el comportamiento correcto y hoy fallan
por esto. Detalle completo y verificacion en el chip de tarea correspondiente.

### M3. `ACCESS_TOKEN_EXPIRE_MINUTES` compartido entre v1 y v2

**Donde:** `database/services/auth/security.py:18` y `v2/auth/security.py:16`

Defaults distintos (30 min vs 480 min) pero **leen la misma variable de entorno**. Setearla
pensando en el portal academico le da 8 horas de vida a los tokens del CMS.

**Fix propuesto:** `V2_ACCESS_TOKEN_EXPIRE_MINUTES` para v2, con fallback al valor actual.

### M4. CORS permisivo

**Donde:** `main.py:265`

`allow_origins=["*"]` junto a `allow_credentials=True`. Los navegadores rechazan esa
combinacion, asi que en la practica no funciona como se espera; y como la API usa Bearer tokens
en vez de cookies, CORS no es la defensa principal. Pero indica que nadie reviso la
configuracion.

**Fix propuesto:** lista explicita de origenes del frontend, reusando el enfoque de
`OAUTH_ALLOWED_REDIRECT_ORIGINS`.

### M5. 53 `print(f"DEBUG ...")` en el camino de autenticacion

**Donde:** `database/services/auth/security.py`, `database/services/redis/redis.py`

Se ejecutan en **cada request autenticado**, e imprimen `jti` y email. No exponen el token, pero
ensucian los logs, meten datos personales en ellos y cuestan I/O.

**Fix propuesto:** pasarlos al logger del proyecto con nivel DEBUG, o eliminarlos.

### M6. Una condicion de filtro que falla se descarta en silencio

**Donde:** `database/services/filter/filters.py:481,520,550`

`_apply_condition()` y `_apply_relation_condition()` loguean el error y devuelven `None`. La
condicion se cae del query y **la consulta devuelve mas filas de las pedidas**, sin que el
llamador se entere.

**Impacto:** en un listado filtrado por permisos o por `published`, un error de construccion
del filtro se convierte en una fuga de datos silenciosa. `QueryBuilder` se usa en los endpoints
`/filters` de v1 y v2.

**Fix propuesto:** propagar el error (`QueryBuilderError`) en vez de descartar la condicion.

---

## Pendiente — Bajo

| # | Hallazgo | Donde |
|---|---|---|
| B1 | `get_current_usuario` chequea `activo` pero no `eliminado`. Hoy `eliminar_usuario()` setea ambos, asi que no hay bug — pero depende de que nunca se desacoplen. Defensa en profundidad. | `v2/auth/dependencies.py:42` |
| B2 | `/auth/me` usa `get_current_user` (sin chequeo de `active`): un usuario desactivado sigue leyendo su perfil hasta que expire el token. | `routes/auth.py:397` |
| B3 | La respuesta de `/auth/logout` devuelve `jti` y `blacklist_key` en el body. Innecesario. | `routes/auth.py:245` |
| B4 | `create_access_token(expires_delta=None)` genera un token **sin expiracion**. El login no usa ese camino, pero el footgun esta. | `database/services/auth/security.py:30` |
| B5 | `SECRET_KEY` tiene default publico en 3 lugares. Confirmado correcto en produccion, pero la app arrancaria igual si faltara. Hardening: fallar al arrancar. | `v1`, `v2`, `main.py:277` |
| B6 | 8 bloques `except: pass` sin log en servicios de negocio. Los de notificaciones son deliberados y estan comentados; los demas conviene revisarlos uno por uno. | ver `grep -rn "except.*:" -A1` |

---

## Verificado como correcto (sin cambios)

- **Webhooks de MercadoPago**: validan firma HMAC contra el secret y rechazan si no esta
  configurado (`routes/mercadopago/mercadopago.py:169`).
- **Whitelist anti open-redirect del OAuth v2**: `_is_redirect_allowed()` compara el origen
  parseado contra la lista, y el default sin env var es solo localhost.
- **Hashing de contraseñas**: bcrypt via passlib.
- **Soft-delete de usuarios v2**: `eliminar_usuario()` setea `eliminado=True` y `activo=False`,
  y `get_current_usuario` valida `activo` en **cada request**, no solo al login.
- **Logout v1**: verifica el resultado de `blacklist_token()` y devuelve 400 si fallo.
- **Endpoints publicos del sitio** (`/careers/careers`, `/news/public/*`, `/testimonies/public/*`):
  filtran por `published` correctamente. La excepcion es M1.

---

## Orden de ataque sugerido

1. **A3** — rotar credenciales. Es lo unico que puede estar comprometido ahora mismo y no se
   arregla con codigo.
2. **A1** — mismo fix que ya se aplico en v2, bajo riesgo, cierra el ultimo fail-open de auth.
3. **M6** — una fuga de datos silenciosa es peor que una ruidosa, y toca el sistema de filtros
   que se usa en todos lados.
4. **A2** — rate limiting.
5. **M2** — los emails rotos son lo mas visible para el usuario final.
6. El resto por orden de severidad.

---

*Auditoria — CTC Salto, Julio 2026*
