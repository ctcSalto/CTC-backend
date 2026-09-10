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
