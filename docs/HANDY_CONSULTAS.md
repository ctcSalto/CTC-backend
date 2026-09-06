# Handy — consultas

> **Estado al 06/09/2026:** el mail se envio. Nos derivaron al area de
> integraciones y **todavia no hay respuesta**. Las preguntas 1 y 2 siguen
> abiertas y son las que condicionan el diseño de seguridad.

**Contacto:** `integraciones@handy.uy`
(figura en el pie de las 18 páginas del manual del Botón de Pago y es el que la
página de guías indica para integraciones y configuración)

Abajo está el mail listo para copiar y pegar. Antes, el contexto de por qué se
pregunta cada cosa, para poder sostener la conversación si responden por teléfono
o repreguntan.

---

## Lo que bloquea el diseño

Estas dos definen si la integración puede ser segura. Todo lo demás se puede
resolver de nuestro lado.

### 1. ¿Cómo validamos que el webhook viene de Handy?

El manual v2.0 no menciona firma, HMAC, token ni validación de origen. Tal como
está documentado, **cualquiera que descubra la URL de callback puede enviar un
`Status: 1`** y hacernos acreditar un curso que nadie pagó.

Puede ser que exista y no esté en el manual. Si no existe, necesitamos saberlo
para compensarlo con las mitigaciones de nuestro lado.

### 2. ¿Hay forma de consultar el estado de un pago?

El manual documenta `POST /payments` (crear) y `DELETE /payments` (devolver).
**No hay endpoint de consulta.**

Esto agrava lo anterior: sin poder preguntarle a Handy *"¿esta transacción está
realmente paga?"*, no tenemos contra qué verificar la notificación. Con un
endpoint de consulta, el webhook pasa a ser un simple disparador y la fuente de
verdad es la consulta — que es como se hace normalmente.

Si no existe ninguna de las dos cosas, la integración se puede hacer igual, pero
hay que asumir el riesgo por escrito y compensarlo con URL secreta, validación
contra nuestra propia base y log de todo lo recibido.

---

## Lo demás

| Pregunta | Por qué importa |
|---|---|
| IPs de origen de los webhooks | **Solo si no hay firma ni consulta.** Ver abajo |
| ¿Reintentan ante error nuestro? ¿Cuántas veces? | Define si podemos responder 500 ante un fallo transitorio o tenemos que aceptar siempre y procesar después |
| `merchant-secret-key` de producción | Sin esto no se puede salir a producción |
| ¿`InvoiceNumber` tiene que ser único? | Define si lo generamos nosotros o lo puede repetir |
| Rubro asignado a CTC | Determina si quedan habilitados Amex y Passcard (Ley 19.210) o Edenred (Ley 17.934) |

### Por qué igual conviene pedir las IPs

Puede que no las den, y es una pregunta que se hace igual. El motivo es que
**si no hay firma ni endpoint de consulta, la lista de IPs es lo único que
autentica de verdad.**

Las otras mitigaciones —URL con segmento secreto, exigir que el
`TransactionExternalId` exista en nuestra base— son *seguridad por oscuridad*:
suben el costo del ataque, pero cualquiera que consiga la URL y un identificador
válido entra igual. Filtrar por IP en el proxy sí bloquea.

Queda planteada como condicional: si contestan que sí a la 1 o a la 2, la 3 deja
de importar y no insistimos.

**No se pregunta** por comisiones ni plazos de acreditación: eso se negoció
directo con dirección. Tampoco por personalizar la página de pago — es una página
hospedada por ellos, como la de MercadoPago, y queda como está.

**Nota sobre el ambiente de pruebas:** el `merchant-secret-key` de testing viene
publicado en el propio manual (`c80c2dca-ee4f-4cec-ace0-850747a5dcfa`), o sea que
es compartido y público. Sirve para probar, nunca para otra cosa.

---

## Mail listo para enviar

> Revisar antes de mandarlo: completar lo que está entre corchetes y confirmar
> que el remitente sea el que corresponde.

**Para:** integraciones@handy.uy
**Asunto:** Integración Botón de Pago — CTC Salto — consultas técnicas y credenciales

```
Buenos días,

Escribo desde el Centro de Tecnologías de la Comunicación (CTC) de Salto
[RUT / número de comercio, si ya lo tienen asignado]. Estamos por integrar
la pasarela de Handy para la venta de cursos en nuestro sitio.

Revisamos los dos manuales publicados y optamos por el Botón de Pago
(Manual de integración v2.0), ya que nuestro backend está hecho en Python
y el Checkout API requiere firmado y canonicalización de mensajes sobre un
servicio WCF, algo que no aplica a nuestro caso. La integración la vamos a
hacer contra la API REST, desde el servidor.

Antes de avanzar nos quedaron algunas consultas técnicas.

SOBRE LAS NOTIFICACIONES (webhook)

1. ¿Qué mecanismo ofrecen para validar que una notificación proviene
   efectivamente de Handy? Consultamos por firma HMAC, un header con
   secreto compartido, mTLS o cualquier otro esquema. En el manual v2.0
   no encontramos referencia a esto y necesitamos poder verificar el
   origen antes de dar por acreditado un pago.

2. ¿Existe algún endpoint para consultar el estado de una transacción a
   partir del TransactionExternalId? En el manual figuran la creación
   (POST /payments) y la devolución (DELETE /payments), pero no una
   consulta. Nos sería muy útil para confirmar el estado contra Handy en
   lugar de depender únicamente de la notificación recibida.

3. En caso de que no exista ninguna de las dos opciones anteriores:
   ¿desde qué direcciones IP se emiten los webhooks? Nos permitiría
   restringirlas a nivel de infraestructura como alternativa.

4. Si nuestro endpoint responde con un error (por ejemplo un 500 por una
   caída momentánea), ¿reintentan el envío? ¿Cuántas veces y con qué
   intervalo?

SOBRE LA PUESTA EN PRODUCCIÓN

5. ¿Cómo solicitamos el merchant-secret-key de producción y qué
   documentación necesitan de nuestra parte?

6. ¿El campo InvoiceNumber debe ser único por transacción? ¿Lo validan
   del lado de ustedes?

7. ¿Qué rubro tenemos asignado? Lo consultamos porque de eso depende si
   quedan habilitados Amex y Passcard (Ley 19.210) o Edenred
   (Ley 17.934).

Quedamos atentos. Cualquier consulta, respondemos por este medio.

Saludos cordiales,

[Nombre]
[Cargo]
Centro de Tecnologías de la Comunicación — Salto
[Teléfono]
[Email]
```

---

## Cuando respondan

Según qué contesten a las dos primeras, cambia el diseño:

- **Si hay firma de webhook** → se valida la firma y el webhook pasa a ser
  confiable. Es el mejor escenario.
- **Si hay endpoint de consulta pero no firma** → el webhook queda como simple
  disparador y la fuente de verdad es la consulta. También es un buen escenario.
- **Si no hay ninguna de las dos** → se implementan las mitigaciones descriptas
  en [INTEGRACION_HANDY.md](INTEGRACION_HANDY.md), y conviene dejar registrado
  que el riesgo residual es una decisión tomada a conciencia.

En los tres casos hace falta la tabla de intentos de pago: es lo que permite
contrastar el `TransactionExternalId`, el monto y la moneda contra lo que
nosotros originamos.
