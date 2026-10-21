# Archivos descargables de la oferta académica — guía para frontend

Pedido de dirección (08/10/2026): que cada carrera o curso de la web ofrezca
archivos para descargar (el programa, el plan de estudios, un folleto…).

Son endpoints de **v1** (`/careers`), los mismos de la oferta académica.

---

## Resumen

| Qué | Endpoint | Quién |
|---|---|---|
| Ver los archivos de una carrera | campo `files` en **todas** las respuestas de carreras | público |
| Descargar / abrir un archivo | `GET` a la URL que viene en `files` | público |
| Agregar archivos | `POST /careers/{careerId}/files` | admin |
| Quitar un archivo | `DELETE /careers/{careerId}/files?url=…` | admin |
| Reordenar (o quitar varios) | `PUT /careers/{careerId}/files` | admin |
| Reemplazar uno por otro | `PUT /careers/{careerId}/files/replace?url=…` | admin |
| Subirlos al crear la carrera | `POST /careers/create` acepta `files` | admin |

Los de admin usan el mismo token de siempre: `Authorization: Bearer <token>` de
un usuario con rol admin.

---

## El campo `files`

Una lista de URLs (`string[]`), **en el orden en que se muestran**. Siempre
viene: si la carrera no tiene archivos, es `[]`.

```json
{
  "careerId": 12,
  "name": "Analista Programador",
  "imageLink": "https://…supabase.co/…",
  "files": [
    "https://<backend>/careers/files/12/3f9a1c2e_programa_2026.pdf",
    "https://<backend>/careers/files/12/a71b0d44_plan_de_estudios.docx"
  ]
}
```

Viene en todos los endpoints que devuelven carreras: listados (`/careers/careers`,
`/careers/careers-optimized`, `/careers/public/random`, `/careers/published`…),
detalle (`/careers/{id}`, `/careers/career-optimized/{id}`) y sus versiones de
admin. En `/public/filters` y `/admin/filters` viene si se pide el campo.

**Las URLs son absolutas y se usan tal cual**, en un `<a href>` o un `fetch`. No
hace falta armarlas.

### Nombre para mostrar

El nombre del archivo está en la URL, después del primer `_`:

```
https://<backend>/careers/files/12/3f9a1c2e_programa_2026.pdf
                                    ^^^^^^^^ ^^^^^^^^^^^^^^^^^^
                                    prefijo  nombre (minúsculas, sin tildes, _ en vez de espacios)
```

El backend lo guarda **normalizado**: "Plan de Estudios 2026 (versión final).pdf"
queda `plan_de_estudios_2026_version_final.pdf`. Para mostrarlo lindo:

```js
function nombreArchivo(url) {
  const archivo = decodeURIComponent(url.split('/').pop());   // 3f9a1c2e_programa_2026.pdf
  const sinPrefijo = archivo.slice(archivo.indexOf('_') + 1); // programa_2026.pdf
  const [nombre, ext] = [sinPrefijo.replace(/\.[^.]+$/, ''), sinPrefijo.split('.').pop()];
  const legible = nombre.replace(/_/g, ' ');
  return { legible: legible.charAt(0).toUpperCase() + legible.slice(1), ext }; // "Programa 2026", "pdf"
}
```

La extensión sirve para el ícono (PDF, Word, Excel…).

---

## Descargar: `GET /careers/files/{careerId}/{nombre}`

Público, sin token. Es la URL que viene en `files`.

| Tipo | Qué hace el navegador |
|---|---|
| PDF, JPG, PNG, WebP | **Lo abre** (`Content-Disposition: inline`) |
| Word, Excel, PowerPoint, OpenDocument | **Lo descarga** con su nombre (`attachment`) |

Si se quiere forzar la descarga también de los PDF, usar el atributo `download`:

```html
<a href="{url}" target="_blank" rel="noopener">Ver programa</a>
<a href="{url}" download>Descargar programa</a>
```

- `404` si el archivo no existe (por ejemplo, porque se quitó).
- Responde con `Cache-Control: public, max-age=3600`.

---

## Admin

### Agregar: `POST /careers/{careerId}/files`

