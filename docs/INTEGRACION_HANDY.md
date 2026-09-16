# Integración con Handy — análisis previo

Estado al 10/09/2026: **integración implementada, pendiente de probar contra
el ambiente de testing de Handy.**

Hecho: tablas (`pago`, `pago_notificacion`), cliente HTTP, servicio con la
máquina de estados y las validaciones, webhook, endpoints de alumno y admin,
informes, 53 tests. Detalle de endpoints en
[v2/API_ENDPOINTS_V2.md §16.b](../v2/API_ENDPOINTS_V2.md). Variables de entorno
en [PENDIENTES_PRODUCCION.md](../PENDIENTES_PRODUCCION.md).

Falta: correr un cobro real contra testing con las tarjetas del manual, y con
eso pedirle a Handy el secret de producción.

Escrito el 28/08/2026 sobre los manuales oficiales, actualizado con las
respuestas.

Fuentes leídas (los PDF, no la página):
- Botón de Pago, manual de integración **v2.0** (30/09/2025)
- Checkout API, manual de integración **v4.2** — es el manual de **Plexo**

---

## Recomendación: Botón de Pago

Tu intuición era correcta en el diagnóstico, pero el motivo es más fuerte de lo
que parecía. No es solo que no haya SDK de Python: **el Checkout API ni siquiera
es REST**.

| | Botón de Pago | Checkout API (Plexo) |
|---|---|---|
| Endpoint | `https://api.payments.handy.uy/api/v2` | `https://testing.plexo.com.uy:4043/SecurePaymentGateway.svc` |
| Protocolo | REST + JSON | `.svc` — WCF/SOAP |
| Autenticación | un header, `merchant-secret-key` | certificado `.pfx` con clave privada, **firmando y canonicalizando cada mensaje** |
| Alta previa | ninguna | `AddCommerce` + código de comercio de **cada sello** (Visa, MC, OCA…) negociado por separado |
| Datos de tarjeta | nunca tocan nuestro servidor | `AddInstrument` los recibe directo → **alcance PCI** |
| Esfuerzo | bajo | alto |

El manual de Plexo dice textual que el firmado y la canonicalización quedan fuera
de sus ejemplos y dependen del canal — que es justo la parte difícil, y en Python
sin SDK hay que implementarla a mano contra un servicio WCF. Es el tipo de cosa
que se lleva semanas y falla en producción por un espacio en blanco.

**Para vender cursos no hace falta nada de eso.** El redirect a una página
hospedada por Handy es UX aceptable para este caso, y nos deja fuera del alcance
PCI, que es una ventaja real y no un detalle.

Cubre además todos los medios que interesan: tarjetas (Visa, Mastercard, OCA,
Amex, Cabal, Passcard, Anda, Club del Este, Edenred), **Redpagos** y
transferencias bancarias (Itaú, BROU, Scotiabank, BBVA, Bandes).

---

## Cómo funciona

### 1. Crear el link de pago

```http
POST {base}/payments
merchant-secret-key: {secret}
Content-Type: application/json
```

```json
{
  "Cart": {
    "Currency": 858,
    "TotalAmount": 5.00,
    "TaxedAmount": 4.10,
    "InvoiceNumber": 123457,
    "TransactionExternalId": "b4a8e7c3-5d41-4b8f-a23a-9c7d1f31e8f0",
    "LinkImageUrl": "https://.../curso.jpg",
    "Products": [
      { "Name": "Caramelo", "Quantity": 1, "Amount": 5.00, "TaxedAmount": 4.10 }
    ]
  },
  "Client": { "CommerceName": "CTC Salto", "SiteUrl": "https://ctcsalto.edu.uy" },
  "CallbackUrl": "https://.../v1/handy/webhook",
  "ResponseType": "Json"
}
```

Devuelve `{"url": "https://pago.arriba.uy?sessionId=..."}`. Se redirige al
comprador ahí. **El link sirve una sola vez.**

