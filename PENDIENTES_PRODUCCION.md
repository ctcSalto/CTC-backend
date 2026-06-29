# Pendientes antes de mergear bedelia -> main

## Migraciones de base de datos

**IMPORTANTE:** Las migraciones deben aplicarse en la BD de produccion (puerto 5432) ANTES de mergear el PR a main. Si el codigo se despliega sin las tablas, la app crashea al intentar importar los modelos v2.

### Migracion requerida

```bash
# 1. Asegurarse de que DATABASE_URL apunta a produccion (puerto 5432)
# 2. Ejecutar la migracion
alembic upgrade head
```

**Migraciones (en orden):**

1. `c80c0cfd30d6_v2_tablas_academicas` — Crea 15 tablas nuevas del portal academico:
   - `usuario`, `programa`, `materia`, `politica_calificacion`, `politica_examen`
   - `materia_instancia_evaluacion`, `previatura`, `docente_materia`
   - `inscripcion_materia`, `calificacion`, `equipo`, `equipo_miembro`
   - `periodo_inscripcion_materia`, `periodo_examen`, `inscripcion_examen`

2. `d1a2b3c4d5e6_v2_refactor_portal_academico` — Refactor completo:
   - Tablas nuevas: `alumno`, `profesor`, `administrativo_perfil`, `inscripcion_programa`, `instancia_cursado`, `instancia_examen`, `docente_instancia_examen`
   - Columnas nuevas en tablas existentes (id_rastreo, campos de usuario, etc.)
   - Data migration: crea instancias_cursado desde materia_id+anio_lectivo existentes
   - DROP TABLE `periodo_examen`

3. `e2f3g4h5i6j7_agregar_faltas` — Sistema de faltas:
   - `instancia_cursado.faltas_maximas` (int nullable)
   - `inscripcion_materia.faltas` (int default 0)

4. `f3g4h5i6j7k8_seed_previaturas` — **Carga inicial de previaturas:**
   - Previaturas de **Analista Programador** (9 materias con previas + Integrador requiere TODAS las demas)
   - Previaturas de **Tecnico en Gestion y Direccion de Empresas** (18 materias con previas)
   - Resuelve por nombre de materia dentro de cada programa
   - **REQUISITO:** Los programas y materias deben existir en la BD antes de correr esta migracion

5. `a1b2c3d4e5f6_agregar_columnas_usuario_v2` — **Columnas faltantes en usuario:**
   - Columnas nuevas (todas nullable, sin romper datos existentes):
     - `usuario`: `email_personal` (varchar), `fecha_nacimiento` (date), `domicilio` (varchar 200), `eliminado` (bool default false), `fecha_eliminacion` (datetime), `id_rastreo` (varchar)
   - Usa `_column_exists()` — si una columna ya existe en la BD, la ignora sin error

7. `4d769166125d_agregar_campos_planilla_admin_y_tabla_` — **Fase 1: Campos planilla admin + documentos:**
   - Tabla nueva: `documento_usuario` (almacenamiento de archivos de alumnos/profesores)
   - Enum nuevo: `TipoDocumento` (formula_69a, escolaridad, constancia_convenio, cedula, titulo, otro)
   - Columnas nuevas (todas nullable, sin romper datos existentes):
     - `usuario`: `fecha_nacimiento` (date), `domicilio` (varchar 200)
     - `programa`: `certificacion` (varchar 100), `horas_totales` (int)
     - `materia`: `horas_semanales` (int), `horas_totales` (int)
     - `profesor`: `carga_horaria_semanal` (int)
     - `inscripcion_programa`: `fecha_baja` (datetime), `motivo_baja` (varchar 255)
     - `inscripcion_examen`: `fecha_baja` (datetime)
     - `inscripcion_materia`: `fecha_baja` (datetime)
   - Usa `_safe_add_column()` — si una columna ya existe en la BD, la ignora sin error

8. `087c21eff7fd_fase2_rendiciones_bajas_revalida` — **Fase 2: Rendiciones, bajas soft-delete, revalida:**
   - Columnas nuevas (todas con server_default, sin romper datos existentes):
     - `politica_examen`: `max_oportunidades` (int, default 5) — maximo de veces que se puede rendir un examen
     - `inscripcion_examen`: `numero_rendicion` (int, default 1) — numero de rendicion (1ra, 2da, etc.)
     - `inscripcion_materia`: `motivo_revalida` (varchar 255, nullable) — motivo de revalida
   - Usa `_safe_add_column()` — si una columna ya existe en la BD, la ignora sin error
   - **Cambios de comportamiento (no requieren migracion):**
     - Desinscripcion de materia ahora usa soft-delete (estado ABANDONO + fecha_baja) en vez de borrar
     - Desinscripcion de examen ahora usa soft-delete (estado BAJA + fecha_baja) con plazo de 72hs
     - Inscripcion a examen valida max_oportunidades y asigna numero_rendicion automaticamente
     - Calificacion de examen reprobado verifica si se agotaron las rendiciones (cambia materia a REPROBADO)
     - Nuevo endpoint de revalida: `POST /v2/admin/inscripciones/{id}/revalidar`