`multipart/form-data` con uno o varios archivos en el campo **`files`**
(repetido). Se agregan **al final** de la lista. Devuelve la carrera completa
(`CareerRead`) con el `files` actualizado.

```js
const form = new FormData();
for (const f of inputArchivos.files) form.append('files', f);

const r = await fetch(`${API}/careers/${careerId}/files`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}` },   // NO poner Content-Type: lo arma el navegador
  body: form,
});
const carrera = await r.json();   // carrera.files
```

**Si un archivo no se acepta, no se guarda ninguno** y vuelve `400` con el
motivo, que nombra el archivo:

```json
{ "detail": "'folleto.zip' no es de un tipo aceptado. Se aceptan: doc, docx, jpg, odp, ods, odt, pdf, png, ppt, pptx, webp, xls, xlsx." }
```

### Quitar: `DELETE /careers/{careerId}/files?url=<url>`

La URL **tal cual** está en `files` (en un query param, con `encodeURIComponent`).
Saca el archivo de la lista y lo borra del servidor. Devuelve la carrera.

```js
await fetch(`${API}/careers/${careerId}/files?url=${encodeURIComponent(url)}`, {
  method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
});
```

`404` si esa URL no es de la carrera.

### Reordenar: `PUT /careers/{careerId}/files`

JSON con la lista en el orden nuevo. Sirve para drag & drop. Las URLs que no
vengan se **quitan y se borran** (o sea, también sirve para quitar varias de
una vez).

```js
await fetch(`${API}/careers/${careerId}/files`, {
  method: 'PUT',
  headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({ files: [urlC, urlA, urlB] }),
});
```

- Solo acepta URLs que ya tiene la carrera: **no sirve para agregar** (eso es el POST).
- `400` si viene una URL ajena o repetida.

### Reemplazar: `PUT /careers/{careerId}/files/replace?url=<url>`

Cambia un archivo por otro **en la misma posición** (por ejemplo, el programa
actualizado). `multipart/form-data` con el archivo nuevo en el campo **`file`**
(singular). El anterior se borra.

```js
const form = new FormData();
form.append('file', archivoNuevo);
await fetch(`${API}/careers/${careerId}/files/replace?url=${encodeURIComponent(urlVieja)}`, {
  method: 'PUT', headers: { Authorization: `Bearer ${token}` }, body: form,
});
```

La URL cambia (el archivo nuevo tiene otro nombre): usar el `files` de la respuesta.
Si el archivo nuevo no se acepta, vuelve `400` y **el anterior queda como estaba**.

### Al crear la carrera: `POST /careers/create`

Además de `image` y los campos de siempre, acepta archivos opcionales en
**`files`** (repetido). Se validan antes de crear la carrera: si alguno no
sirve, vuelve `400` y la carrera **no** se crea.

### Editar la carrera (`PUT /careers/{careerId}`)

**No** toca `files`: los archivos se manejan solo con los endpoints de arriba.

---

## Reglas

| | |
|---|---|
| Tipos | **PDF**; **Word** (doc, docx), **Excel** (xls, xlsx), **PowerPoint** (ppt, pptx); **OpenDocument** (odt, ods, odp); **imágenes** JPG, PNG, WebP |
| Tamaño | hasta **20 MB** por archivo |
| Cantidad | hasta **20** archivos por carrera |
| Validación | por el **contenido**, no por la extensión: un `.pdf` que en realidad es otra cosa se rechaza |

Para el `<input>`, sugerido:

```html
<input type="file" multiple
  accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.odt,.ods,.odp,.jpg,.jpeg,.png,.webp">
```

El `accept` es solo ayuda: el backend valida igual.

## Errores

| Código | Cuándo |
|---|---|
| `400` | Tipo no aceptado, archivo vacío, más de 20 MB, más de 20 archivos, URL ajena o repetida al reordenar. El `detail` está en castellano y se puede mostrar tal cual. |
| `401` / `403` | Sin token o el usuario no es admin |
| `404` | La carrera no existe, la URL no es de esa carrera, o el archivo ya no está |

## Caché

Los listados públicos de carreras pasan por Redis, pero cada cambio de archivos
**invalida** el caché de carreras: después de agregar, quitar, reordenar o
reemplazar, los listados ya muestran el cambio.