- `Currency` es ISO 4217 numérico: **858** peso uruguayo, **840** dólar
- `TaxedAmount` es el monto gravado; si está exento de IVA va 0
- `TotalAmount` es el total **con** IVA
- `TransactionExternalId` lo generamos nosotros y es la clave para conciliar y
  para devolver después. Un UUID por intento de pago

### 2. El webhook

Handy hace `POST` con JSON a `CallbackUrl` en cada cambio de estado:

```json
{
  "TransactionExternalId": "b4a8e7c3-...",
  "PurchaseData": {
    "Status": 1,
    "Created": "2025-10-07T12:28:13Z",
    "TotalAmount": 5, "TaxedAmount": 4.1, "Currency": 858,
    "Products": []
  },
  "InstrumentData": {
    "Name": "520394XXXXXX3450",
    "IssuerName": "MasterCard",
    "NotACard": false,
    "Expiration": null
  }
}
```

| `Status` | Significado |
|---|---|
| 0 | Pago iniciado (no llega siempre) |
| 1 | **Pago exitoso** |
| 2 | Pago fallido |
| 3 | Pendiente de pago |

El 3 importa: **Redpagos genera un pendiente** con `Expiration`, y el alumno paga
después en el local. Ahí el curso todavía no está pago.

### 3. Devoluciones

`DELETE {base}/payments` con `TransactionExternalId` y `CallbackUrl`. Una sola vez
por venta, solo con tarjeta (Redpagos y transferencias no admiten), tope UYU
10.000 / USD 250. El resultado llega por webhook, no en la respuesta.

---

## ⚠️ El problema de seguridad

> **Actualizado 10/09/2026 — Handy respondió y confirmó el peor escenario.**
> No hay firma, no hay endpoint de consulta, no publican IPs y **tampoco hay
> reintentos**. Este último punto no estaba previsto y es el que más condiciona
> el diseño: un webhook perdido no se recupera de ninguna forma.
> Ver [HANDY_RESPUESTAS.md](HANDY_RESPUESTAS.md).

**El webhook no viene firmado.** El manual v2.0 no menciona HMAC, firma, token ni
ninguna validación de origen. Cualquiera que descubra la URL puede mandar un
`Status: 1` y hacernos creer que un curso está pago.

Y no hay salida fácil: **el manual no documenta ningún endpoint para consultar el
estado de un pago.** Solo `POST /payments` (crear) y `DELETE /payments`
(devolver). O sea que no podemos confirmar contra Handy lo que nos llega.

Mitigaciones que sí podemos aplicar:

1. **URL de callback con un segmento secreto de alta entropía**, distinta por
   ambiente. No es autenticación de verdad, pero saca del juego al que escanea.
2. **Exigir que el `TransactionExternalId` exista** en nuestra base, en estado
   pendiente, con el monto y la moneda que esperábamos. Como el GUID lo generamos
   nosotros y no es público, el atacante tendría que adivinarlo.
3. **Idempotencia**: el mismo `TransactionExternalId` no puede acreditar dos veces.
4. **Registrar todos los webhooks recibidos** en crudo, aceptados y rechazados.
   Sin poder consultar el estado, ese log es la única pista para conciliar.
5. ~~Allowlist de IPs~~ — **descartado:** Handy no publica un rango fijo.

6. **El endpoint no puede devolver 500 nunca, ni ante un error nuestro.** Como no
   hay reintentos, un error de nuestro lado cuesta el aviso de pago. Hay que
   recibir, persistir en crudo, responder 200 y procesar después.

7. **Informe de pagos pendientes** para bedelía: sin endpoint de consulta ni
   reintentos, cotejar a mano contra el panel de Handy es el único mecanismo de
   recuperación cuando se pierde un aviso.

---

## Respuestas de Handy — recibidas

Las consultas se enviaron y **Handy respondió el 10/09/2026**. El detalle
completo, con el impacto de cada respuesta sobre el diseño, está en
[HANDY_RESPUESTAS.md](HANDY_RESPUESTAS.md).

