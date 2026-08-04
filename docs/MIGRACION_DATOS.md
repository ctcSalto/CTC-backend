# Carga inicial del Portal Académico

Plan para pasar de la base actual a un portal usable con alumnos reales.

---

## 1. De qué partimos

Inventario de `develop` al 03/08/2026:

| Tabla | Filas | Comentario |
|---|---|---|
| `programa` | 1 | Analista Programador |
| `materia` | 3 | PROG1, PROG2, BD1 |
| `previatura` | **1** | solo PROG2 → PROG1 |
| `inscripcion_programa` | **0** | nadie inscripto a ninguna carrera |
| `alumno` | 4 | de prueba |
| `profesor` | 1 | de prueba |
| `usuario` | 12 | 6 estudiantes, 3 docentes, 3 administrativos |
| `politica_calificacion` | 2 | base 100 (70/86) y curso corto |

**Lo que hay en `develop` son datos de prueba, no datos reales.**

### Las previaturas sí están definidas — pero nunca llegaron a la base

La migración `f3g4h5i6j7k8_seed_previaturas` (03/05/2026) tiene la malla completa
que salió de `moodle_materias_previaturas.xlsx`: **44 previaturas sobre 40
materias**, en dos programas (Analista Programador y Técnico en Gestión y
Dirección de Empresas), más la regla de que el Integrador requiere todas.

Esa migración **corrió y no insertó nada**. Resuelve cada materia por nombre
exacto contra la tabla `materia`, que en ese momento estaba vacía: cada búsqueda
devolvió `None` y siguió de largo en silencio. De las 40 materias que menciona,
hoy encuentra **1**. Ignorando tildes y mayúsculas encontraría 3 — el seed busca
`Programación 1` y en la base figura `Programacion 1`.

La única previatura que hay en la tabla tiene `id_rastreo = NULL`, y el seed
siempre asigna un UUID: **no la creó el seed**, se cargó a mano o desde un test.

Alembic no vuelve a correr una revisión ya aplicada, así que esos datos quedaron
en el repo sin forma de llegar a la base por sí solos. La malla se movió a
[`v2/scripts/malla_inicial.py`](../v2/scripts/malla_inicial.py) como fuente única,
y desde ahí la planilla la precarga: bedelía **no tiene que volver a escribir las
44 previaturas**, solo revisarlas.

Lo que falta de verdad es la tabla `materia` — nada en el repo la carga, ni
migración ni script. Y con ella, alumnos, docentes e historial.

`inscripcion_programa` en 0 es bloqueante por sí solo: el portal del estudiante
devuelve **403** si el alumno no tiene inscripción activa a un programa. Sin esa
tabla poblada, ningún alumno ve nada.

---

## 2. Cómo se carga

Tres pasos, con la planilla en el medio para que administración trabaje en
paralelo mientras se termina el backend.

### Paso 1 — Generar la planilla

```bash
python -m v2.scripts.generar_planilla_migracion
```

Produce un `.xlsx` con siete hojas:

| Hoja | Qué lleva |
|---|---|
| `LEEME` | instrucciones, en criollo |
| `1-Alumnos` | personas + a qué carrera pertenecen |
| `2-Docentes` | personas, incluidos los que ya no dictan |
| `3-Plan de estudios` | 40 materias **precargadas**; falta semestre y créditos |
| `4-Previaturas` | 44 requisitos **precargados**; solo hay que revisarlos |
| `5-Historial` | alumno × materia × estado — **la importante** |
| `6-Dictado actual` | quién dicta qué este semestre |

Decisiones de diseño, todas por el mismo motivo — que lo que vuelva sea
importable sin interpretar nada a mano:

- **Todo se referencia por documento (cédula)**, no por nombre ni por id interno.
  Es la única clave estable que bedelía maneja. El validador normaliza puntos y
  guiones, así que `4.123.456-7` y `41234567` son la misma persona.
- **Listas desplegables** en cada columna de valor cerrado. Sin eso, la columna
  estado vuelve con `aprobado`, `APROBADO`, `Aprobó`, `ex.` y `exo`.
- **Lo que ya sabemos viene precargado.** Gris = está en la base. Verde = sale de
  la malla ya definida y todavía no llegó a la base. Bedelía corrige o completa,
  no tipea de cero. En concreto: las 44 previaturas llegan hechas y de las 40
  materias solo falta el semestre del plan y los créditos.
- **La materia se identifica por nombre, no por código.** `Materia.codigo` es
  nullable en el modelo y la malla que ya tenemos vino sin códigos, así que
  exigirlos sería inventar un requisito que el sistema no tiene. Las hojas que
  referencian materias aceptan las dos formas; el validador resuelve nombres
  ignorando tildes y mayúsculas, y avisa si un nombre existe en dos carreras.
- **Vocabulario reducido** en el historial: cinco estados, no los ocho del enum.
  Administración no lleva registro de "perdido por inasistencia" de hace cuatro
  años, y ofrecer opciones que nadie va a usar bien solo genera ruido.