9. `b2c3d4e5f6g7_fase5_notificaciones` — **Fase 5: sistema de notificaciones por email:**
   - Tabla nueva: `notificacion_log` (registro de todos los emails enviados, con `id_rastreo` para trazabilidad)
   - Columna nueva: `inscripcion_materia.notificacion_calificacion_enviada` (bool, default false)
   - Esta migracion estaba aplicada en desarrollo pero no se habia documentado aqui; se detecto al
     encontrar dos heads simultaneos en el historial de Alembic (ver migracion 10)

10. `4fd4c9f395dd_merge_heads_usuario_v2_y_notificaciones` — **Merge de heads:**
    - Migracion no-op (no toca esquema). Las migraciones 5 (`a1b2c3d4e5f6`) y 9 (`b2c3d4e5f6g7`)
      se crearon ambas con el mismo padre (`087c21eff7fd`), generando dos heads divergentes en vez
      de una cadena lineal. Esto rompia `alembic revision --autogenerate` (autogenerate no detecta
      el estado real combinado) y podia generar ambigüedad en `alembic upgrade head`.
    - **Importante:** si la BD de produccion ya tiene aplicada la migracion 5 (`a1b2c3d4e5f6`) pero
      NO la 9 (`b2c3d4e5f6g7`), hay que correr `alembic upgrade head` normalmente (aplica 9 y luego
      el merge). Si por algun motivo ya estuvieran ambas aplicadas via SQL manual, verificar con
      `alembic current` y usar `alembic stamp` si hace falta alinear el historial.

11. `bad9dad1cc40_agregar_tabla_testimony_video` — **Videos en testimonios:**
    - Tabla nueva: `testimony_video` (`testimonyVideoId`, `testimonyId` FK a `testimony`, `url`,
      `order`, `creationDate`)
    - Permite N videos por testimonio (ej: testimonios con video de YouTube o Supabase Storage,
      a definir cual proveedor se usa — la tabla no depende de esa decision, solo guarda la URL)
    - Endpoints nuevos: `POST/PUT/DELETE /testimonies/{testimony_id}/videos[/{video_id}]`
    - `TestimonyRead` y `TestimonyPublic` ahora incluyen `videos: List[TestimonyVideoRead]`

**Riesgo:** Las migraciones 1-3 crean/modifican tablas. La migracion 4 inserta datos (previaturas). La migracion 5 agrega columnas a usuario. Las migraciones 7 y 8 agregan columnas nullable/con defaults (sin impacto en datos existentes). La migracion 9 crea una tabla nueva y una columna con default (sin impacto). La migracion 10 es no-op (solo ordena el historial). La migracion 11 crea una tabla nueva con FK a `testimony` (sin impacto en datos existentes).

**Nota sobre `alembic/env.py`:** se detecto que el archivo no importaba `Career`, `Testimony` ni `News` en su `target_metadata`, lo cual hacia que `alembic revision --autogenerate` marcara esas tablas como "removidas" (¡riesgo real de DROP TABLE accidental si se aceptaba un autogenerate sin revisar el diff!). Se corrigio agregando esos imports. **Cualquier autogenerate futuro debe revisarse a mano antes de aplicarse** — el diff todavia puede traer ruido de tablas legacy (`author`, `profile`, `post`, `example`) que existen en algunas BDs pero no en los modelos actuales.

### Checklist de deploy

- [ ] Verificar que los programas "Analista Programador" y "Tecnico en Gestion y Direccion de Empresas" existen en tabla `programa`
- [ ] Verificar que las materias de ambos programas existen en tabla `materia` con los nombres correctos
- [ ] Aplicar migraciones en BD produccion (`alembic upgrade head` con DATABASE_URL de prod)
- [ ] Verificar que las tablas se crearon (`\dt` en psql)
- [ ] Verificar que las previaturas se insertaron (`SELECT count(*) FROM previatura`)
- [ ] Verificar que la tabla `documento_usuario` se creo (`\d documento_usuario`)
- [ ] Verificar columnas nuevas: `SELECT fecha_nacimiento, domicilio FROM usuario LIMIT 1`
- [ ] Crear directorio de documentos: `sudo mkdir -p /var/ctc/documentos && sudo chown <app_user> /var/ctc/documentos`
- [ ] Agregar variables de entorno: `DOCUMENTOS_BASE_PATH`, `DOCUMENTOS_MAX_SIZE_MB`
- [ ] Mergear PR bedelia -> main
- [ ] Verificar que la app levanta sin errores (`/health`)
- [ ] Verificar endpoints de documentos en Swagger (`/docs` -> seccion "Admin Documentos")
- [ ] Verificar columna `max_oportunidades` en `politica_examen`: `SELECT max_oportunidades FROM politica_examen LIMIT 1`
- [ ] Verificar columna `numero_rendicion` en `inscripcion_examen`: `SELECT numero_rendicion FROM inscripcion_examen LIMIT 1`
- [ ] Verificar endpoint de revalida en Swagger (`/docs` -> seccion "Admin Inscripciones")
- [ ] Agregar variable de entorno: `PLAZO_BAJA_EXAMEN_HORAS` (opcional, default 72)
- [ ] Verificar tabla `notificacion_log` y columna `inscripcion_materia.notificacion_calificacion_enviada` (migracion 9, antes no documentada)
- [ ] Correr `alembic current` ANTES de `alembic upgrade head` en produccion para confirmar en que revision esta (por el merge de heads de la migracion 10)
- [ ] Verificar que la tabla `testimony_video` se creo (`\d testimony_video`)
- [ ] Verificar endpoints de videos en Swagger (`/docs` -> seccion "Testimonies", rutas `/testimonies/{id}/videos`)
- [ ] Decidir proveedor de hosting de video (YouTube vs Supabase Storage) — no bloquea el deploy de esta migracion, la tabla solo guarda una URL libre

