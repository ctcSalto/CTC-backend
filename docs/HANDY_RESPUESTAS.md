# Handy — respuestas recibidas

**Recibidas el 10/09/2026** de Support (`integraciones@handy.uy`), en respuesta a
las consultas de [HANDY_CONSULTAS.md](HANDY_CONSULTAS.md).

**Contacto comercial:** Lucía Regueiro — `lucia.regueiro@handy.uy`

---

## Resumen

| # | Consulta | Respuesta |
|---|---|---|
| 1 | Validación del origen del webhook | *"Deben usar el TransactionExternalId"* |
| 2 | Endpoint de consulta de estado | **No existe.** Todo por callbacks |
| 3 | Rango de IPs de origen | **No publican** rango fijo |
| 4 | Reintentos ante fallo de entrega | **No hay reintento automático** |
| 5 | Secret de producción | Se solicita tras confirmar que testing funciona |
| 6 | Unicidad de `InvoiceNumber` | No la controlan. *"Quizás Plexo lo restringe"* |
| 7 | Rubro asignado | **Escuela y servicios educativos** |

Se confirmó el escenario que habíamos anticipado como el peor: **no hay firma, no
hay consulta de estado y no hay IPs**. Y apareció algo que no estaba en el
análisis previo: **tampoco hay reintentos**.

---

## 1 y 2 — No hay forma de verificar un pago contra Handy

La respuesta a la validación del webhook es *"usen el TransactionExternalId"*.
Eso **no es autenticación**: es el GUID que nosotros mismos generamos y le
mandamos a Handy al crear el cobro, funcionando como secreto compartido.

Sirve para algo —un atacante necesita adivinar un UUID v4 válido y vigente, que
no es realista por fuerza bruta— pero tiene una diferencia importante con una
firma: **si el identificador se filtra, no hay forma de detectarlo ni de
revocarlo**. Viaja en la URL de pago que ve el comprador, queda en logs
intermedios y en el historial del navegador.

Combinado con la respuesta 2 —no hay endpoint de consulta— significa que
**no podemos preguntarle a Handy si una transacción está realmente paga**. La
notificación es la única fuente de verdad y no es verificable.

**Cómo se compensa:**

1. Aceptar el webhook **solo si** el `TransactionExternalId` existe en nuestra
   base, está pendiente, y el monto y la moneda coinciden con lo que originamos.
2. **Idempotencia estricta:** un mismo identificador no acredita dos veces.
3. Registrar **todos** los webhooks recibidos en crudo, aceptados y rechazados.
4. Alertar ante rechazos repetidos: es la señal de que alguien está probando.

Es aceptable para el volumen y el tipo de operación de CTC, pero conviene que
quede asentado que es una mitigación, no una solución.

---

## 4 — El hallazgo importante: un webhook perdido no se recupera

> *"No, actualmente no hay reintento automático de nuestro lado si la entrega
> falla."*

Esto es más grave en la práctica que el tema de la firma, y no estaba en el
análisis previo porque asumí que reintentaban.

**Si nuestro servidor no responde en el momento exacto en que Handy envía la
notificación, esa notificación se pierde para siempre.** No hay reintento, y por
la respuesta 2 tampoco hay forma de consultar después qué pasó.

Escenario concreto: el alumno paga durante un despliegue. El servidor está
reiniciando 20 segundos. Handy manda el aviso, no hay nadie escuchando, y el pago
queda cobrado en Handy pero invisible para nosotros. El alumno reclama y no
tenemos registro.

**Consecuencias de diseño, no negociables:**

- El endpoint de webhook **tiene que responder 200 lo antes posible**. Recibir,
  persistir en crudo, devolver 200, procesar después. Nunca procesar antes de
  responder: si el procesamiento falla, ya perdimos el aviso.
- **El webhook nunca debe devolver 500.** Ni ante un error nuestro. Si algo falla
  al guardar, hay que responder 200 igual y dejarlo en una cola de revisión: un
  error nuestro no puede costar un pago.
- Los despliegues deben hacerse con **reinicio sin caída** (el proceso viejo
  sigue atendiendo hasta que el nuevo está listo), o programarse fuera de los
  horarios de cobro.
- Hace falta un **informe de pagos pendientes** para bedelía: intentos que quedaron
  sin resolución pasado cierto tiempo, para cotejar a mano contra el panel de
  Handy. Es el único mecanismo de recuperación posible.

Esto refuerza la necesidad del registro propio de operaciones: sin él, un webhook
perdido no deja **ningún** rastro.

