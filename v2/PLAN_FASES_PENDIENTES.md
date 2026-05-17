# Plan de implementacion - Fases pendientes

**Fecha:** Mayo 2026
**Origen:** Analisis comparativo Planilla Administracion vs Modelo v2 actual
**Rama:** `develop`

---

## Contexto

Tras cruzar los datos de la planilla de definicion de datos de Bedelias con nuestro esquema v2 actual, se identificaron atributos faltantes y funcionalidad nueva. Este plan organiza el trabajo en dos fases mas un servicio transversal de archivos locales.

---

## Servicio de Archivos Locales

### Justificacion

Los documentos de alumnos y profesores (cedulas, titulos, escolaridad, constancias de convenio) son datos sensibles y privados. Se almacenan en la VPS (150 GB SSD) en lugar de Supabase (500 MB gratuito) por:

- Espacio: 150 GB vs 500 MB
- Latencia: <5ms local vs 100-300ms CDN externo
- Privacidad: documentos con datos personales no deben tener URL publica
- Sin dependencia: no depender de un servicio externo para datos criticos

Supabase se mantiene para las imagenes publicas del sitio (noticias, testimonios, fotos de carreras).

### Estructura de carpetas

```
/var/ctc/documentos/                          ← raiz configurable via env DOCUMENTOS_BASE_PATH
├── alumnos/
│   ├── {usuario_id}_{apellido}_{nombre}/     ← carpeta por alumno
│   │   ├── formula_69a/
│   │   │   └── 2026-03-15_formula69a.pdf
│   │   ├── escolaridad/
│   │   │   └── 2026-03-15_escolaridad.pdf
│   │   ├── constancia_convenio/
│   │   │   └── 2026-04-01_convenio_empresa.pdf
│   │   └── otros/
│   │       └── 2026-05-10_certificado_ingles.pdf
│   ├── 2_perez_juan/
│   │   └── ...
│   └── 3_garcia_maria/
│       └── ...
├── profesores/
│   ├── {usuario_id}_{apellido}_{nombre}/     ← carpeta por profesor
│   │   ├── cedula/
│   │   │   ├── 2026-03-01_cedula_frente.jpg
│   │   │   └── 2026-03-01_cedula_dorso.jpg
│   │   ├── titulo/
│   │   │   └── 2026-03-01_titulo_universitario.pdf
│   │   └── otros/
│   │       └── 2026-06-15_certificacion_aws.pdf
│   └── 5_gomez_luis/
│       └── ...
└── temp/                                     ← archivos en proceso, se limpian periodicamente
```

**Convenciones de nombre:**
- Carpeta usuario: `{usuario_id}_{apellido}_{nombre}` (todo minusculas, sin acentos, espacios reemplazados por `_`)
- Archivo: `{fecha}_{tipo_documento}.{extension}` (ej: `2026-03-15_formula69a.pdf`)
- El `usuario_id` al inicio garantiza unicidad si hay homonimos

### Modelo de base de datos

```python
class DocumentoUsuario(SQLModel, table=True):
    __tablename__ = "documento_usuario"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    tipo: TipoDocumento          # FORMULA_69A, ESCOLARIDAD, CONSTANCIA_CONVENIO, CEDULA, TITULO, OTRO
    nombre_original: str         # nombre del archivo que subio el usuario
    ruta_relativa: str           # "alumnos/1_perez_juan/formula_69a/2026-03-15_formula69a.pdf"
    mime_type: str               # "application/pdf", "image/jpeg"
    tamanio_bytes: int           # tamano del archivo en bytes
    descripcion: Optional[str]   # descripcion libre del usuario o admin
    subido_por: int              # usuario_id de quien subio (puede ser admin)
    fecha_subida: datetime
    activo: bool = True          # soft delete
    id_rastreo: str              # UUID trazabilidad
```

```python
class TipoDocumento(str, Enum):
    # Alumno
    FORMULA_69A = "formula_69a"
    ESCOLARIDAD = "escolaridad"
    CONSTANCIA_CONVENIO = "constancia_convenio"
    # Profesor
    CEDULA = "cedula"
    TITULO = "titulo"
    # Compartido
    OTRO = "otro"
```

### Procesamiento de archivos

Al subir un archivo, el servicio aplica procesamiento automatico segun el tipo:

