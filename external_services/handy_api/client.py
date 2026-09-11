"""
Cliente HTTP del Boton de Pago de Handy. Manual de integracion v2.0.

Dos operaciones y nada mas, porque es todo lo que Handy expone:
  - crear un link de pago      POST   {base}/payments
  - devolver un pago           DELETE {base}/payments

No hay endpoint de consulta de estado. Lo confirmo Handy por escrito: todo llega
por callback, y si la entrega del callback falla no reintentan. Ver
docs/HANDY_RESPUESTAS.md. Por eso este cliente no tiene un `consultar_pago`: no
es una omision, es que no existe.

La autenticacion es un solo header, `merchant-secret-key`. El de testing esta
publicado en el manual y es compartido; el de produccion se pide a Handy una vez
validada la integracion en testing.

Sin SDK: Handy no publica uno para Python. Se usa `requests` directo, como el
cliente de n8n.
"""
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import UUID

import requests


# Monedas ISO 4217 numericas que acepta Handy
MONEDA_UYU = 858
MONEDA_USD = 840
MONEDAS_VALIDAS = (MONEDA_UYU, MONEDA_USD)


class HandyError(Exception):
    """Handy respondio con error, o no respondio."""

    def __init__(self, mensaje: str, status_code: Optional[int] = None,
                 cuerpo: Optional[str] = None):
        super().__init__(mensaje)
        self.status_code = status_code
        self.cuerpo = cuerpo


@dataclass
class LinkDePago:
    """Lo que devuelve crear_pago: la URL a la que se redirige al comprador."""
    url: str


class HandyClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        merchant_secret: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or os.getenv("HANDY_BASE_URL", "")).rstrip("/")
        self.merchant_secret = merchant_secret or os.getenv("HANDY_MERCHANT_SECRET", "")
        self.timeout = timeout or int(os.getenv("HANDY_TIMEOUT", "30"))

    @property
    def configurado(self) -> bool:
        return bool(self.base_url and self.merchant_secret)

    def _headers(self) -> dict:
        return {
            "merchant-secret-key": self.merchant_secret,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def crear_pago(
        self,
        referencia_externa: str,
        moneda: int,
        monto_total: Decimal,
        monto_gravado: Decimal,
        concepto: str,
        callback_url: str,
        site_url: str,
        commerce_name: str,
        numero_factura: Optional[int] = None,
        imagen_url: Optional[str] = None,
    ) -> LinkDePago:
        """
        Pide a Handy un link de pago de un solo uso.

        `referencia_externa` es NUESTRO identificador (el TransactionExternalId
        de Handy). Tiene que ser un UUID: es la clave de conciliacion y lo que
        Handy nos va a devolver en el callback para que sepamos de que pago habla.
        """
        if not self.configurado:
            raise HandyError("Handy no esta configurado: faltan HANDY_BASE_URL o HANDY_MERCHANT_SECRET")
        if moneda not in MONEDAS_VALIDAS:
            raise HandyError(f"Moneda {moneda} no valida. Handy acepta 858 (UYU) y 840 (USD)")
        if monto_total <= 0:
            raise HandyError("El monto total tiene que ser mayor a cero")
        # Handy exige UUID; si no lo es, mejor fallar aca que en el callback
        UUID(referencia_externa)

        cuerpo = {
            "Cart": {
                "Currency": moneda,
                "TotalAmount": float(monto_total),
                "TaxedAmount": float(monto_gravado),
                "InvoiceNumber": numero_factura,
                "TransactionExternalId": referencia_externa,
                "LinkImageUrl": imagen_url,
                "Products": [{
                    "Name": concepto[:100],
                    "Quantity": 1,
                    "Amount": float(monto_total),
                    "TaxedAmount": float(monto_gravado),
                }],
            },
            "Client": {
                "CommerceName": commerce_name,
                "SiteUrl": site_url,
            },
            "CallbackUrl": callback_url,
            "ResponseType": "Json",
        }
        # Handy no acepta null en estos: se omiten si no vienen
        if numero_factura is None:
            del cuerpo["Cart"]["InvoiceNumber"]
        if imagen_url is None:
            del cuerpo["Cart"]["LinkImageUrl"]

        respuesta = self._post("/payments", cuerpo)

        url = respuesta.get("url") if isinstance(respuesta, dict) else None
        if not url:
            raise HandyError(
                "Handy respondio sin la URL del link de pago", cuerpo=str(respuesta)
            )
        return LinkDePago(url=url)

    def devolver_pago(self, referencia_externa: str, callback_url: str) -> dict:
        """
        Inicia una devolucion. El resultado real llega despues por callback.

        Restricciones de Handy: una sola vez por venta, solo tarjeta, tope
        UYU 10.000 / USD 250. Si no se puede, responde 400 con el motivo.
        """
        if not self.configurado:
            raise HandyError("Handy no esta configurado")

        cuerpo = {
            "TransactionExternalId": referencia_externa,
            "CallbackUrl": callback_url,
        }
        return self._request("DELETE", "/payments", cuerpo)

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def _post(self, ruta: str, cuerpo: dict) -> dict:
        return self._request("POST", ruta, cuerpo)

    def _request(self, metodo: str, ruta: str, cuerpo: dict) -> dict:
        url = f"{self.base_url}{ruta}"
        try:
            r = requests.request(
                metodo, url, headers=self._headers(), json=cuerpo,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout:
            raise HandyError(f"Timeout al llamar a Handy (>{self.timeout}s)")
        except requests.exceptions.ConnectionError as e:
            raise HandyError(f"No se pudo conectar con Handy: {e}")

        if r.status_code >= 400:
            raise HandyError(
                f"Handy respondio {r.status_code} en {metodo} {ruta}",
                status_code=r.status_code, cuerpo=r.text[:500],
            )

        try:
            return r.json()
        except ValueError:
            raise HandyError(
                f"Handy respondio algo que no es JSON en {metodo} {ruta}",
                status_code=r.status_code, cuerpo=r.text[:500],
            )
