# Handy — credenciales y datos de prueba

Chuleta para probar la integración. Todo lo que está acá es **público**: sale
del manual de integración del Botón de Pago v2.0 que Handy entrega a cualquier
comercio. Lo que **no** es público no está acá y no va al repo (ver al final).

Cómo funciona la integración: [INTEGRACION_HANDY.md](INTEGRACION_HANDY.md).
Lo que Handy respondió a nuestras consultas: [HANDY_RESPUESTAS.md](HANDY_RESPUESTAS.md).

---

## Ambiente de testing

| | |
|---|---|
| API | `https://api.payments.arriba.uy/api/v2` |
| `merchant-secret-key` | `c80c2dca-ee4f-4cec-ace0-850747a5dcfa` (compartido, del manual) |
| Página de pago | `https://pago.arriba.uy?sessionId=…` (la devuelve `POST /payments`) |

Variables para el backend:

```
HANDY_BASE_URL=https://api.payments.arriba.uy/api/v2
HANDY_MERCHANT_SECRET=c80c2dca-ee4f-4cec-ace0-850747a5dcfa
```

## Tarjetas de prueba

| Sello | Número | Vencimiento | CVV |
|---|---|---|---|
| Mastercard | `5203 9481 0002 3450` | 12/26 | 045 |
| Cabal | `5896 5720 9999 9991` | 03/80 | 450 |

Nombre del titular y documento: cualquiera. El propio manual avisa que *"el
ambiente de pruebas de los medios de pago no siempre funciona correctamente"*:
si una tarjeta falla, probar con la otra antes de buscar el error de nuestro
lado.

Redpagos y transferencias no tienen datos de prueba: en testing se prueban
solo tarjetas.

## Probar de punta a punta

```bash
python -m v2.scripts.probar_pago_handy                        # crea un cobro de $100 y da el link
python -m v2.scripts.probar_pago_handy --estado <referencia>  # ¿llegó el aviso? ¿qué hizo?
```

Necesita en el `.env` local las variables de arriba más `BASE_URL` (la URL
**pública** del backend que va a recibir el webhook), `HANDY_WEBHOOK_SECRETO`
(el mismo que tiene ese backend) y `DATABASE_URL` apuntando a la misma base.
Detalle en [INTEGRACION_HANDY.md](INTEGRACION_HANDY.md#cómo-probar-de-punta-a-punta-testing).

## Producción

| | |
|---|---|
| API | `https://api.payments.handy.uy/api/v2` |
| `merchant-secret-key` | **se pide a Handy** después de validar testing |
| Contacto técnico | `integraciones@handy.uy` |
| Contacto comercial | Lucía Regueiro — `lucia.regueiro@handy.uy` |

---

## Lo que NO va en este archivo ni en el repo

- **`HANDY_MERCHANT_SECRET` de producción.** Es la llave para cobrar en
  nombre de CTC. Solo en las variables de entorno del servidor.
- **`HANDY_WEBHOOK_SECRETO`.** Es nuestro, no de Handy: la parte secreta de la
  URL a la que Handy manda los avisos. Se genera con `openssl rand -hex 32`, va
  en las variables de entorno del servidor y en el `.env` local de quien corre
  la prueba, y en ningún otro lado. Si se filtra, se genera otro (los cobros ya
  iniciados con el anterior dejan de recibir aviso: cambiarlo sin pagos en
  curso).
- El `.env` está en `.gitignore`. Que siga así.