**PDFs** → se guardan tal cual, sin modificar.

**Imagenes (cedula, titulo, constancias escaneadas):**
- Conversion automatica a WebP (igual que el servicio de Supabase actual)
- Compresion al 85% de calidad
- Correccion de rotacion EXIF (fotos de celular)
- Redimensionado: si el ancho o alto supera 2000px, se reduce proporcionalmente a 2000px de lado maximo. Una foto de cedula no necesita 12 megapixeles.
- Nombre final: `{fecha}_{tipo}.webp`

Esto garantiza que las imagenes ocupen el minimo espacio posible sin perder calidad util. Un JPG de celular de 4 MB queda en ~100-200 KB como WebP redimensionado.

### Servicio: `LocalFileService`

```
v2/services/local_file_service.py
```

Responsabilidades:
- **upload(usuario_id, tipo, archivo)** → guarda en disco, crea registro en BD, retorna DocumentoRead
- **download(documento_id, usuario_solicitante)** → valida permisos, retorna FileResponse
- **list(usuario_id)** → listar documentos de un usuario
- **delete(documento_id)** → soft delete en BD, opcionalmente borrar archivo fisico
- **ensure_user_folder(usuario_id)** → crea la estructura de carpetas si no existe
- **sanitize_folder_name(nombre, apellido)** → normaliza nombre de carpeta (sin acentos, minusculas)

Reglas de acceso:
- Un alumno solo puede ver/subir sus propios documentos
- Un docente solo puede ver/subir sus propios documentos
- Un admin puede ver/subir documentos de cualquier usuario
- Los archivos NUNCA se sirven como estaticos publicos; siempre pasan por endpoint autenticado

### Endpoints

```
POST   /v2/portal/estudiante/documentos           ← subir documento propio
GET    /v2/portal/estudiante/mis-documentos        ← listar mis documentos
GET    /v2/portal/estudiante/documentos/{id}       ← descargar documento propio

POST   /v2/portal/docente/documentos               ← subir documento propio
GET    /v2/portal/docente/mis-documentos            ← listar mis documentos
GET    /v2/portal/docente/documentos/{id}           ← descargar documento propio

POST   /v2/admin/documentos/{usuario_id}           ← subir documento para cualquier usuario
GET    /v2/admin/documentos/{usuario_id}            ← listar documentos de un usuario
GET    /v2/admin/documentos/descargar/{id}          ← descargar cualquier documento
DELETE /v2/admin/documentos/{id}                    ← eliminar documento
```

### Variable de entorno

```
DOCUMENTOS_BASE_PATH=/var/ctc/documentos    # produccion
DOCUMENTOS_BASE_PATH=./documentos_dev       # desarrollo local
DOCUMENTOS_MAX_SIZE_MB=10                   # limite por archivo
```

---

## Fase 1 - Atributos faltantes (sin romper nada)

### Objetivo
Agregar campos que administracion necesita para el registro manual. Son columnas nuevas `nullable`, no rompen datos existentes ni endpoints actuales.

### 1.1 Cambios en modelos

#### Usuario (`v2/models/usuario.py`)

| Campo nuevo | Tipo | Obligatorio | Descripcion |
|---|---|---|---|
| `fecha_nacimiento` | `date` (nullable) | Si segun admin | Fecha de nacimiento |
| `domicilio` | `str(200)` (nullable) | Si segun admin | Direccion del alumno |

> Se agregan en `Usuario` (no en `Alumno`) porque el domicilio y fecha de nacimiento son datos de la persona, no del rol. Un docente tambien podria necesitarlos.

#### Programa (`v2/models/programa.py`)

| Campo nuevo | Tipo | Obligatorio | Descripcion |
|---|---|---|---|
| `certificacion` | `str(100)` (nullable) | No | Institucion certificadora: "CTC-UCLAEH", "CTC-IPEP" |
| `horas_totales` | `int` (nullable) | No | Total de horas del programa |

#### Materia (`v2/models/materia.py`)

| Campo nuevo | Tipo | Obligatorio | Descripcion |
|---|---|---|---|
| `horas_semanales` | `int` (nullable) | No | Horas por semana (numero, no texto) |
| `horas_totales` | `int` (nullable) | No | Horas totales de la materia |

#### Profesor (`v2/models/profesor.py`)