---

## 6 — `InvoiceNumber` sin control de unicidad

No lo validan, y sugieren probar si Plexo lo restringe.

Lo generamos nosotros de forma única y lo probamos en testing. Si Plexo lo
rechaza por duplicado, nos enteramos ahí.

---

## 7 — Rubro: escuela y servicios educativos

Es un rubro **no alimentación**, así que según el manual:

| Medio | ¿Disponible? |
|---|---|
| Amex | **Sí** — aplica Ley 19.210 (rubro no alimentación) |
| Passcard | **Sí** — misma condición |
| Edenred | **No** — es solo para rubro alimentación (Ley 17.934) |

El resto (Visa, Mastercard, OCA, Cabal, Anda, Club del Este, Redpagos y
transferencias) está disponible sin condición.

> Conviene **confirmarlo en testing**, porque la habilitación efectiva depende de
> cómo quede configurada la cuenta y no solo del rubro nominal.

---

## 5 — Camino a producción

El secret de producción se solicita **después** de confirmar que la integración
funciona en testing, por el mismo canal (`integraciones@handy.uy`).

O sea que el orden es: integrar contra testing → confirmarles → recibir el secret
→ salir a producción. No se puede pedir por adelantado.

---

## Qué cambia respecto del plan original

| Antes | Ahora |
|---|---|
| Diseño de validación pendiente de respuesta | **Definido:** mitigaciones, no firma |
| Se asumía reintento ante fallo | **No hay.** El webhook debe ser altamente disponible y no devolver 500 nunca |
| Conciliación con endpoint de consulta | **Manual**, contra el panel de Handy, con informe de pendientes |
| Rubro desconocido | Escuela y servicios educativos — Amex y Passcard sí, Edenred no |

**No quedan bloqueos externos para empezar.** El ambiente de testing está
disponible y documentado, y el alcance de la validación ya está definido.

---

## Hallazgo de la primera llamada real (11/09/2026)

Se probo `POST /payments` contra el ambiente de testing con el secret publico
del manual. **Handy acepto el payload y devolvio el link de pago**, asi que el
contrato del cliente esta validado.

Pero aparecio algo que el manual no dice:

| Header enviado | Content-Type de respuesta | `r.json()` devuelve |
|---|---|---|
| sin `Accept` | `text/plain` | un dict, JSON limpio |
| `Accept: application/json` | `application/json` | **un string** que a su vez es JSON |

Con `Accept: application/json` Handy responde el JSON **doblemente codificado**
(comportamiento tipico de .NET Web API con negociacion de contenido). El cliente
ya no manda ese header, y ademas tolera la doble codificacion por si vuelve a
aparecer. Los dos casos tienen test.

Es exactamente el tipo de cosa que solo se descubre contra la API real, y la
razon por la que el paso siguiente —el webhook de entrada— tambien hay que
probarlo de verdad y no solo con el doble.

---

## Prueba de punta a punta del webhook (16/09/2026)

Con el backend de develop publicado y las variables de Handy cargadas, se
crearon dos cobros de $100 contra testing y se pagaron desde el navegador con
las dos tarjetas del manual.

| | Cobro 1 (Mastercard) | Cobro 2 (Cabal) |
|---|---|---|
| Link generado | ✅ | ✅ |
| Aviso recibido en el webhook | ✅ a los 4 min | ✅ a 1 min 38 s |
| IP de origen | `34.192.193.146` | `34.192.193.146` |
| Cuerpo | igual al manual, campo por campo | igual |
| Monto y moneda contra nuestro registro | coinciden | coinciden |
| `PurchaseData.Status` | **2 (fallido)** | **2 (fallido)** |
| Emisor resuelto (`IssuerName`) | `ARGENTA SPAARBANK` | `BANCO CREDICOOP` |
| Estado final del cobro | `fallido` | `fallido` |

**Lo nuestro está validado:** Handy alcanza el webhook con el segmento
secreto, el cuerpo tiene la forma esperada, la validación de monto/moneda y
la máquina de estados funcionan contra un aviso real. La rama de aprobación
(`Status = 1`) es el mismo código y está cubierta por tests con este mismo
cuerpo.

**Lo que no se pudo probar:** un pago aprobado. El sandbox rechazó las dos
tarjetas que el propio manual publica como de prueba, con BINs que resuelve a
bancos belgas y argentinos. Es el *"el ambiente de pruebas de los medios de
pago no siempre funciona correctamente"* del manual. Se les consulta y se
pide el secret de producción (ver HANDY_CONSULTAS.md, segundo mail).