Lo que quedó definido:

- **Sin firma de webhook.** La validación es contra nuestro propio registro.
- **Sin endpoint de consulta.** Todo por callbacks.
- **Sin IPs publicadas.**
- **Sin reintentos** ante fallo de entrega. Lo más determinante del diseño.
- Rubro: **escuela y servicios educativos** → Amex y Passcard sí, Edenred no.
- El secret de producción se pide **después** de validar la integración en testing.

**Ambiente de pruebas:**
- Base testing: `https://api.payments.arriba.uy/api/v2`
- Tarjetas: Mastercard `5203948100023450` 12/26 CVV 045 · Cabal
  `5896572099999991` 03/80 CVV 450
- El propio manual avisa que *"el ambiente de pruebas de los medios de pago no
  siempre funciona correctamente"*

---

## Decidido: conviven las dos pasarelas

**MercadoPago se queda**, aunque no se use para cursos, y a futuro puede sumarse
alguna más para vender al exterior.

Eso cambia el diseño, y conviene tenerlo en cuenta ahora: no estamos integrando
Handy, estamos **agregando el primer proveedor a un modelo de pagos que va a
tener varios**. La diferencia se paga barata hoy y cara después.

### Dónde sí abstraer y dónde no

**Los datos, sí.** La tabla de pagos tiene que ser agnóstica del proveedor desde
el día uno: agregarle una columna `proveedor` ahora no cuesta nada, y migrar
después una tabla llena de pagos reales de `pago_handy` a un modelo genérico es
un trabajo que nadie quiere hacer.

**El código, no.** Nada de armar una interfaz de pasarelas ni un registry de
proveedores con un solo proveedor real funcionando. Cada uno vive en su módulo
bajo `external_services/`, con su cliente y su webhook, y el patrón común aparece
solo cuando haya dos integraciones andando de verdad y se vea cuál es. Abstraer
antes de eso es adivinar.

Lo que sí conviene desde el principio es que los dos converjan en **el mismo
estado interno**, para que el resto del sistema no tenga que saber quién cobró.

### El identificador es lo que hace fácil la convivencia

Handy usa `TransactionExternalId`, un GUID **que generamos nosotros**.
MercadoPago tiene `external_reference`, que cumple exactamente el mismo rol.

O sea que la clave de conciliación es nuestra en los dos casos: una fila en
nuestra tabla, un identificador propio, y cada proveedor guarda además el suyo.
Cualquier pasarela que sumemos después va a tener su equivalente.

### Estados internos, no los del proveedor

Handy maneja `0/1/2/3`; MercadoPago tiene los suyos. Guardar el código crudo del
proveedor y además un estado normalizado nuestro:

| Interno | Handy | Qué significa |
|---|---|---|
| `INICIADO` | 0 | Se creó el link, nadie pagó todavía |
| `PENDIENTE` | 3 | Esperando pago offline (Redpagos, con vencimiento) |
| `PAGADO` | 1 | Acreditado |
| `FALLIDO` | 2 | Rechazado |
| `DEVUELTO` | — | Llega por el webhook de devolución |

Así, el día que se venda al exterior con otra pasarela, quien consulta si un
curso está pago no cambia.

---

## Estado de la implementación (16/09/2026)

Todo lo de arriba está implementado y mergeado en `develop`:

| Qué | Dónde |
|---|---|
| Tablas `pago` y `pago_notificacion` | migración `a6b7c8d9e0f1`, aplicada en develop |
| Cliente HTTP (crear link, devolver) | `external_services/handy_api/client.py` |
| Máquina de estados, webhook, inscripción al pagar | `v2/services/pago_service.py` |
| Endpoints de alumno, admin, informes y acciones | `v2/routes/pagos.py` |
| Contrato de salida probado contra testing real | 11/09/2026 (ver `HANDY_RESPUESTAS.md`) |
| Webhook de entrada probado de punta a punta | **pendiente** — ver abajo cómo |