| Campo nuevo | Tipo | Obligatorio | Descripcion |
|---|---|---|---|
| `carga_horaria_semanal` | `int` (nullable) | No | Horas semanales totales del docente |

#### InscripcionPrograma (`v2/models/inscripcion_programa.py`)

| Campo nuevo | Tipo | Obligatorio | Descripcion |
|---|---|---|---|
| `fecha_baja` | `datetime` (nullable) | No | Cuando se dio de baja |
| `motivo_baja` | `str(255)` (nullable) | No | Motivo de la baja |

#### InscripcionExamen (`v2/models/inscripcion_examen.py`)

| Campo nuevo | Tipo | Obligatorio | Descripcion |
|---|---|---|---|
| `fecha_baja` | `datetime` (nullable) | No | Cuando se desinscribio |

#### InscripcionMateria (`v2/models/inscripcion_materia.py`)

| Campo nuevo | Tipo | Obligatorio | Descripcion |
|---|---|---|---|
| `fecha_baja` | `datetime` (nullable) | No | Fecha de desinscripcion (para historial) |

### 1.2 Migracion Alembic

Una sola migracion que agrega todas las columnas:

```
alembic/versions/xxxx_agregar_campos_planilla_admin.py
```

Todas las columnas son `nullable`, asi que la migracion es un `ALTER TABLE ADD COLUMN` sin valor default ni backfill. Compatible con datos existentes.

### 1.3 Cambios en schemas (Create/Update/Read)

Cada modelo necesita actualizar sus schemas para exponer los campos nuevos:

- `UsuarioRead` → agregar `fecha_nacimiento`, `domicilio`
- `UsuarioUpdate` → agregar `fecha_nacimiento`, `domicilio`
- `ProgramaCreate/Update/Read` → agregar `certificacion`, `horas_totales`
- `MateriaCreate/Update/Read` → agregar `horas_semanales`, `horas_totales`
- `ProfesorCreate/Update/Read` → agregar `carga_horaria_semanal`
- `InscripcionProgramaRead` → agregar `fecha_baja`, `motivo_baja`
- `InscripcionExamenRead` → agregar `fecha_baja`
- `InscripcionMateriaRead` → agregar `fecha_baja`

### 1.4 Tabla de documentos

Agregar modelo `DocumentoUsuario` y enum `TipoDocumento` (descritos en la seccion de archivos locales).

### 1.5 Servicio de archivos

Crear `LocalFileService` e implementar los endpoints documentados arriba.

### 1.6 Archivos afectados

```
v2/models/usuario.py                      ← +2 campos
v2/models/programa.py                     ← +2 campos
v2/models/materia.py                      ← +2 campos
v2/models/profesor.py                     ← +1 campo
v2/models/inscripcion_programa.py         ← +2 campos
v2/models/inscripcion_examen.py           ← +1 campo
v2/models/inscripcion_materia.py          ← +1 campo
v2/models/documento_usuario.py            ← NUEVO
v2/models/enums.py                        ← +1 enum (TipoDocumento)
v2/models/__init__.py                     ← registrar DocumentoUsuario
v2/services/local_file_service.py         ← NUEVO
v2/services/__init__.py                   ← registrar servicio
v2/routes/estudiante.py                   ← +3 endpoints documentos
v2/routes/docente.py                      ← +3 endpoints documentos
v2/routes/admin_documentos.py             ← NUEVO (+4 endpoints)
main.py                                   ← registrar router admin_documentos
alembic/versions/xxxx_campos_planilla.py  ← NUEVA migracion
alembic/env.py                            ← importar DocumentoUsuario
```

### 1.7 Tests

```
v2/tests/test_local_file_service.py       ← upload, download, permisos, carpetas
v2/tests/test_documentos_endpoints.py     ← endpoints estudiante, docente, admin
```

### 1.8 Impacto en endpoints existentes

**CERO.** Todos los campos nuevos son opcionales/nullable. Los endpoints actuales siguen funcionando exactamente igual. Frontend puede empezar a enviar los campos nuevos cuando quiera, o no enviarlos.

---

## Fase 2 - Logica de negocio (rendiciones de examen y bajas)

### Objetivo
Implementar reglas de negocio que administracion usa diariamente: control de rendiciones de examen, soft-delete con historial en desinscripciones, y plazos de baja.

### 2.1 Control de rendiciones de examen

