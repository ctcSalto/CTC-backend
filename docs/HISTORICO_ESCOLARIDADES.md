# Histórico de escolaridades (legajo)

Lo que bedelía llevaba en la planilla **`Escolaridades ver 2023.xlsm`** antes
del portal: ~20 años de actas de cursadas, exámenes y talleres. Se cargó en
tablas propias, de solo lectura, para que se pueda consultar desde una pestaña
"Legajo / Histórico" sin mezclarlo con los programas y materias vigentes.

**Estado:** cargado en develop el 11/09/2026. 39 planes, 2.941 personas, 13.624
actas (2004–2026).

---

## 1. Qué había en la planilla

Cuatro hojas, 8 MB, cifrada con contraseña, con macros. Lo que importa:

| Hoja | Qué es | Filas | Se usa |
|---|---|---|---|
| `RESULTADOS` | **Las actas.** Una fila por evaluación de un alumno en una materia | 20.084 | Sí |
| `ALUMNOS` | Tabla de clientes del sistema administrativo viejo (personas, empresas, cuentas contables) | 3.482 | Sí, filtrada |
| `ESCOLARIDAD` | El certificado que bedelía imprimía: fórmulas sobre RESULTADOS + catálogo de planes | — | Solo las fórmulas y el catálogo |
| `Validaciones` | Listas desplegables (planes, materias, docentes, códigos) | — | No |

### Lo que se encontró al analizarla

- **30 % de las actas están duplicadas** (5.992 filas idénticas en las 17
  columnas). Se cargan una sola vez.
- 468 filas tienen solo la inicial del operador: restos de carga. Se saltean.
- Los códigos de plan vienen con variantes (`AP2011` / `AP 2011`, `OPDG` /
  `OP DG`). Se unifican.
- 153 nombres de materia distintos, con variantes de la misma materia entre
  planes (`MARKETING` / `MARKETING `, `TALLER DE FIBRA OPTICA` / `TALLER DE
  FIBRAS OPTICAS`, `INDESING CTC`). Se normalizan mayúsculas y espacios, **no
  se corrigen tipeos**: es la fuente.
- 5 fechas tipeadas a mano (`31/07//2024`, `14/032025`). 4 se rescatan; una es
  imposible (`31/11/2024`) y queda con `fecha = null` y `fecha_texto` con el
  original.
- Valores basura en resultado (`#REF!`, `0`): quedan en `null`.
- `ALUMNOS` mezcla alumnos con UTE, la Intendencia, "COBRANZA A IMPUTAR" y
  proveedores. Solo se toman las filas cuya clave es una cédula (6 a 8 dígitos):
  2.938. De esas, **1.155 tienen actas**; el resto son personas del sistema
  viejo sin actas cargadas (cursos cortos anteriores a 2008, o inscriptos que
  no rindieron).
- 97 filas de `ALUMNOS` están **desplazadas** (cédula y nombre bien, el resto de
  las columnas es de otra persona). De esas se toma solo cédula y nombre, con
  una observación que lo dice.
- 3 personas están en las actas y no en `ALUMNOS`: se crean con el nombre del
  acta.

### Lo que se dejó afuera a propósito

