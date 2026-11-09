# CERTIX en la oferta académica — guía para frontend

CERTIX es la nueva división de certificados del instituto. Algunas carreras,
cursos o talleres tienen **el respaldo de CERTIX** y otras no.

**No es un tipo de oferta nuevo.** `careerType` sigue siendo `career`, `course`,
`workshop` o `diploma`. CERTIX es un campo aparte que se suma: una carrera puede
ser `career` **y** tener respaldo de CERTIX.

Son endpoints de **v1** (`/careers`).

---

## El campo `certix`

Un booleano. Viene en **todas** las respuestas de carreras: listados, detalle,
`career-optimized`, públicos y de admin. Las ofertas que no lo tienen vienen en
`false`.

```json
{
  "careerId": 12,
  "name": "Analista Programador",
  "careerType": "career",
  "certix": true
}
```

Sirve para mostrar el sello o la mención "Respaldo CERTIX" en la tarjeta y en el
detalle de la oferta.

## Filtrar

Con los filtros de siempre (`POST /careers/public/filters` y `/careers/admin/filters`):

```json
{
  "conditions": [
    { "attribute": "certix", "operator": "eq", "value": true }
  ]
}
```

Se combina con lo demás. Por ejemplo, solo las **carreras** con respaldo CERTIX:

```json
{
  "conditions": [
    { "attribute": "certix", "operator": "eq", "value": true },
    { "attribute": "careerType", "operator": "eq", "value": "career" }
  ]
}
```

- El público solo trae ofertas publicadas, como siempre.
- `"value": false` trae las que **no** tienen respaldo.
- Si se piden campos con `fields`, agregar `"certix"` para que venga.

## Cargar y editar (admin)

**Alta** (`POST /careers/create`, multipart): campo **`certix`** en el formulario,
`"true"` o `"false"`. Si no se manda, queda en `false`.

```js
form.append('certix', conCertix ? 'true' : 'false');
```

**Edición** (`PUT /careers/{careerId}`, JSON): mandar `certix` para prenderlo o
apagarlo. Si no se manda, no cambia.

```json
{ "certix": true }
```
