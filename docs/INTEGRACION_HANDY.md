# Integración con Handy — análisis previo

Estado: **análisis, sin código**. Falta pedir credenciales de producción y
decidir el modelo de datos. Escrito el 28/08/2026 sobre los manuales oficiales.

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
5. **Allowlist de IPs**, si Handy publica las suyas — hay que preguntar.

---

## Para preguntarle a Handy el lunes

**Seguridad (lo importante):**
- [ ] ¿El webhook se puede firmar? ¿HMAC, header con secreto, mTLS, algo?
- [ ] ¿Hay endpoint para **consultar el estado** de un pago por
      `TransactionExternalId`? Sin eso no podemos verificar nada.
- [ ] ¿Desde qué **IPs** salen los webhooks, para poder filtrar?
- [ ] ¿Reintentan si respondemos 500? ¿Cuántas veces, con qué espera?

**Operativo:**
- [ ] `merchant-secret-key` de **producción** (la de testing está publicada en el
      manual: `c80c2dca-ee4f-4cec-ace0-850747a5dcfa` — jamás reusarla)
- [ ] ¿El `InvoiceNumber` tiene que ser único? ¿Lo validan?
- [ ] ¿Rubro asignado a CTC? Define si quedan habilitados Amex y Passcard
      (Ley 19.210) o Edenred (Ley 17.934)
- [ ] ¿Cuándo se acredita la plata y con qué comisión por medio de pago?
- [ ] ¿Se puede personalizar la página de pago con la marca de CTC?

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

## Lo que falta decidir

### Persistencia — propuesta

Hoy **no hay ninguna tabla de pagos**: MercadoPago vive entero en
`external_services/` y no persiste nada. Para Handy eso no alcanza — sin registro
propio no hay forma de validar el webhook (mitigación 2) ni de conciliar.

Propuesta, a grandes rasgos:

- **Tabla de intentos de pago**, agnóstica del proveedor: identificador propio,
  `proveedor`, id del proveedor, monto, moneda, estado interno, estado crudo del
  proveedor, qué se compra, quién compra, marcas de tiempo.
- **Log crudo de webhooks recibidos**, aceptados y rechazados. Sin endpoint de
  consulta en Handy, ese log es la única pista para conciliar cuando algo no
  cierre.

MercadoPago **no se toca ahora**. El día que se quiera, entra en la misma tabla
sin cambiar el esquema — que es justamente el punto de hacerla agnóstica.

> **Es una propuesta, no está aplicado.** Según la regla vigente en
> [PENDIENTES_PRODUCCION.md](../PENDIENTES_PRODUCCION.md) no se toca el esquema
> sin pedirlo antes. Cuando esté definido el alcance lo escribo como migración y
> va a la lista de pendientes.

### Qué se vende

El flujo actual de MercadoPago no está atado a `v2`. Si el pago tiene que
habilitar una inscripción del Portal Académico, hay que definir ese vínculo.
Es lo único que queda abierto.