Dos datos que no estaban en ningún lado y ahora sí:

- **Handy llama desde `34.192.193.146`** (AWS, us-east-1) — al menos hoy, en
  testing. Dijeron que no publican IPs fijas, así que no sirve para filtrar,
  pero sí para reconocer un aviso legítimo en los logs.
- **Latencia del aviso:** entre 1,5 y 4 minutos después de que el comprador
  termina en la página de Handy. El frontend no puede esperar el resultado en
  la misma pantalla: tiene que mostrar "estamos confirmando el pago" y
  consultar `GET /v2/portal/estudiante/pagos` después.

---

## Respuesta al segundo mail (17/09/2026): tarjetas nuevas

Handy respondió el mismo día con tarjetas de prueba **actualizadas** (las del
manual v2.0 ya no sirven): Visa `4111 1111 1111 1111`, Visa
`4456 5300 0000 1096` y Mastercard `5123 4500 0000 0008`, con cualquier CVV y
vencimiento. Y un dato que no estaba en el manual: el sandbox de tarjetas es
el de **Mastercard Gateway (MPGS)**; de su documentación se pueden sacar más.
Están en `HANDY.md`.

---

## Intentos 3 y 4 con las tarjetas nuevas (18/09/2026): certificado vencido

Con las tarjetas que mandó Handy pasó lo mismo: `Status = 2`. La Visa
terminada en 1096 pasó la autenticación 3DS (OTP de sandbox `1234`, en
Cardinal Commerce) y fue rechazada igual; la 4111 también, incluso mandando
el cobro **sin `InvoiceNumber`** para descartar una colisión de factura en el
comercio de prueba compartido.

La página de resultado de Handy dio el motivo que el webhook no trae:

> **Security Data : Merchant certificate has expired.**

Es el certificado del comercio de pruebas (`Plexo UY 001` / *"Comercio
pruebas boton de pago v2"*) en Plexo. Ninguna transacción de ese comercio
puede aprobar hasta que Handy lo renueve. No hay nada que hacer de nuestro
lado; se les pidió que lo renueven o den otro secret de testing (tercer mail
en `HANDY_CONSULTAS.md`).

| Cobro | Tarjeta | InvoiceNumber | 3DS | Resultado |
|---|---|---|---|---|
| 1 | Mastercard del manual | 1 | — | rechazada |
| 2 | Cabal del manual | 2 | — | rechazada |
| 3 | Visa …1096 (nueva) | 3 | OTP ok | rechazada |
| 4 | Visa …1111 (nueva) | ninguno | — | rechazada |

Dos cosas más que se vieron y sirven para producción:

- El comprador ve **"Plexo UY 001"** como nombre del comercio en la pantalla
  de 3DS. En producción va a aparecer lo que Handy/Plexo tengan configurado
  para CTC; conviene confirmarlo y avisarlo en la pantalla de pago del portal.
- Con tarjetas reales el alumno va a pasar por 3DS (SMS del banco). Es parte
  de la latencia y otra razón para que el frontend no espere el resultado en
  la misma pantalla.

---

## Reintento del 22/09/2026: ahora falla antes, "vinculo vencido"

Handy pidio volver a probar. El resultado cambio, pero sigue sin poder
completarse un pago:

| | 18 y 21/09 | 22/09 |
|---|---|---|
| Formulario de tarjeta | aparecia | **no aparece** |
| 3DS | se superaba | no se llega |
| Mensaje | "Security Data : Merchant certificate has expired" | "El vinculo de compra se ha vencido" |
| Donde falla | al autorizar en Plexo | al **iniciar la sesion** (redirige a `/?plexoLoading=true`, HTTP 400 en consola) |

**No es un vencimiento por tiempo:** se abrio un link 20 segundos despues de
generarlo, con dos links distintos, y ya decia vencido. `POST /payments`
sigue respondiendo 200 con el link. Referencias: `d6ab8580-...`,
`cc3f8125-...`, `7f2d8cb3-...`.

### Pendiente de preguntar: cuanto dura un link

El mensaje de Handy dice textual *"los vinculos de compra se vencen despues
de un tiempo"*. **No esta en el manual cuanto.** Importa: `VENTANA_REUSO` en
`pago_service.py` reutiliza un intento abierto de hasta 30 minutos, y si el
TTL de Handy es menor le estariamos devolviendo al alumno un link ya muerto.
Cuando el sandbox funcione, preguntar el TTL y ajustar esa ventana a algo
menor.
