"""
Servicio de cobros con Handy.

Lo que estos tests fijan es lo que compensa lo que Handy no ofrece
(docs/HANDY_RESPUESTAS.md):

  - sin firma  -> un aviso solo se acepta si contrasta contra nuestra fila
  - sin reintentos -> procesar_notificacion nunca lanza, persiste antes de procesar
  - sin consulta de estado -> el informe de pendientes es la unica recuperacion

Y la decision de negocio: el pago habilita la inscripcion.

Handy se reemplaza por un doble: no se llama a la red.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from sqlmodel import select

from v2.models.pago import Pago, PagoNotificacion, PagoCreate, PagoConciliacion
from v2.models.usuario import UsuarioRead
from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.enums import ProveedorPago, EstadoPago, EstadoInscripcionPrograma
from v2.services.pago_service import PagoService, VENTANA_REUSO
from external_services.handy_api.client import HandyError, LinkDePago

UYU = 858


def ahora():
    return datetime.now(ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo")))


class HandyFalso:
    """Doble del cliente. Registra lo que se le pidio y devuelve un link."""

    def __init__(self, fallar: bool = False):
        self.fallar = fallar
        self.llamadas = []
        self.configurado = True

    def crear_pago(self, **kwargs):
        self.llamadas.append(kwargs)
        if self.fallar:
            raise HandyError("Handy respondio 500", status_code=500)
        return LinkDePago(url=f"https://pago.arriba.uy?sessionId=M_{kwargs['referencia_externa'][:8]}")

    def devolver_pago(self, referencia_externa, callback_url):
        self.devoluciones = getattr(self, "devoluciones", [])
        self.devoluciones.append((referencia_externa, callback_url))
        if self.fallar:
            raise HandyError("Handy respondio 400: no se puede devolver", status_code=400)
        return {"IsSuccess": True, "StatusCode": 200}


@pytest.fixture(autouse=True)
def entorno_handy(monkeypatch):
    monkeypatch.setenv("BASE_URL", "https://backend.test")
    monkeypatch.setenv("HANDY_WEBHOOK_SECRETO", "s3cr3t0-de-prueba")


@pytest.fixture(name="handy")
def fixture_handy():
    return HandyFalso()


@pytest.fixture(name="servicio")
def fixture_servicio(handy):
    return PagoService(cliente_handy=handy)


def pedido(programa, alumno=None, **kwargs):
    datos = dict(
        proveedor=ProveedorPago.HANDY, moneda=UYU,
        monto_total=Decimal("5000.00"), monto_gravado=Decimal("4098.36"),
        concepto="Curso", programa_id=programa.id,
    )
    if alumno is not None:
        datos["alumno_id"] = alumno.id
    datos.update(kwargs)
    return PagoCreate(**datos)


def aviso(pago, status=1, total=None, moneda=None, issuer="MasterCard", expiration=None):
    """Un webhook de Handy con la forma real del manual."""
    return {
        "TransactionExternalId": pago.referencia_externa,
        "PurchaseData": {
            "Status": status,
            "Created": "2026-09-10T12:00:00Z",
            "TotalAmount": float(total if total is not None else pago.monto_total),
            "TaxedAmount": float(pago.monto_gravado),
            "Currency": moneda if moneda is not None else pago.moneda,
            "Products": [],
        },
        "InstrumentData": {
            "Name": "520394XXXXXX3450", "IssuerName": issuer,
            "IssuerImageUrl": "", "Expiration": expiration, "NotACard": False,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# Iniciar un cobro
# ══════════════════════════════════════════════════════════════════════════════

class TestIniciarPago:
    def test_crea_el_registro_y_pide_el_link(self, session, servicio, handy, programa, alumno):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)

        assert pago.id is not None
        assert pago.estado == EstadoPago.INICIADO
        assert pago.url_pago.startswith("https://pago.arriba.uy")
        assert len(handy.llamadas) == 1

    def test_le_manda_a_handy_nuestra_referencia(self, session, servicio, handy, programa, alumno):
        """La referencia es la clave de conciliacion: tiene que ser la nuestra."""
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)

        assert handy.llamadas[0]["referencia_externa"] == pago.referencia_externa

    def test_el_callback_lleva_el_secreto(self, session, servicio, handy, programa, alumno):
        servicio.iniciar_pago(pedido(programa, alumno), session)

        assert handy.llamadas[0]["callback_url"] == (
            "https://backend.test/v2/pagos/handy/webhook/s3cr3t0-de-prueba"
        )

    def test_el_numero_de_factura_es_el_id(self, session, servicio, handy, programa, alumno):
        """Handy no controla unicidad del InvoiceNumber: la garantizamos nosotros."""
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)

        assert pago.numero_factura == pago.id
        assert handy.llamadas[0]["numero_factura"] == pago.id

    def test_si_handy_falla_queda_registrado_como_fallido(
        self, session, programa, alumno
    ):
        roto = HandyFalso(fallar=True)
        servicio = PagoService(cliente_handy=roto)

        with pytest.raises(ValueError, match="No se pudo generar"):
            servicio.iniciar_pago(pedido(programa, alumno), session)

        pago = session.exec(select(Pago)).first()
        assert pago.estado == EstadoPago.FALLIDO
        assert pago.estado_proveedor == "error_creacion"
        assert pago.url_pago is None

    def test_programa_inexistente(self, session, servicio, alumno):
        class P:
            id = 99999
        with pytest.raises(ValueError, match="no encontrado"):
            servicio.iniciar_pago(pedido(P, alumno), session)

    def test_solo_handy_por_ahora(self, session, servicio, programa, alumno):
        with pytest.raises(ValueError, match="no implementado"):
            servicio.iniciar_pago(
                pedido(programa, alumno, proveedor=ProveedorPago.MERCADOPAGO), session
            )


class TestVeinteClics:
    """Un solo cobro abierto por compra: no se generan veinte links."""

    def test_reutiliza_el_intento_abierto(self, session, servicio, handy, programa, alumno):
        primero = servicio.iniciar_pago(pedido(programa, alumno), session)
        segundo = servicio.iniciar_pago(pedido(programa, alumno), session)

        assert segundo.id == primero.id
        assert len(handy.llamadas) == 1

    def test_pero_no_si_ya_esta_pago(self, session, servicio, handy, programa, alumno):
        primero = servicio.iniciar_pago(pedido(programa, alumno), session)
        primero.estado = EstadoPago.PAGADO
        session.add(primero)
        session.commit()

        segundo = servicio.iniciar_pago(pedido(programa, alumno), session)

        assert segundo.id != primero.id

    def test_ni_si_el_intento_es_viejo(self, session, servicio, handy, programa, alumno):
        primero = servicio.iniciar_pago(pedido(programa, alumno), session)
        primero.fecha_creacion = ahora() - VENTANA_REUSO - timedelta(minutes=1)
        session.add(primero)
        session.commit()

        segundo = servicio.iniciar_pago(pedido(programa, alumno), session)

        assert segundo.id != primero.id

    def test_otro_programa_es_otro_cobro(self, session, servicio, handy, programa, alumno, politica_base100):
        from v2.models.programa import Programa
        from v2.models.enums import TipoPrograma
        otro = Programa(nombre="Otro", descripcion="x", tipo=TipoPrograma.CURSO_CORTO,
                        duracion_semestres=1, activo=True)
        session.add(otro)
        session.commit()
        session.refresh(otro)

        uno = servicio.iniciar_pago(pedido(programa, alumno), session)
        dos = servicio.iniciar_pago(pedido(otro, alumno), session)

        assert uno.id != dos.id

    def test_sin_alumno_se_deduplica_por_email(self, session, servicio, handy, programa):
        uno = servicio.iniciar_pago(
            pedido(programa, email_comprador="interesado@gmail.com"), session
        )
        dos = servicio.iniciar_pago(
            pedido(programa, email_comprador="interesado@gmail.com"), session
        )
        assert uno.id == dos.id


# ══════════════════════════════════════════════════════════════════════════════
# Webhook: la validacion que reemplaza a la firma
# ══════════════════════════════════════════════════════════════════════════════

class TestAvisoDePagoExitoso:
    def test_acredita_y_habilita_la_inscripcion(self, session, servicio, programa, alumno):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)

        resultado = servicio.procesar_notificacion(aviso(pago), session)

        assert resultado.aceptada, resultado.motivo
        session.refresh(pago)
        assert pago.estado == EstadoPago.PAGADO
        assert pago.fecha_pago is not None
        assert pago.medio_pago == "MasterCard"
        assert pago.inscripcion_programa_id is not None

        inscripcion = session.get(InscripcionPrograma, pago.inscripcion_programa_id)
        assert inscripcion.alumno_id == alumno.id
        assert inscripcion.programa_id == programa.id
        assert inscripcion.estado == EstadoInscripcionPrograma.ACTIVA

    def test_si_ya_habia_inscripcion_activa_se_vincula_sin_duplicar(
        self, session, servicio, programa, alumno
    ):
        """Pagar dos veces el mismo curso no inscribe dos veces."""
        existente = InscripcionPrograma(
            alumno_id=alumno.id, programa_id=programa.id, anio_ingreso=2026,
        )
        session.add(existente)
        session.commit()
        session.refresh(existente)

        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.procesar_notificacion(aviso(pago), session)
        session.refresh(pago)

        assert pago.inscripcion_programa_id == existente.id
        total = session.exec(select(InscripcionPrograma)).all()
        assert len(total) == 1

    def test_sin_alumno_queda_pagado_sin_inscripcion(self, session, servicio, programa):
        """Venta desde el CRM: el alumno todavia no existe. Lo resuelve bedelia."""
        pago = servicio.iniciar_pago(
            pedido(programa, email_comprador="nuevo@gmail.com"), session
        )

        resultado = servicio.procesar_notificacion(aviso(pago), session)
        session.refresh(pago)

        assert resultado.aceptada
        assert pago.estado == EstadoPago.PAGADO
        assert pago.inscripcion_programa_id is None
        assert "bedelia" in resultado.motivo
        assert pago in servicio.pagos_sin_inscripcion(session)

    def test_queda_registrado_el_aviso(self, session, servicio, programa, alumno):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        resultado = servicio.procesar_notificacion(aviso(pago), session, ip_origen="203.0.113.7")

        notif = resultado.notificacion
        assert notif.id is not None
        assert notif.pago_id == pago.id
        assert notif.aceptada is True
        assert notif.ip_origen == "203.0.113.7"
        assert notif.cuerpo["PurchaseData"]["Status"] == 1


class TestRedpagos:
    """Pendiente primero, pagado despues, con dias en el medio."""

    def test_pendiente_y_despues_pagado(self, session, servicio, programa, alumno):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)

        r1 = servicio.procesar_notificacion(
            aviso(pago, status=3, issuer="Redpagos", expiration="2026-09-15T12:00:00"),
            session,
        )
        session.refresh(pago)
        assert r1.aceptada
        assert pago.estado == EstadoPago.PENDIENTE
        assert pago.fecha_vencimiento is not None
        assert pago.inscripcion_programa_id is None  # todavia no pago

        r2 = servicio.procesar_notificacion(aviso(pago, status=1, issuer="Redpagos"), session)
        session.refresh(pago)
        assert r2.aceptada
        assert pago.estado == EstadoPago.PAGADO
        assert pago.inscripcion_programa_id is not None


class TestAvisosQueSeRechazan:
    def test_referencia_desconocida(self, session, servicio):
        """
        El caso que mas importa: alguien manda una referencia que no es nuestra.
        Se rechaza y queda registrado con pago_id nulo.
        """
        falso = {
            "TransactionExternalId": "00000000-0000-0000-0000-000000000000",
            "PurchaseData": {"Status": 1, "TotalAmount": 5000, "Currency": 858},
        }
        resultado = servicio.procesar_notificacion(falso, session, ip_origen="198.51.100.9")

        assert not resultado.aceptada
        assert "ningun pago nuestro" in resultado.motivo
        assert resultado.notificacion.pago_id is None
        assert resultado.notificacion.ip_origen == "198.51.100.9"

    def test_monto_distinto(self, session, servicio, programa, alumno):
        """El monto es lo unico que podemos contrastar sin firma."""
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)

        resultado = servicio.procesar_notificacion(aviso(pago, total=1.00), session)
        session.refresh(pago)

        assert not resultado.aceptada
        assert "Monto distinto" in resultado.motivo
        assert pago.estado == EstadoPago.INICIADO

    def test_moneda_distinta(self, session, servicio, programa, alumno):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)

        resultado = servicio.procesar_notificacion(aviso(pago, moneda=840), session)

        assert not resultado.aceptada
        assert "Moneda distinta" in resultado.motivo

    def test_status_desconocido(self, session, servicio, programa, alumno):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        resultado = servicio.procesar_notificacion(aviso(pago, status=99), session)

        assert not resultado.aceptada
        assert "desconocido" in resultado.motivo

    def test_transicion_invalida(self, session, servicio, programa, alumno):
        """Un PAGADO no vuelve a INICIADO."""
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.procesar_notificacion(aviso(pago, status=1), session)

        resultado = servicio.procesar_notificacion(aviso(pago, status=0), session)
        session.refresh(pago)

        assert not resultado.aceptada
        assert "Transicion invalida" in resultado.motivo
        assert pago.estado == EstadoPago.PAGADO

    def test_un_fallido_no_resucita(self, session, servicio, programa, alumno):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.procesar_notificacion(aviso(pago, status=2), session)

        resultado = servicio.procesar_notificacion(aviso(pago, status=1), session)
        session.refresh(pago)

        assert not resultado.aceptada
        assert pago.estado == EstadoPago.FALLIDO
        assert pago.inscripcion_programa_id is None

    def test_los_rechazos_se_cuentan(self, session, servicio, programa, alumno):
        for _ in range(3):
            servicio.procesar_notificacion(
                {"TransactionExternalId": "no-existe", "PurchaseData": {"Status": 1}}, session
            )
        assert servicio.rechazos_recientes(session) == 3


class TestIdempotencia:
    """El mismo aviso dos veces no acredita dos veces, y tampoco es error."""

    def test_pagado_dos_veces_es_una_sola_inscripcion(self, session, servicio, programa, alumno):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)

        r1 = servicio.procesar_notificacion(aviso(pago), session)
        r2 = servicio.procesar_notificacion(aviso(pago), session)

        assert r1.aceptada and r2.aceptada
        assert "repetido" in r2.motivo
        assert len(session.exec(select(InscripcionPrograma)).all()) == 1

    def test_las_dos_quedan_registradas(self, session, servicio, programa, alumno):
        """Aunque la segunda no tenga efecto, tiene que quedar en el log."""
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.procesar_notificacion(aviso(pago), session)
        servicio.procesar_notificacion(aviso(pago), session)

        notifs = session.exec(
            select(PagoNotificacion).where(PagoNotificacion.pago_id == pago.id)
        ).all()
        assert len(notifs) == 2
        assert all(n.aceptada for n in notifs)


class TestDevolucion:
    def test_devolucion_exitosa(self, session, servicio, programa, alumno):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.procesar_notificacion(aviso(pago), session)

        devolucion = {
            "Success": True, "Message": "Devolucion procesada",
            "TransactionExternalId": pago.referencia_externa,
        }
        resultado = servicio.procesar_notificacion(devolucion, session)
        session.refresh(pago)

        assert resultado.aceptada
        assert pago.estado == EstadoPago.DEVUELTO

    def test_devolucion_fallida_no_cambia_el_estado(self, session, servicio, programa, alumno):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.procesar_notificacion(aviso(pago), session)

        devolucion = {
            "Success": False, "Message": "El sello no permite la devolucion",
            "TransactionExternalId": pago.referencia_externa,
        }
        resultado = servicio.procesar_notificacion(devolucion, session)
        session.refresh(pago)

        assert resultado.aceptada  # se registra, no es error nuestro
        assert pago.estado == EstadoPago.PAGADO

    def test_no_se_devuelve_lo_que_no_esta_pago(self, session, servicio, programa, alumno):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        devolucion = {"Success": True, "TransactionExternalId": pago.referencia_externa}

        resultado = servicio.procesar_notificacion(devolucion, session)

        assert not resultado.aceptada
        assert "Transicion invalida" in resultado.motivo


# ══════════════════════════════════════════════════════════════════════════════
# Conciliacion manual: lo que Handy no avisa lo cierra bedelia, con registro
# ══════════════════════════════════════════════════════════════════════════════

def como_admin(usuario_admin):
    return UsuarioRead.model_validate(usuario_admin)


def conciliacion(estado=EstadoPago.PAGADO, motivo="Verificado en el panel de Handy el 16/09", **extra):
    return PagoConciliacion(estado=estado, motivo=motivo, **extra)


class TestConciliacionManual:
    """
    El aviso se perdio (Handy no reintenta). Bedelia lo ve en pendientes, lo
    verifica en el panel de Handy y lo cierra a mano. Tiene que comportarse
    igual que si el aviso hubiera llegado, y dejar rastro de quien y por que.
    """

    def test_pagado_a_mano_habilita_la_inscripcion(self, session, servicio, programa, alumno, usuario_admin):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)

        pago = servicio.conciliar_manual(pago.id, conciliacion(), como_admin(usuario_admin), session)

        assert pago.estado == EstadoPago.PAGADO
        assert pago.estado_proveedor == "conciliacion_manual"
        assert pago.fecha_pago is not None
        inscripcion = session.get(InscripcionPrograma, pago.inscripcion_programa_id)
        assert inscripcion.alumno_id == alumno.id and inscripcion.programa_id == programa.id

    def test_queda_registrado_quien_y_por_que(self, session, servicio, programa, alumno, usuario_admin):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.conciliar_manual(
            pago.id, conciliacion(proveedor_id="HANDY-778899"), como_admin(usuario_admin), session,
        )

        registros = session.exec(
            select(PagoNotificacion).where(PagoNotificacion.pago_id == pago.id)
        ).all()
        assert len(registros) == 1
        r = registros[0]
        assert r.aceptada
        assert r.cuerpo["origen"] == "conciliacion_manual"
        assert r.cuerpo["usuario_email"] == usuario_admin.email
        assert r.cuerpo["estado_anterior"] == "iniciado" and r.cuerpo["estado"] == "pagado"
        assert "panel de Handy" in r.cuerpo["motivo"]
        session.refresh(pago)
        assert pago.proveedor_id == "HANDY-778899"

    def test_fallido_a_mano(self, session, servicio, programa, alumno, usuario_admin):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        pago = servicio.conciliar_manual(
            pago.id, conciliacion(EstadoPago.FALLIDO, "En el panel figura rechazada por el emisor"),
            como_admin(usuario_admin), session,
        )
        assert pago.estado == EstadoPago.FALLIDO
        assert pago.inscripcion_programa_id is None

    def test_respeta_la_maquina_de_estados(self, session, servicio, programa, alumno, usuario_admin):
        """Un FALLIDO no vuelve a PAGADO ni a mano: se crea otro cobro."""
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.procesar_notificacion(aviso(pago, status=2), session)

        with pytest.raises(ValueError, match="Transicion invalida"):
            servicio.conciliar_manual(pago.id, conciliacion(), como_admin(usuario_admin), session)

    def test_no_concilia_al_mismo_estado(self, session, servicio, programa, alumno, usuario_admin):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.procesar_notificacion(aviso(pago), session)

        with pytest.raises(ValueError, match="ya esta en pagado"):
            servicio.conciliar_manual(pago.id, conciliacion(), como_admin(usuario_admin), session)

    def test_solo_a_estados_que_se_ven_en_el_panel(self, session, servicio, programa, alumno, usuario_admin):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        with pytest.raises(ValueError, match="Solo se puede conciliar"):
            servicio.conciliar_manual(
                pago.id, conciliacion(EstadoPago.PENDIENTE), como_admin(usuario_admin), session,
            )

    def test_el_motivo_es_obligatorio(self):
        with pytest.raises(ValueError):
            PagoConciliacion(estado=EstadoPago.PAGADO, motivo="ok")

    def test_pago_inexistente(self, session, servicio, usuario_admin):
        with pytest.raises(ValueError, match="no encontrado"):
            servicio.conciliar_manual(9999, conciliacion(), como_admin(usuario_admin), session)

    def test_un_aviso_tardio_despues_de_conciliar_no_hace_nada(self, session, servicio, programa, alumno, usuario_admin):
        """Si el aviso al final llega, cae en 'mismo estado' y no duplica nada."""
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.conciliar_manual(pago.id, conciliacion(), como_admin(usuario_admin), session)

        resultado = servicio.procesar_notificacion(aviso(pago), session)
        session.refresh(pago)

        assert resultado.aceptada and "sin efecto" in resultado.motivo
        assert len(session.exec(select(InscripcionPrograma)).all()) == 1


# ══════════════════════════════════════════════════════════════════════════════
# Devolucion pedida desde admin
# ══════════════════════════════════════════════════════════════════════════════

class TestPedirDevolucion:
    def test_pide_a_handy_y_espera_el_webhook(self, session, servicio, handy, programa, alumno, usuario_admin):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.procesar_notificacion(aviso(pago), session)

        pago = servicio.devolver(pago.id, como_admin(usuario_admin), session)

        assert handy.devoluciones == [(pago.referencia_externa, servicio.callback_url())]
        assert pago.estado == EstadoPago.PAGADO            # todavia: Handy avisa despues
        assert pago.estado_proveedor == "devolucion_solicitada"

        registro = session.exec(
            select(PagoNotificacion).where(PagoNotificacion.pago_id == pago.id)
        ).all()[-1]
        assert registro.cuerpo["origen"] == "solicitud_devolucion"
        assert registro.cuerpo["usuario_email"] == usuario_admin.email

        # Llega el resultado por webhook
        servicio.procesar_notificacion(
            {"Success": True, "TransactionExternalId": pago.referencia_externa}, session,
        )
        session.refresh(pago)
        assert pago.estado == EstadoPago.DEVUELTO

    def test_solo_lo_que_esta_pagado(self, session, servicio, programa, alumno, usuario_admin):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        with pytest.raises(ValueError, match="Solo se devuelve un pago en PAGADO"):
            servicio.devolver(pago.id, como_admin(usuario_admin), session)

    def test_no_se_pide_dos_veces(self, session, servicio, handy, programa, alumno, usuario_admin):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.procesar_notificacion(aviso(pago), session)
        servicio.devolver(pago.id, como_admin(usuario_admin), session)

        with pytest.raises(ValueError, match="ya se pidio"):
            servicio.devolver(pago.id, como_admin(usuario_admin), session)
        assert len(handy.devoluciones) == 1

    def test_respeta_el_tope_de_handy(self, session, servicio, handy, programa, alumno, usuario_admin):
        pago = servicio.iniciar_pago(pedido(programa, alumno, monto_total=Decimal("12000.00")), session)
        servicio.procesar_notificacion(aviso(pago), session)

        with pytest.raises(ValueError, match="no devuelve mas de 10000"):
            servicio.devolver(pago.id, como_admin(usuario_admin), session)
        assert not getattr(handy, "devoluciones", [])

    def test_si_handy_la_rechaza_no_queda_como_pedida(self, session, servicio, handy, programa, alumno, usuario_admin):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        servicio.procesar_notificacion(aviso(pago), session)
        handy.fallar = True

        with pytest.raises(ValueError, match="Handy rechazo la devolucion"):
            servicio.devolver(pago.id, como_admin(usuario_admin), session)
        session.refresh(pago)
        assert pago.estado_proveedor != "devolucion_solicitada"


# ══════════════════════════════════════════════════════════════════════════════
# NUNCA lanza: Handy no reintenta
# ══════════════════════════════════════════════════════════════════════════════

class TestNuncaLanza:
    def test_cuerpo_que_no_es_dict(self, session, servicio):
        resultado = servicio.procesar_notificacion("basura", session)
        assert not resultado.aceptada
        assert resultado.notificacion.id is not None

    def test_cuerpo_vacio(self, session, servicio):
        resultado = servicio.procesar_notificacion({}, session)
        assert not resultado.aceptada
        assert "TransactionExternalId" in resultado.motivo

    def test_purchase_data_roto(self, session, servicio, programa, alumno):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        roto = {"TransactionExternalId": pago.referencia_externa, "PurchaseData": "no-es-dict"}

        resultado = servicio.procesar_notificacion(roto, session)

        assert not resultado.aceptada
        assert resultado.notificacion.id is not None

    def test_error_interno_queda_registrado_y_no_lanza(
        self, session, servicio, programa, alumno, monkeypatch
    ):
        """
        Si algo explota en el medio, el aviso ya esta guardado y el error
        queda como motivo. Un bug nuestro no puede costar el aviso.
        """
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)

        def explota(*a, **k):
            raise RuntimeError("se cayo la base en el peor momento")
        monkeypatch.setattr(servicio, "_transicionar", explota)

        resultado = servicio.procesar_notificacion(aviso(pago), session)

        assert not resultado.aceptada
        assert "Error interno" in resultado.motivo
        assert "se cayo la base" in resultado.motivo
        assert resultado.notificacion.id is not None
        assert resultado.notificacion.cuerpo["TransactionExternalId"] == pago.referencia_externa

    def test_el_aviso_se_guarda_antes_de_procesar(
        self, session, servicio, programa, alumno, monkeypatch
    ):
        pago = servicio.iniciar_pago(pedido(programa, alumno), session)
        antes = len(session.exec(select(PagoNotificacion)).all())

        monkeypatch.setattr(servicio, "_aplicar_notificacion",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
        servicio.procesar_notificacion(aviso(pago), session)

        despues = len(session.exec(select(PagoNotificacion)).all())
        assert despues == antes + 1


# ══════════════════════════════════════════════════════════════════════════════
# Informes y secreto
# ══════════════════════════════════════════════════════════════════════════════

class TestInformePendientes:
    def test_encuentra_los_viejos_sin_resolver(self, session, servicio, programa, alumno):
        viejo = servicio.iniciar_pago(pedido(programa, alumno), session)
        viejo.fecha_creacion = ahora() - timedelta(hours=5)
        session.add(viejo)
        session.commit()

        # uno reciente (no preocupa) y uno resuelto: ninguno debe aparecer
        reciente = servicio.iniciar_pago(pedido(programa, alumno, concepto="otro"), session)
        reciente.programa_id = None
        session.add(reciente)
        resuelto = Pago(proveedor=ProveedorPago.HANDY, moneda=UYU, monto_total=Decimal("1"),
                        concepto="x", estado=EstadoPago.PAGADO)
        resuelto.fecha_creacion = ahora() - timedelta(hours=9)
        session.add(resuelto)
        session.commit()

        pendientes = servicio.pendientes(session, horas=2)

        assert [p.id for p in pendientes] == [viejo.id]


class TestSecretoDelWebhook:
    def test_acepta_el_correcto(self, servicio):
        assert servicio.secreto_webhook_valido("s3cr3t0-de-prueba")

    def test_rechaza_otro(self, servicio):
        assert not servicio.secreto_webhook_valido("cualquier-cosa")

    def test_sin_configurar_rechaza_todo(self, servicio, monkeypatch):
        """Sin secreto configurado, ninguna ruta es valida: mejor cerrado que abierto."""
        monkeypatch.setenv("HANDY_WEBHOOK_SECRETO", "")
        assert not servicio.secreto_webhook_valido("")
        assert not servicio.secreto_webhook_valido("s3cr3t0-de-prueba")
