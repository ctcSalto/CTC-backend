# Guia de Migracion de Usuarios a Google Workspace

## Resumen

Estos scripts crean cuentas de Google Workspace (`@ctcsalto.edu.uy`) a partir de datos en archivos Excel, generan contrasenas seguras, y envian las credenciales al email personal del alumno via n8n.

---

## Scripts disponibles

| Script | Proposito | Excel que usa |
|--------|-----------|---------------|
| `migrate_usuarios.py` | Migracion masiva desde Moodle (multiples hojas, tipos de usuario) | `Moodle 2025.xlsx` |
| `migrate_nuevos_inscriptos.py` | Nuevos inscriptos con formato simple (nombre + email) | `Nuevos Inscriptos.xlsx` |
| `test_migrate_usuarios.py` | Test de validacion sin crear cuentas | `Moodle 2025.xlsx` |

---

## Proceso general (aplica a todos los scripts)

### Etapas por alumno
1. **Crear cuenta Google Workspace** via n8n → Google Admin API
2. **Enviar notificacion** via n8n → email al correo personal con las credenciales
3. **Escribir en xlsx** → nuevo correo, nueva contrasena, Migrado=Si

### Manejo de errores
- Si la cuenta **ya existe** (error 409) → se continua con la notificacion
- Si la **notificacion falla** despues de crear la cuenta → NO se marca Migrado=Si. Al re-ejecutar el script, reintenta solo la notificacion
- Si **falla la escritura** al xlsx → se imprimen las credenciales en consola para no perderlas
- **Es seguro re-ejecutar**: los alumnos marcados como "Si" en la columna Migrado se saltean

### Generacion de email
- Formato: `primer_nombre.apellido@ctcsalto.edu.uy`
- Sin tildes ni caracteres especiales
- Todo en minusculas
- Ejemplos:
  - "Bruno Nahuel Barboza" → `bruno.barboza@ctcsalto.edu.uy`
  - "Fermina Santurio" → `fermina.santurio@ctcsalto.edu.uy`

### Contrasena
- 16 caracteres aleatorios
- Incluye: minusculas, mayusculas, digitos, caracteres especiales (`!@#$%&*-_=+`)

---

## Como usar con un Excel nuevo

### Paso 1: Identificar la estructura del Excel

Antes de ejecutar, abri el Excel y anotá:

```
- Nombre del archivo: ej. "Nuevos Inscriptos 2027.xlsx"
- Nombre de la hoja: ej. "Hoja1"
- Fila donde empiezan los datos: ej. fila 6 (si fila 5 es header)
- Columnas:
  - Columna del nombre: A, B, C...
  - Columna del email personal: A, B, C...
  - El nombre esta junto (nombre completo) o separado (nombre | apellido)?
  - Hay columna de tipo de usuario (Estudiante/Docente)?
  - Hay filas vacias intermedias?
  - Hay filas de encabezado/titulo antes de los datos?
```

### Paso 2: Elegir que script usar o adaptar

**Si el Excel tiene formato simple (2 columnas: nombre completo + email):**
→ Usar `migrate_nuevos_inscriptos.py`

Modificar estas constantes al inicio del script:
```python
XLSX_PATH   = os.path.join(PROJECT_ROOT, "NOMBRE_DEL_ARCHIVO.xlsx")
SHEET_NAME  = "Hoja1"          # nombre de la hoja
HEADER_ROW  = 5                # fila del header (los datos empiezan en HEADER_ROW + 1)

# Columnas (0-indexed: A=0, B=1, C=2...)
COL_NOMBRE_COMPLETO = 0   # columna con el nombre
COL_EMAIL_PERSONAL  = 1   # columna con el email personal
COL_NUEVO_CORREO    = 2   # columna donde se escribe el nuevo email (vacia, se llena)
COL_NUEVA_CONTRA    = 3   # columna donde se escribe la contrasena (vacia, se llena)
COL_MIGRADO         = 4   # columna donde se escribe "Si" (vacia, se llena)
```

**Si el Excel tiene nombre y apellido separados + tipo de usuario:**
→ Usar `migrate_usuarios.py`

Modificar las constantes de columnas segun el nuevo esquema.

**Si la estructura es muy diferente:**
→ Crear un nuevo script basado en `migrate_nuevos_inscriptos.py` (es el mas simple).
Lo importante es que la funcion de lectura retorne una lista de dicts con:
```python
{
    "row":            numero_fila,       # para escribir resultados
    "firstname":      "Bruno",           # primer nombre
    "lastname":       "Barboza",         # apellido
    "email_personal": "algo@gmail.com",  # donde se envia la notificacion
}
```

### Paso 3: Ejecutar

