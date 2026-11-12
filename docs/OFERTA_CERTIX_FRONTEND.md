# CERTIX en la oferta académica — guía para frontend

CERTIX es la nueva división de certificados del instituto. Algunas carreras,
cursos o talleres tienen **el respaldo de CERTIX** y otras no.

Hay **dos** formas, y conviven:

| | Qué significa |
|---|---|
| `careerType: "certix"` | La oferta **es** de CERTIX (un tipo más, como `career` o `diploma`) |
| `certix: true` | Una oferta de **cualquier** tipo tiene además el **respaldo** de CERTIX |

`GET /careers/types` ya devuelve `certix` entre los tipos, para el selector del admin.
Para filtrar por tipo: `{ "attribute": "careerType", "operator": "eq", "value": "certix" }`.

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