## Variables de entorno nuevas

### Requeridas para el sistema de documentos (Migracion 5)

```bash
# Ruta base donde se almacenan los documentos de alumnos/profesores
# En produccion: directorio en la VPS con espacio suficiente
DOCUMENTOS_BASE_PATH=/var/ctc/documentos

# Limite de tamano por archivo en MB (default: 10)
DOCUMENTOS_MAX_SIZE_MB=10
```

**IMPORTANTE:** Crear el directorio en produccion antes de deployar:
```bash
sudo mkdir -p /var/ctc/documentos
sudo chown -R <usuario_app>:<grupo_app> /var/ctc/documentos
```

La estructura de carpetas se crea automaticamente al subir el primer documento de cada usuario:
```
/var/ctc/documentos/
├── alumnos/{id}_{apellido}_{nombre}/
│   ├── formula_69a/
│   ├── escolaridad/
│   └── otros/
├── profesores/{id}_{apellido}_{nombre}/
│   ├── cedula/
│   ├── titulo/
│   └── otros/
└── administrativos/...
```

### Notificaciones por email (Fase 5)

```bash
# Webhook de n8n para envio de emails de notificaciones
N8N_EMAIL_WEBHOOK_URL=https://automatizaciones-n8n.vtu0xl.easypanel.host/webhook/webhook/ctc-email-send
```

### Opcional para control de rendiciones (Migracion 6)

```bash
# Plazo minimo en horas antes del examen para permitir baja (default: 72)
PLAZO_BAJA_EXAMEN_HORAS=72
```

### Google OAuth 2.0

```bash
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=
GOOGLE_ALLOWED_DOMAIN=ctcsalto.edu.uy

# Origenes permitidos para redirect_to en el login OAuth (whitelist anti open-redirect)
# Lista separada por comas con los origenes del frontend (Next.js)
# Ejemplo: https://portal.ctcsalto.edu.uy,https://frontend-develop.vtu0xl.easypanel.host
OAUTH_ALLOWED_REDIRECT_ORIGINS=
```

## Google OAuth - Consola de Google Cloud

- [ ] Agregar origenes de JS autorizados de develop y produccion (cuando frontend empiece desarrollo)
- [ ] Las URIs de redireccion del backend ya estan configuradas
- [ ] Configurar variables `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` en el entorno de deploy
- [ ] Configurar `OAUTH_ALLOWED_REDIRECT_ORIGINS` con los origenes del frontend Next.js (NO es la URL del backend, sino la del frontend que recibe el token tras el login)
- [ ] Agregar la URI de callback de develop en Google Console: `https://backend-backend-ctc-develop.vtu0xl.easypanel.host/v2/auth/google/callback`
- [ ] Pagina de prueba OAuth disponible en `/test-login` (SvelteKit) para que frontend valide la integracion

## Proxy inverso (Easypanel / Traefik)

El backend corre detras de un proxy inverso que termina SSL. Sin la configuracion de `--proxy-headers`, FastAPI recibe las requests como `http://` en lugar de `https://`, lo que causa error **"Redirect URI Mismatch"** con Google OAuth.

**Solucion aplicada:** Se agrego `--proxy-headers` y `--forwarded-allow-ips='*'` en uvicorn (`Procfile`), y se agrego el middleware `ProxyHeadersMiddleware` en `main.py`. Esto hace que FastAPI confie en los encabezados `X-Forwarded-Proto` y `X-Forwarded-For` del proxy.

- [ ] Verificar que Google OAuth funciona correctamente en develop (redireccion HTTPS)
- [ ] Verificar que Google OAuth funciona correctamente en produccion

## Notas

- Las tablas v2 coexisten con las v1 (user, career, testimony, news)
- No hay FK entre tablas v1 y v2
- El codigo v2 esta en el directorio `v2/` y no afecta el funcionamiento actual
- Si se necesita rollback completo: `alembic downgrade 055950855a1a` (elimina todas las tablas v2)
- Si se necesita rollback solo de Fase 2 (rendiciones): `alembic downgrade 4d769166125d` (quita max_oportunidades, numero_rendicion, motivo_revalida)
- Si se necesita rollback de Fases 1+2: `alembic downgrade f3g4h5i6j7k8` (quita todo de Fase 1 y 2)
- Si se necesita rollback solo de la tabla de videos: `alembic downgrade 4fd4c9f395dd` (elimina `testimony_video`)