**Problema:** El alumno puede rendir un examen hasta 5 veces. Si no aprueba en 5, debe recursar la materia. Hoy no controlamos esto.

#### Cambios en modelos

**PoliticaExamen** (`v2/models/politica_examen.py`):

| Campo nuevo | Tipo | Default | Descripcion |
|---|---|---|---|
| `max_oportunidades` | `int` | `5` | Maximo de veces que puede rendir |

**InscripcionExamen** (`v2/models/inscripcion_examen.py`):

| Campo nuevo | Tipo | Default | Descripcion |
|---|---|---|---|
| `numero_rendicion` | `int` | `1` | Numero de rendicion (1ra, 2da, 3ra...) |

#### Logica en servicio

En `inscripcion_examen_service.py`, al inscribir a examen:

```
1. Contar inscripciones previas del alumno en la misma materia
   (estado APROBADO, REPROBADO o AUSENTE — no contar INSCRIPTO activo)
2. Si cantidad >= max_oportunidades de la politica de examen:
   → Error "Superaste el maximo de oportunidades (5). Debes recursar la materia."
3. Si no, asignar numero_rendicion = cantidad + 1
```

Al reprobar la 5ta rendicion:
```
1. Marcar inscripcion examen como REPROBADO
2. Marcar inscripcion materia como REPROBADO (debe recursar)
```

#### Archivos afectados

```
v2/models/politica_examen.py              ← +1 campo
v2/models/inscripcion_examen.py           ← +1 campo
v2/services/inscripcion_examen_service.py ← logica de conteo y bloqueo
```

### 2.2 Desinscripcion como soft-delete con historial

**Problema:** Hoy al desinscribirse de una materia, se cambia el estado pero no queda registro de cuando ni por que. Administracion necesita fecha y motivo.

#### Cambios en logica

En `inscripcion_service.py` → `desinscribir_materia()`:

```
Antes:  inscripcion.estado = ABANDONO
Ahora:  inscripcion.estado = ABANDONO
        inscripcion.fecha_baja = datetime.now()
        inscripcion.motivo_cierre = "Desinscripcion voluntaria"
```

En `inscripcion_programa_service.py` → dar de baja programa:

```
inscripcion.estado = BAJA
inscripcion.fecha_baja = datetime.now()
inscripcion.motivo_baja = motivo  # parametro del endpoint
```

En `inscripcion_examen_service.py` → `desinscribir_examen()`:

```
Antes:  session.delete(inscripcion_examen)
Ahora:  inscripcion_examen.estado = BAJA  # nuevo estado enum
        inscripcion_examen.fecha_baja = datetime.now()
```

> Esto requiere agregar `BAJA` al enum `EstadoInscripcionExamen`.

#### Archivos afectados

```
v2/models/enums.py                         ← +1 valor en EstadoInscripcionExamen
v2/services/inscripcion_service.py         ← desinscripcion materia con fecha
v2/services/inscripcion_examen_service.py  ← desinscripcion examen como soft-delete
```

### 2.3 Plazo de baja de examen (72 horas)

**Regla:** El alumno puede darse de baja de un examen hasta 72 horas antes de la fecha del examen.

#### Cambio en servicio

En `inscripcion_examen_service.py` → `desinscribir_examen()`:

```python
ahora = datetime.now(tz)
limite = instancia_examen.fecha_examen - timedelta(hours=72)
if ahora > limite:
    raise ValueError("No puedes darte de baja. El plazo es hasta 72 horas antes del examen.")
```

#### Variable de entorno (configurable)

```
PLAZO_BAJA_EXAMEN_HORAS=72
```

### 2.4 Revalida (basico)

**Problema:** Un alumno puede revalidar una materia (convalidar por haberla aprobado en otra institucion). Administracion lo marca manualmente.

#### Cambios

- Agregar `REVALIDADA` a `EstadoInscripcionMateria`
- Agregar `motivo_revalida: Optional[str]` a `InscripcionMateria`
- Endpoint admin: `POST /v2/admin/inscripciones/{inscripcion_id}/revalidar`
  - Body: `{ "motivo": "Aprobada en UTEC - 2025" }`
  - Cambia estado a REVALIDADA, asigna creditos, registra motivo

#### Archivos afectados

