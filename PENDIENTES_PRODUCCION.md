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

**Riesgo:** Las migraciones 1-3 crean/modifican tablas. La migracion 4 inserta datos (previaturas).

### Checklist de deploy

- [ ] Verificar que los programas "Analista Programador" y "Tecnico en Gestion y Direccion de Empresas" existen en tabla `programa`
- [ ] Verificar que las materias de ambos programas existen en tabla `materia` con los nombres correctos
- [ ] Aplicar migraciones en BD produccion (`alembic upgrade head` con DATABASE_URL de prod)
- [ ] Verificar que las tablas se crearon (`\dt` en psql)
- [ ] Verificar que las previaturas se insertaron (`SELECT count(*) FROM previatura`)
- [ ] Mergear PR bedelia -> main
- [ ] Verificar que la app levanta sin errores (`/health`)

## Variables de entorno nuevas (para fases futuras)

Estas variables no son necesarias ahora (Fase 1 es solo modelos), pero seran requeridas cuando se implementen las fases de auth y endpoints:

```bash
# Google OAuth 2.0 (Fase 2)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=
GOOGLE_ALLOWED_DOMAIN=ctcsalto.edu.uy
```

## Google OAuth - Consola de Google Cloud

- [ ] Agregar origenes de JS autorizados de develop y produccion (cuando frontend empiece desarrollo)
- [ ] Las URIs de redireccion del backend ya estan configuradas
- [ ] Configurar variables `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` en el entorno de deploy

## Proxy inverso (Easypanel / Traefik)

El backend corre detras de un proxy inverso que termina SSL. Sin la configuracion de `--proxy-headers`, FastAPI recibe las requests como `http://` en lugar de `https://`, lo que causa error **"Redirect URI Mismatch"** con Google OAuth.

**Solucion aplicada:** Se agrego `--proxy-headers` y `--forwarded-allow-ips='*'` en uvicorn (`Procfile`), y se agrego el middleware `ProxyHeadersMiddleware` en `main.py`. Esto hace que FastAPI confie en los encabezados `X-Forwarded-Proto` y `X-Forwarded-For` del proxy.

- [ ] Verificar que Google OAuth funciona correctamente en develop (redireccion HTTPS)
- [ ] Verificar que Google OAuth funciona correctamente en produccion

## Notas

- Las tablas v2 coexisten con las v1 (user, career, testimony, news)
- No hay FK entre tablas v1 y v2
- El codigo v2 esta en el directorio `v2/` y no afecta el funcionamiento actual
- Si se necesita rollback: `alembic downgrade 055950855a1a` (elimina las 15 tablas v2)