```bash
# Siempre desde la carpeta de scripts:
cd external_services/moodle_api/scripts

# 1. Dry-run primero (SIEMPRE)
python migrate_nuevos_inscriptos.py --dry-run

# 2. Revisar el plan: verificar que los emails generados sean correctos
#    y que no haya duplicados

# 3. Ejecutar la migracion real
python migrate_nuevos_inscriptos.py

# 4. Para un alumno especifico (por nombre parcial):
python migrate_nuevos_inscriptos.py --alumno "Rafel Lupano"
```

### Paso 4: Verificar

- Revisar el reporte final en consola (exitosos vs errores)
- Abrir el Excel: verificar que las columnas de Nuevo Correo, Nueva Contrasena y Migrado se llenaron
- Si hubo errores, re-ejecutar el script: solo procesara los que NO tienen Migrado=Si

---

## Parseo del nombre completo

Cuando el nombre viene en una sola columna (como en `migrate_nuevos_inscriptos.py`):

| Nombre en Excel | Resultado | Email |
|----------------|-----------|-------|
| "Rafel Lupano" (2 palabras) | nombre=Rafel, apellido=Lupano | rafel.lupano@... |
| "Bruno Nahuel Barboza" (3 palabras) | nombre=Bruno, apellido=Barboza | bruno.barboza@... |
| "Fernando Gaston Ferrand" (3 palabras) | nombre=Fernando, apellido=Ferrand | fernando.ferrand@... |

**Regla**: primer token = nombre, ultimo token = apellido (tokens intermedios se ignoran).

**Casos especiales a tener en cuenta:**
- Apellidos compuestos ("De Lima", "Di Donato"): el script toma la ultima palabra. Si el apellido compuesto esta al final (ej: "Juan De Lima") tomaria "Lima" en vez de "De Lima". En ese caso, seria mejor tener nombre y apellido en columnas separadas o ajustar el parseo.

---

## Variables de entorno requeridas (.env)

```
N8N_NOTIFICATION_WEBHOOK_URL=https://...   # webhook de n8n para enviar notificacion
N8N_API_TOKEN=...                          # token de autenticacion para n8n
N8N_HEADER_NAME=Authorization              # nombre del header (default: Authorization)
N8N_TIMEOUT=30                             # timeout en segundos (default: 30)
N8N_BASE_URL=https://...                   # URL base de n8n (para crear cuentas)
N8N_API_TOKEN=...                          # token de n8n
```

---

## Errores comunes

| Error | Causa | Solucion |
|-------|-------|----------|
| "Error al crear la cuenta de Google" | n8n/Google rechazo la creacion | Verificar en Google Admin si la cuenta ya existe. Puede ser por caracteres especiales en el nombre |
| 409 / "already exists" | La cuenta ya existe en Google Workspace | No es error fatal, el script continua con la notificacion |
| "N8N_NOTIFICATION_WEBHOOK_URL no esta definida" | Falta variable en .env | Agregar la URL del webhook de notificacion |
| Timeout | n8n o Google tardaron mucho | Re-ejecutar el script, solo reintenta los pendientes |
| Error escribiendo xlsx | El archivo esta abierto en Excel | Cerrar Excel y re-ejecutar |

---

## Estructura de archivos

```
external_services/moodle_api/scripts/
  migrate_usuarios.py              # migracion desde Moodle 2025.xlsx
  migrate_nuevos_inscriptos.py     # migracion desde Nuevos Inscriptos.xlsx
  test_migrate_usuarios.py         # test de validacion
  actualizar_fotos_perfil.py       # actualiza fotos de perfil en Moodle
  GUIA_MIGRACION.md                # esta guia
```

---

## Informacion para Claude (contexto rapido)

Si necesitas pedirle a Claude que cree un nuevo script de migracion, dale esta info:

1. **Nombre y ubicacion del Excel** (en la raiz del proyecto)
2. **Nombre de la hoja** dentro del Excel
3. **Fila donde empiezan los datos** (despues del header)
4. **Columnas**: que dato tiene cada columna (A, B, C...)
5. **Si el nombre esta junto o separado** (1 columna vs 2 columnas)
6. **Tipo de usuario**: si son todos estudiantes o hay docentes/administrativos
7. **Si hay filas vacias intermedias** o encabezados extras
8. **OU (Organizational Unit)**: /Alumnos, /Equipo Docente, /Administracion y Ventas
9. **Dominio**: ctcsalto.edu.uy

El script base mas simple para copiar y adaptar es `migrate_nuevos_inscriptos.py`.
Reutiliza funciones de `migrate_usuarios.py`: `strip_accents`, `generate_password`, `send_notification`.
