"""
Cliente HTTP de Handy.

Lo que se fija aca es el contrato: la forma exacta del payload que espera el
Boton de Pago v2.0, el header de autenticacion y como se traducen los errores.
No se toca la red: requests.request se reemplaza.
"""
import pytest
from decimal import Decimal

from external_services.handy_api.client import HandyClient, HandyError, LinkDePago

REFERENCIA = "b4a8e7c3-5d41-4b8f-a23a-9c7d1f31e8f0"


class RespuestaFalsa:
    def __init__(self, status_code=200, json_body=None, text=""):
        self.status_code = status_code
        self._json = json_body
        self.text = text or (str(json_body) if json_body is not None else "")

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


@pytest.fixture(name="capturar")
def fixture_capturar(monkeypatch):
    """Reemplaza requests.request y guarda lo que se envio."""
    import external_services.handy_api.client as modulo
    enviado = {}

    def falso(metodo, url, headers=None, json=None, timeout=None):
        enviado.update(metodo=metodo, url=url, headers=headers, json=json, timeout=timeout)
        return enviado.get("_responder", RespuestaFalsa(200, {"url": "https://pago.arriba.uy?sessionId=M_x"}))

    monkeypatch.setattr(modulo.requests, "request", falso)
    return enviado


@pytest.fixture(name="cliente")
def fixture_cliente():
    return HandyClient(
        base_url="https://api.payments.arriba.uy/api/v2",
        merchant_secret="secreto-de-testing",
    )


def crear(cliente, **extra):
    datos = dict(
        referencia_externa=REFERENCIA, moneda=858,
        monto_total=Decimal("5000.00"), monto_gravado=Decimal("4098.36"),
        concepto="Curso de Analista Programador",
        callback_url="https://backend.test/v2/pagos/handy/webhook/s",
        site_url="https://ctcsalto.edu.uy", commerce_name="CTC Salto",
        numero_factura=42,
    )
    datos.update(extra)
    return cliente.crear_pago(**datos)


class TestContratoConHandy:
    def test_url_y_metodo(self, cliente, capturar):
        crear(cliente)
        assert capturar["metodo"] == "POST"
        assert capturar["url"] == "https://api.payments.arriba.uy/api/v2/payments"

    def test_el_header_de_autenticacion(self, cliente, capturar):
        crear(cliente)
        assert capturar["headers"]["merchant-secret-key"] == "secreto-de-testing"

    def test_no_manda_accept(self, cliente, capturar):
        """
        Probado contra testing el 11/09/2026: con Accept: application/json,
        Handy devuelve el JSON doblemente codificado. Sin el header, JSON limpio.
        """
        crear(cliente)
        assert "Accept" not in capturar["headers"]

    def test_la_forma_del_cart(self, cliente, capturar):
        """Los nombres de campo son los del manual, con su capitalizacion."""
        crear(cliente)
        cart = capturar["json"]["Cart"]

        assert cart["Currency"] == 858
        assert cart["TotalAmount"] == 5000.0
        assert cart["TaxedAmount"] == 4098.36
        assert cart["TransactionExternalId"] == REFERENCIA
        assert cart["InvoiceNumber"] == 42
        assert len(cart["Products"]) == 1
        assert cart["Products"][0] == {
            "Name": "Curso de Analista Programador", "Quantity": 1,
            "Amount": 5000.0, "TaxedAmount": 4098.36,
        }

    def test_client_y_callback(self, cliente, capturar):
        crear(cliente)
        cuerpo = capturar["json"]

        assert cuerpo["Client"] == {"CommerceName": "CTC Salto", "SiteUrl": "https://ctcsalto.edu.uy"}
        assert cuerpo["CallbackUrl"] == "https://backend.test/v2/pagos/handy/webhook/s"
        assert cuerpo["ResponseType"] == "Json"

    def test_los_opcionales_se_omiten_no_van_en_null(self, cliente, capturar):
        crear(cliente, numero_factura=None)
        cart = capturar["json"]["Cart"]

        assert "InvoiceNumber" not in cart
        assert "LinkImageUrl" not in cart

    def test_devuelve_el_link(self, cliente, capturar):
        link = crear(cliente)
        assert isinstance(link, LinkDePago)
        assert link.url == "https://pago.arriba.uy?sessionId=M_x"