| En la planilla | En el sistema |
|---|---|
| `APROBADA` | `APROBADO` |
| `EXONERADA` | `EXONERADO` |
| `A_EXAMEN` | `A_EXAMEN` |
| `CURSANDO` | `CURSANDO` |
| `RECURSA` | `REPROBADO` |
| *(sin fila)* | nunca la cursó |

`A_EXAMEN` está aunque parezca un detalle: hay alumnos que arrastran materias
con derecho a examen durante años, y si eso se pierde en la migración quedan
como si nunca las hubieran cursado.

### Paso 2 — Validar lo que devuelvan

```bash
python -m v2.scripts.validar_planilla_migracion carga_inicial.xlsx --reporte errores.txt
```

No toca la base. Se puede correr las veces que haga falta, y el `.txt` se le
reenvía a administración tal cual.

Separa **ERROR** (impide importar la fila) de **AVISO** (se importa, pero
conviene mirarlo). Verifica, entre otras cosas: cédulas con formato válido y
consistentes entre hojas, códigos de materia que existan y sean únicos,
previaturas dentro del mismo programa, **ciclos de previaturas**, notas en rango,
estados dentro del vocabulario, y una fila por alumno y materia.

**El chequeo que más importa** es el de cadenas incompletas: si un alumno figura
con Programación 2 aprobada pero Programación 1 no aparece en su historial, sale
un aviso. Casi siempre significa que falta cargar historial viejo. Si eso no se
corrige antes de importar, el día uno el portal le bloquea la inscripción a ese
alumno y bedelía reporta que el sistema está roto.

### Paso 3 — Importar

Pendiente de escribir. Se hace cuando vuelva la primera planilla con datos
reales: el importador depende de cómo se vean los datos de verdad, y escribirlo
antes es adivinar. Va a tener `--dry-run` y ser idempotente (correrlo dos veces
no duplica nada).

Tiene que resolver los nombres **ignorando tildes y mayúsculas**. Es exactamente
el error que dejó el seed sin efecto, y se repite solo si se vuelve a comparar
con igualdad exacta.

---

## 3. Historial viejo y previaturas

El punto que hay que resolver bien.

Las inscripciones a materia cuelgan de una `instancia_cursado` — el dictado
concreto de una materia en un año. Para el historial viejo esas instancias no
existen. Dos caminos:

**(a) Crear una instancia por (materia, año) que aparezca en el historial**,
marcada como `FINALIZADA`, y colgar de ahí las inscripciones con su estado y
nota. Preserva el historial con fechas reales y el motor de previaturas funciona
solo, sin casos especiales.

**(b) Cargar todo como `REVALIDADA`.** Más rápido, pero está mal: `REVALIDADA`
significa "estudios hechos en otra institución", y además **corta la regla de
cumplimiento pleno** — o sea que desactivaría el control de cadena de previaturas
para toda la población migrada, justo lo que se acaba de implementar.

**Recomendación: (a).** El costo extra es generar instancias sintéticas, que es
código, no trabajo de bedelía.

---

## 4. Lo que no depende de la planilla

### Cuentas de Google

El login de v2 es Google OAuth restringido a `@ctcsalto.edu.uy`. **Un alumno sin
cuenta institucional no puede entrar**, por más que esté cargado en la base.

`Usuario.email` es nullable justamente para esto: se puede cargar la persona sin
cuenta y crearla después. Pero eso significa que la creación de cuentas (vía los
webhooks de n8n) es un frente paralelo, y para una fecha de fin de mes es lo que
más riesgo de calendario tiene: no depende de nosotros ni de bedelía.

Conviene arrancarlo ya, con la lista de alumnos, sin esperar el resto de la
planilla.

### Usuarios de v1

`user` en v1 son cuentas del sitio público (gente que se registró para consultar
carreras), no el padrón académico. No son la misma población y no tienen
necesariamente cuenta institucional. **No dar por hecho que migran solos**: hay
que cruzar por documento y ver cuántos coinciden de verdad.

### Políticas de calificación

Ya están cargadas y coinciden con la regla vigente: base 100, `<70` reprueba,
`70-85` derecho a examen, `>=86` exonera. No requiere trabajo de administración.

Falta definir la política de examen de **Base de Datos 1**, que tiene
`politica_examen_id` en null mientras las otras dos materias la tienen.

---

## 5. Antes de importar en producción

- [ ] Migraciones 13, 14, 15 y `d2e3f4a5b6c7` aplicadas (ver
      [PENDIENTES_PRODUCCION.md](../PENDIENTES_PRODUCCION.md))
- [ ] `V2_ENABLED=true`
- [ ] `python -m v2.scripts.verificar_ciclos_previaturas` en verde
- [ ] Validador sin errores y con los avisos revisados uno por uno
- [ ] Backup de la base **antes** de correr el importador
- [ ] Importador en `--dry-run` primero, comparando totales contra la planilla
- [ ] Una escolaridad real (`GET /v2/portal/estudiante/mi-escolaridad`) contrastada
      contra el papel de bedelía, antes de dar acceso a nadie