MercadoPago sigue como estaba, en `external_services/`, sin tocar.

---

## Operación: lo que hace bedelía

Handy no reintenta ni permite consultar, así que hay tres situaciones que
**no se resuelven solas** y para las que existe una acción en el panel de admin.

### Un cobro que quedó en `iniciado`

El alumno dice que pagó y en el portal figura iniciado. Causas posibles: no
terminó de pagar, o pagó y el aviso se perdió (el servidor estaba reiniciando,
un corte de red, etc.).

1. `GET /v2/admin/pagos/informes/pendientes` lo lista.
2. Se busca en el **panel de Handy** por fecha y monto (o por la referencia,
   que Handy guarda como `TransactionExternalId`).
3. Si en Handy está cobrado: `POST /v2/admin/pagos/{id}/conciliar` con
   `{"estado": "pagado", "motivo": "…", "proveedor_id": "…"}`. Eso pasa el cobro
   por la misma máquina de estados que un aviso real, **habilita la
   inscripción**, y deja registrado quién lo hizo y por qué.
4. Si en Handy no existe o figura rechazado: lo mismo con `"estado": "fallido"`.
   El alumno vuelve a intentar y se genera otro link.

Si el aviso de Handy llega después de conciliar, cae en "mismo estado, sin
efecto": no duplica nada.

### Una devolución

`POST /v2/admin/pagos/{id}/devolver`. Solo para cobros en `pagado`. Handy
acepta el pedido en el momento y **responde el resultado después por
webhook**: el cobro pasa a `devuelto` recién cuando llega ese aviso. Mientras
tanto queda `estado_proveedor = devolucion_solicitada` y no se puede pedir dos
veces.

Restricciones de Handy que el backend chequea antes de llamar: tope UYU
10.000 / USD 250. Las que no puede chequear (una sola vez por venta, solo
tarjeta) las rechaza Handy con un 400 que se devuelve tal cual.

Si el aviso de la devolución se pierde, se concilia igual que un pago:
`conciliar` con `"estado": "devuelto"`.

### Un pago sin alumno

Venta desde el CRM a alguien que todavía no tiene usuario. Queda `pagado` sin
inscripción; `GET /v2/admin/pagos/informes/sin-inscripcion` lo lista. Se crea
el alumno y se vincula a mano (no hay endpoint para eso todavía: se decide
cuando esté el CRM).

---

## Cómo probar de punta a punta (testing)

Lo único que no se puede probar con dobles es que **Handy alcance nuestro
webhook**. Hace falta un backend con URL pública configurado con:

```
HANDY_BASE_URL=https://api.payments.arriba.uy/api/v2
HANDY_MERCHANT_SECRET=<el de testing del manual>
HANDY_WEBHOOK_SECRETO=<openssl rand -hex 32>
BASE_URL=<URL pública del backend>
V2_ENABLED=true
```

Y en la máquina desde la que se corre la prueba, las mismas cinco variables
en el `.env` (`DATABASE_URL` apuntando a la **misma base** que ese backend, y
el **mismo** `HANDY_WEBHOOK_SECRETO`: el callback lo lleva en la ruta).

```bash
# 1. Crea un cobro de $100 en la base y muestra el link de Handy
python -m v2.scripts.probar_pago_handy

# 2. Abrir el link y pagar con la tarjeta de prueba del manual de Handy
#    (Mastercard de testing; el número está en el manual, no acá)

# 3. Ver si el aviso llegó al backend público y qué hizo
python -m v2.scripts.probar_pago_handy --estado <referencia>
```

Lo que tiene que pasar: el cobro queda `pagado`, con `medio_pago` cargado y un
aviso `ACEPTADO` con `Status=1`. Si no llega nada en un minuto, lo primero que
se revisa es `BASE_URL` (tiene que ser la pública, con `https://`) y que el
secreto del webhook sea el mismo en los dos lados.

Cuando eso funciona, se le confirma a Handy (`integraciones@handy.uy`) y se
pide el secret de producción.