class TestValidacionesLocales:
    """Lo que se rechaza antes de llamar a Handy."""

    def test_sin_configurar(self, capturar, monkeypatch):
        # Sin esto el test depende del .env de quien lo corre: el cliente cae
        # a las variables de entorno cuando no le pasan valores.
        monkeypatch.delenv("HANDY_BASE_URL", raising=False)
        monkeypatch.delenv("HANDY_MERCHANT_SECRET", raising=False)
        cliente = HandyClient(base_url="", merchant_secret="")
        with pytest.raises(HandyError, match="no esta configurado"):
            crear(cliente)
        assert "metodo" not in capturar  # no llego a la red

    def test_moneda_invalida(self, cliente, capturar):
        with pytest.raises(HandyError, match="Moneda"):
            crear(cliente, moneda=978)

    def test_monto_cero(self, cliente, capturar):
        with pytest.raises(HandyError, match="mayor a cero"):
            crear(cliente, monto_total=Decimal("0"))

    def test_referencia_que_no_es_uuid(self, cliente, capturar):
        """Handy exige UUID: mejor fallar aca que en el callback."""
        with pytest.raises(ValueError):
            crear(cliente, referencia_externa="pago-123")


class TestErroresDeHandy:
    def test_400_se_traduce_con_el_cuerpo(self, cliente, capturar):
        capturar["_responder"] = RespuestaFalsa(400, text='{"Message":"Bad request"}')
        with pytest.raises(HandyError) as e:
            crear(cliente)
        assert e.value.status_code == 400
        assert "Bad request" in e.value.cuerpo

    def test_respuesta_sin_url(self, cliente, capturar):
        capturar["_responder"] = RespuestaFalsa(200, {"message": True})
        with pytest.raises(HandyError, match="sin la URL"):
            crear(cliente)

    def test_json_doblemente_codificado_se_tolera(self, cliente, capturar):
        """
        Lo que Handy devuelve si se le manda Accept: un string JSON adentro de
        un JSON. Se parsea dos veces. Es el bug que aparecio en la primera
        llamada real.
        """
        import json as _json
        doble = _json.dumps(_json.dumps({"url": "https://pago.arriba.uy?sessionId=M_doble"}))
        capturar["_responder"] = RespuestaFalsa(200, _json.loads(doble), text=doble)

        link = crear(cliente)
        assert link.url == "https://pago.arriba.uy?sessionId=M_doble"

    def test_string_que_no_es_json(self, cliente, capturar):
        capturar["_responder"] = RespuestaFalsa(200, "esto no es json", text='"esto no es json"')
        with pytest.raises(HandyError, match="string que no es JSON"):
            crear(cliente)

    def test_respuesta_que_no_es_json(self, cliente, capturar):
        capturar["_responder"] = RespuestaFalsa(200, None, text="<html>error</html>")
        with pytest.raises(HandyError, match="no es JSON"):
            crear(cliente)

    def test_timeout(self, cliente, monkeypatch):
        import external_services.handy_api.client as modulo
        import requests

        def se_cuelga(*a, **k):
            raise requests.exceptions.Timeout()
        monkeypatch.setattr(modulo.requests, "request", se_cuelga)

        with pytest.raises(HandyError, match="Timeout"):
            crear(cliente)


class TestDevolucion:
    def test_delete_con_referencia_y_callback(self, cliente, capturar):
        capturar["_responder"] = RespuestaFalsa(200, {"IsSuccess": True, "StatusCode": 200})
        cliente.devolver_pago(REFERENCIA, "https://backend.test/cb")

        assert capturar["metodo"] == "DELETE"
        assert capturar["url"].endswith("/payments")
        assert capturar["json"] == {"TransactionExternalId": REFERENCIA, "CallbackUrl": "https://backend.test/cb"}