- `cl_observ`: notas de cobranza en RTF ("se le llamó, la mamá arregló con
  Mario…"). No son parte de un legajo académico.
- `cl_ruc`, `cl_cpostal`: basura.
- Las macros, la hoja `Validaciones` y el certificado como tal.

---

## 2. Cómo quedó guardado

Tres tablas nuevas, **sin FK hacia el resto del esquema**. El vínculo con el
portal es por cédula (`usuario.documento`), en consulta.

```
historico_plan          39 filas   codigo ("AP 2011"), carrera, creditos_requeridos
historico_alumno     2.941 filas   cedula, nombre, nombre_busqueda, plan_declarado, zona,
                                   direccion, localidad, departamento, telefono, celular,
                                   email, observaciones, fila_origen
historico_resultado 13.624 filas   alumno_id, plan_id, materia, docente, fecha, fecha_texto,
                                   tipo_evaluacion, resultado, puntaje, puntaje_promedio,
                                   credito, acta, proyecto, observaciones, operador, fila_origen
```

- Los códigos son **texto, no enum de Postgres**: son los códigos históricos de
  bedelía y no se van a extender.
- `fila_origen` es el número de fila en la hoja original, para volver a la
  fuente ante cualquier duda.
- `nombre_busqueda` es el nombre en mayúsculas sin acentos: la búsqueda no
  distingue `NÚÑEZ` de `NUNEZ`.
- Migración: `a7b8c9d0e1f2_historico`. Carga: `v2/scripts/importar_historico.py`.

### Los códigos

| `tipo_evaluacion` | | `resultado` | | `credito` | |
|---|---|---|---|---|---|
| `CUR` | Cursada | `APR` | Aprobado | `T` | Crédito total |
| `EXA` | Examen | `EXO` | Exonerado | `P` | Parcial: cursada aprobada, examen pendiente |
| `TALLER` | Taller | `ELI` | Eliminado | | |
| `REV` | Reválida | `NSP` | No se presentó | | |
| `DIP` | Diploma | `REV` | Revalidado | | |
| | | `EXA` | A examen | | |
| | | `PEND` | Pendiente | | |

`puntaje` es la nota (0–100). `puntaje_promedio` es la nota que bedelía usaba
para promediar: igual a `puntaje` salvo en eliminados y ausentes, donde es 0.
Los dos vienen de la planilla; no se calculan.

Los endpoints devuelven estos diccionarios en `codigos`, para mostrar la
descripción sin hardcodearla en el frontend.

### Los planes

| Código | Carrera | Créditos |
|---|---|---|
| `AP 95` … `AP 2022` | Analista Programador | 23 … 15 según el plan |
| `TA 1996` … `TA 2017`, `TA 2001 N`, `TA 2016 N` | Técnico en Gerencia (N = nocturno) | 15–19 |
| `TEI`, `TEI 2000` … `TEI 2006` | Técnico en Electrónica Informática | 16–18 |
| `TSI 2011` | Técnico en Soporte Informático | 17 |
| `TGDE 2022`, `TGDE 2025` | Técnico en Gestión y Dirección de Empresas | 19, 16 |
| `SJ 2001` | Secretariado Ejecutivo | 16 |
| `XP`, `XP 2001` | Analista en Publicidad | 14 |
| `OP DG`, `OPG` | Operador en Diseño Gráfico | 5 |
| `OPC`, `OP CONT` | Operador Contable | — |
| `AC`, `AC 2016` | Asistente Contable | 1 |
| `EXCEL AV`, `EX+PBI`, `MANT`, `MANT PC`, `D WEB`, `DG`, `CDAV`, `LS`, `LS+GNS`, `RRHH`, `MD`, `ST IT`, `CYN`, `AT.C`, `LOG 2016`, `IA 2024` | Cursos cortos | — |

Carrera y créditos salen del catálogo de la hoja `ESCOLARIDAD`. Para los cursos
cortos, que no estaban en ese catálogo, la carrera se dedujo de las materias que
contienen (`EXCEL AV` → "Excel Avanzado"). El catálogo completo está en
`CATALOGO_PLANES` del importador.

---

## 3. El resumen por plan (lo que decía el certificado)

La hoja `ESCOLARIDAD` calculaba, por alumno y plan, **créditos aprobados,
créditos revalidados y promedio**. El endpoint del legajo devuelve lo mismo,
con las mismas reglas, para que el número que ve el alumno sea el que le daban
antes:

| Regla | Fórmula de la hoja | Qué significa |
|---|---|---|
| Otorga crédito | `(EXA o TALLER) con nota ≥ 70`, o `CUR + EXO`, o tipo `REV` | Examen o taller aprobado, cursada exonerada, o reválida |
| Cuenta en el promedio | Todo salvo tipo `REV` y `CUR + APR` | La cursada aprobada espera el examen: no cierra nada |
| Nota que promedia | La nota si es examen, taller o cursada exonerada; si no, 0 | **Un eliminado cuenta con 0.** Es duro, pero es la regla que se venía aplicando |
| Revalidado | Resultado `REV` | |
| Promedio | `Σ nota / (filas que cuentan − revalidadas)` | |

**Es la fórmula de la hoja tal cual, con su rareza incluida:** al restar las
revalidadas del divisor, la hoja resta *todas* las filas con resultado `REV`,
incluso las de tipo `REV` que ya no había contado. En 27 de 1.457 pares
alumno-plan eso deja el divisor más chico de lo que "debería", y en uno lo
deja en 0 (`#DIV/0!` en la hoja; `promedio: null` acá). **Se decidió dejarlo
así el 11/09/2026**: el número tiene que ser el mismo que bedelía tiene en su
Excel y en los certificados que ya emitió.

Verificado contra el certificado que estaba armado en la planilla (una
alumna de AP 2022): 6 créditos, 0 revalidados, promedio 30,375. Da lo
mismo. Está como test en `v2/tests/test_historico.py`.

### General y por plan

El certificado de bedelía filtra por documento con **`CARRERA = (Todas)`**:
un alumno que pasó de AP 2020 a AP 2022 promedia **todas** sus actas juntas.
Por eso el legajo trae dos niveles:

- **`general`** — todas las actas de la persona, de todos los planes. Es el
  número del certificado. Los créditos requeridos se toman del plan del acta
  más reciente (en el Excel salen del PLAN que bedelía elige a mano).
- **`planes`** — el mismo cálculo plan por plan, que es lo que ve bedelía si
  filtra una carrera en el certificado.

No es un detalle: **250 de los 1.155 alumnos con actas tienen actas en más de
un plan.** Caso real que trajo bedelía el 22/09/2026: AP 2020 → AP 2022,
recursó Programación 1 tres veces, promedio del certificado 281 / 8 = 35,13.
El general da eso; los dos planes por separado darían 24,25 y 46,0.

**Recursar baja el promedio**, y es a propósito: cada cursada eliminada suma
0 al numerador y 1 al divisor. Es la regla de bedelía.

**Redondeo:** como Excel, hacia arriba en el medio (35,125 → 35,13). El
`round()` de Python redondea al par y daría 35,12.

---

## 4. Endpoints

Todos de **solo lectura**. Los de admin requieren rol `ADMINISTRATIVO`.

### `GET /v2/admin/historico/alumnos` — buscar personas

| Query | | |
|---|---|---|
| `q` | Cédula (prefijo, con o sin puntos) o parte del nombre (sin distinguir acentos) | mín. 2 caracteres |
| `plan` | Código exacto, ej. `AP 2011`: solo quienes tienen actas en ese plan | |
| `solo_con_resultados` | `true` excluye a las 1.786 personas sin actas | default `false` |
| `limit` / `offset` | Paginado | 50 / 0, máx. 200 |

```json
{
  "total": 3, "limit": 50, "offset": 0,
  "items": [
    {
      "id": 812, "cedula": "41234567", "nombre": "PEREZ GOMEZ JUAN",
      "plan_declarado": "AP 2011",
      "planes": ["AP 2011", "TSI 2011"],
      "cantidad_resultados": 40,
      "primera_fecha": "2013-05-23", "ultima_fecha": "2016-12-20"
    }
  ]
}
```

`planes` y las fechas salen de las actas; `plan_declarado` es lo que decía la
hoja `ALUMNOS` y puede no coincidir (o ser `null`).

### `GET /v2/admin/historico/alumnos/{cedula}` — el legajo

La cédula puede venir con puntos y guion. `404` si no existe.

```json
{
  "alumno": {
    "id": 812, "cedula": "41234567", "nombre": "PEREZ GOMEZ JUAN", "plan_declarado": "AP 2011",
    "zona": "11AP", "direccion": "…", "localidad": "SALTO", "departamento": "15",
    "telefono": "…", "celular": "…", "email": "…", "observaciones": null
  },
  "general": {
      "plan": "(Todas)", "carrera": null, "creditos_requeridos": 17,
      "creditos_aprobados": 13, "creditos_revalidados": 0, "promedio": 76.4,
      "cantidad_resultados": 22, "por_resultado": {"APR": 12, "EXO": 4, "ELI": 6},
      "materias_aprobadas": ["…"], "primera_fecha": "2011-07-15", "ultima_fecha": "2015-07-22"
  },
  "planes": [
    {
      "plan": "TSI 2011", "carrera": "Tecnico en Soporte Informatico",
      "creditos_requeridos": 17, "creditos_aprobados": 12, "creditos_revalidados": 0,
      "promedio": 78.5, "cantidad_resultados": 18,
      "por_resultado": {"APR": 10, "EXO": 3, "ELI": 5},
      "materias_aprobadas": ["INFRAESTRUCTURA DE REDES", "REDES LAN", "…"],
      "primera_fecha": "2013-05-23", "ultima_fecha": "2015-07-22"
    }
  ],
  "resultados": [
    {
      "id": 5012, "plan": "TSI 2011", "carrera": "Tecnico en Soporte Informatico",
      "materia": "REDES LAN", "docente": "QUEVEDO, FERNANDO",
      "fecha": "2013-12-23", "fecha_texto": null,
      "tipo_evaluacion": "CUR", "tipo_evaluacion_descripcion": "Cursada",
      "resultado": "EXO", "resultado_descripcion": "Exonerado",
      "puntaje": 90, "puntaje_promedio": 90, "credito": "T",
      "acta": "2376", "proyecto": null, "observaciones": null,
      "otorga_credito": true
    }
  ],
  "codigos": {
    "tipo_evaluacion": {"CUR": "Cursada", "EXA": "Examen", "…": "…"},
    "resultado": {"APR": "Aprobado", "…": "…"},
    "credito": {"T": "Credito total", "P": "…"}
  }
}
```

- **`general` es el número a mostrar primero**: es el del certificado. Si la
  persona tiene un solo plan, coincide con `planes[0]`. `carrera` viene `null`
  cuando mezcla carreras distintas.
- `planes` viene ordenado por primera fecha; `resultados` por fecha ascendente,
  con las de fecha `null` al final.
- `otorga_credito` ya viene calculado por fila: sirve para marcar en la tabla
  qué cerró y qué no.
- Sobre `zona`: es un código de la planilla que parece ser año de ingreso +
  carrera (`11AP` = ingresó en 2011 a AP). No está confirmado; mostrarlo como
  dato secundario o no mostrarlo.
- Los datos de contacto son los del sistema viejo, posiblemente desactualizados.

### `GET /v2/admin/historico/planes` — catálogo con conteos

```json
[
  {"id": 43, "codigo": "AP 2007", "carrera": "Analista Programador", "creditos_requeridos": 17,
   "cantidad_alumnos": 260, "cantidad_resultados": 3110,
   "primera_fecha": "2008-01-30", "ultima_fecha": "2017-12-13"}
]
```

Para armar el filtro de plan.

### `GET /v2/admin/historico/materias?plan=` — nombres de materia

```json
[{"materia": "ALGORITMOS Y ESTRUCTURAS DE DATOS", "cantidad": 37}, …]
```

Para armar el filtro de materia. Sin `plan` trae los 153 nombres; con `plan`,
solo los de ese plan.

### `GET /v2/admin/historico/resultados` — buscar actas

Filas sueltas, sin pasar por el alumno. Para responder "quiénes rindieron X en
tal fecha" o "qué hay en el acta 2961".

| Query | |
|---|---|
| `cedula` | exacta |
| `plan` | código exacto |
| `materia` | parte del nombre |
| `tipo_evaluacion`, `resultado` | código exacto |
| `acta` | número exacto |
| `desde`, `hasta` | `YYYY-MM-DD`, sobre `fecha` |
| `limit` / `offset` | 100 / 0, máx. 500 |

Devuelve `{total, limit, offset, items}`; cada item es una fila como las del
legajo más `"alumno": {"id", "cedula", "nombre"}`. Ordenadas de la más reciente
a la más vieja.

### `GET /v2/portal/estudiante/mi-historico` — el propio legajo

Rol `ESTUDIANTE`. Busca por `usuario.documento`. Misma respuesta que el legajo
de admin.

| Caso | Respuesta |
|---|---|
| El usuario no tiene `documento` cargado | `404` "No tenés documento cargado en tu usuario" |
| Tiene documento pero no figura en el histórico | `404` "No hay legajo histórico para tu documento" |

**No requiere perfil de alumno del portal**: un egresado de 2010 que entra con
su cuenta institucional puede ver su legajo aunque nunca se haya inscripto a
nada en el sistema nuevo. Lo que sí necesita es que bedelía le haya cargado el
documento en el usuario.

---

## 5. Para la pestaña del frontend

Una propuesta de mínima, en dos pantallas:

**Listado** — un buscador (`q`), un select de plan (de `/planes`) y el toggle
"solo con actas". Tabla con nombre, cédula, planes (chips), cantidad de actas y
rango de fechas. Click → legajo.

**Legajo** — cabecera con los datos de la persona y el resumen `general`
(créditos y promedio del certificado); una tarjeta por plan con créditos
aprobados / requeridos, promedio y el desglose `por_resultado`; y la
tabla de actas ordenada por fecha con fecha, plan, materia, tipo, resultado,
nota, crédito, acta y docente. Marcar las filas con `otorga_credito`. Para las
descripciones usar `codigos`.

En el portal del estudiante es la misma pantalla de legajo, pegándole a
`/mi-historico`.

Lo que **no** hay ni va a haber: edición. Si bedelía encuentra un error, se
corrige en la planilla y se reimporta.

---

## 6. Volver a cargar

Si la planilla se corrige y hay que recargarla:

```bash
# 1. Guardar la planilla sin contraseña (Archivo > Información > Proteger libro > Cifrar > borrar)
# 2. Ver qué haría, sin escribir
python -m v2.scripts.importar_historico "ruta/Escolaridades.xlsx" --dry-run
# 3. Cargar, pisando lo que hay
python -m v2.scripts.importar_historico "ruta/Escolaridades.xlsx" --reemplazar
```

El script se niega a correr sobre tablas con datos si no se pasa
`--reemplazar`. Si la planilla cambió de columnas, frena con un mensaje que dice
qué columna esperaba y dónde. El informe final dice cuántas filas cargó, cuántas
descartó y por qué.

Los IDs cambian con cada recarga: el frontend no debe guardar `id` de
resultados; la cédula es el identificador estable.
