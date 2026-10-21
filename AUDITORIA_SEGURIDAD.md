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
| Alto | 4 | 2 |
| Medio | 4 | 3 |
| Bajo | 0 | 6 |

**Segunda tanda (commit de fixes de auditoria):** A1 (blacklist v1 fail-closed),
M2 (templates de email), M3 (expiry v2 separado), M5 (prints DEBUG en el modulo
de auth), y M6 (filtro que descartaba condiciones en silencio). Detalle abajo,
movidos a "Ya arreglado".

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
| 9 | Blacklist de v1 fallaba abierto (mismo bug que v2): con Redis caido, todo token revocado volvia a valer | Alto | fixes auditoria |
| 10 | 8 templates de email con placeholders doble-escapados: los alumnos recibian `Nota: {nota}` literal | Medio | fixes auditoria |
| 11 | `QueryBuilder` descartaba en silencio una condicion que no podia construir → la consulta devolvia mas filas de las pedidas (fuga en listados filtrados por permisos/`published`) | Medio | fixes auditoria |
| 12 | `ACCESS_TOKEN_EXPIRE_MINUTES` compartido v1/v2: setearlo para el portal le cambiaba la vida a los tokens del CMS | Medio | fixes auditoria |
| 13 | 53 `print("DEBUG ...")` en el modulo de auth imprimiendo jti/email en cada request | Medio | fixes auditoria (security.py) |

**Cadena que existia:** `GET /reset-database` (vaciar la base) → `POST /auth/create-first-user`
(crear admin de credenciales publicas) → login. Toma de control completa en dos requests sin
autenticacion. Cortada en los puntos 1 y 4.

---

## Pendiente — Alto

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

### M4. CORS permisivo

**Donde:** `main.py:265`

`allow_origins=["*"]` junto a `allow_credentials=True`. Los navegadores rechazan esa
combinacion, asi que en la practica no funciona como se espera; y como la API usa Bearer tokens
en vez de cookies, CORS no es la defensa principal. Pero indica que nadie reviso la
configuracion.

**Fix propuesto:** lista explicita de origenes del frontend, reusando el enfoque de
`OAUTH_ALLOWED_REDIRECT_ORIGINS`.

### M5b. `print(f"DEBUG ...")` restantes en `redis.py`

**Donde:** `database/services/redis/redis.py`

Los del modulo de auth (`security.py`) ya se limpiaron. Quedan los de `RedisService`, que
imprimen claves de cache. Menor, pero conviene pasarlos al logger o quitarlos.

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

## Orden de ataque sugerido (pendientes)

1. **A3** — rotar credenciales `admin@gmail.com` en produccion. Es lo unico que puede estar
   comprometido ahora mismo y no se arregla con codigo.
2. **A2** — rate limiting en `/auth/login`. Requiere agregar `slowapi` como dependencia; se
   deja para una tanda propia por tocar el middleware.
3. **M1** — filtro `published` en `/careers/{id}` publico. Es una fuga real, pero cambia el
   comportamiento de un endpoint del sitio publico: verificar consumidores antes de tocar.
4. **M4** — CORS explicito. Necesita la lista de origenes del frontend.
5. **M5b** y los items **Bajo**, por orden de severidad.

## Deuda deliberadamente no tomada en la segunda tanda (y por que)

- **A2 (rate limiting):** agrega una dependencia (`slowapi`) y toca el middleware global de
  `main.py`. No se puede testear el efecto sin levantar la app; merece su propio cambio acotado.
- **M1 (`/careers/{id}` published):** es un cambio de comportamiento de un endpoint del sitio
  publico. El panel admin no lo consume (usa `/google/test/*` y `/auth`), pero el sitio publico
  si, y no puedo ver ese frontend. Cambiar la semantica sin confirmar consumidores es arriesgado.
- **M4 (CORS):** hace falta la lista real de origenes del frontend Next.js; ponerla mal rompe
  el navegador.
- **A3 (rotacion):** es operativo, no de codigo.

---

*Auditoria — CTC Salto, Julio 2026*