```
v2/models/enums.py                         ← +1 valor en EstadoInscripcionMateria
v2/models/inscripcion_materia.py           ← +1 campo motivo_revalida
v2/services/inscripcion_service.py         ← metodo revalidar_materia()
v2/routes/admin_inscripciones.py           ← +1 endpoint
```

### 2.5 Migracion Alembic

Una sola migracion para toda la Fase 2:

```
alembic/versions/xxxx_fase2_rendiciones_bajas_revalida.py
```

### 2.6 Tests

```
v2/tests/test_rendiciones_examen.py        ← conteo, bloqueo en 5ta, numero_rendicion
v2/tests/test_bajas_historial.py           ← soft-delete, fechas, plazos 72hs
v2/tests/test_revalida.py                  ← revalidacion, creditos, estado
```

### 2.7 Impacto en endpoints existentes

- `/inscribirse-examen` → agrega validacion de max oportunidades (puede rechazar inscripcion que antes aceptaba)
- `/desinscribir-examen` → ya no borra el registro, lo marca como BAJA con fecha
- `/desinscribir-materia` → agrega fecha_baja al registro

Frontend: los responses de estos endpoints tendran campos nuevos (`numero_rendicion`, `fecha_baja`). Los campos existentes no cambian.

---

## Resumen de archivos por fase

### Fase 1 (17 archivos)

| Archivo | Accion |
|---|---|
| `v2/models/usuario.py` | Modificar (+2 campos) |
| `v2/models/programa.py` | Modificar (+2 campos) |
| `v2/models/materia.py` | Modificar (+2 campos) |
| `v2/models/profesor.py` | Modificar (+1 campo) |
| `v2/models/inscripcion_programa.py` | Modificar (+2 campos) |
| `v2/models/inscripcion_examen.py` | Modificar (+1 campo) |
| `v2/models/inscripcion_materia.py` | Modificar (+1 campo) |
| `v2/models/documento_usuario.py` | **Nuevo** |
| `v2/models/enums.py` | Modificar (+TipoDocumento) |
| `v2/models/__init__.py` | Modificar |
| `v2/services/local_file_service.py` | **Nuevo** |
| `v2/services/__init__.py` | Modificar |
| `v2/routes/estudiante.py` | Modificar (+3 endpoints) |
| `v2/routes/docente.py` | Modificar (+3 endpoints) |
| `v2/routes/admin_documentos.py` | **Nuevo** |
| `main.py` | Modificar |
| `alembic/versions/xxxx_campos_planilla.py` | **Nueva migracion** |

### Fase 2 (11 archivos)

| Archivo | Accion |
|---|---|
| `v2/models/politica_examen.py` | Modificar (+1 campo) |
| `v2/models/inscripcion_examen.py` | Modificar (+1 campo) |
| `v2/models/inscripcion_materia.py` | Modificar (+1 campo) |
| `v2/models/enums.py` | Modificar (+2 valores enum) |
| `v2/services/inscripcion_examen_service.py` | Modificar (rendiciones + soft-delete) |
| `v2/services/inscripcion_service.py` | Modificar (fecha_baja + revalida) |
| `v2/routes/admin_inscripciones.py` | Modificar (+1 endpoint revalida) |
| `alembic/versions/xxxx_fase2.py` | **Nueva migracion** |
| `v2/tests/test_rendiciones_examen.py` | **Nuevo** |
| `v2/tests/test_bajas_historial.py` | **Nuevo** |
| `v2/tests/test_revalida.py` | **Nuevo** |

---

## Orden de ejecucion sugerido

```
Fase 1
  1. Agregar campos simples a modelos existentes + schemas
  2. Crear migracion Alembic (1 sola, todos los campos)
  3. Crear modelo DocumentoUsuario + enum TipoDocumento
  4. Implementar LocalFileService
  5. Agregar endpoints de documentos (estudiante, docente, admin)
  6. Tests
  7. Actualizar API_ENDPOINTS_V2.md y regenerar PDF

Fase 2
  1. Agregar max_oportunidades y numero_rendicion
  2. Implementar logica de conteo y bloqueo
  3. Cambiar desinscripciones a soft-delete con fecha
  4. Agregar regla de plazo 72hs
  5. Implementar revalida basica
  6. Crear migracion Alembic
  7. Tests
  8. Actualizar documentacion
```

---

*Plan generado: Mayo 2026 - CTC Salto*
