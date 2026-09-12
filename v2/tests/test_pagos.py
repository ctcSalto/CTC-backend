"""
Registro de pagos.

Estas tablas no son un accesorio: son lo que sostiene las medidas de seguridad
que compensan lo que Handy no ofrece. Handy no firma las notificaciones, no
reintenta si la entrega falla y no tiene endpoint de consulta, asi que:

  - un aviso solo se acepta si contrasta contra una fila nuestra (referencia,
    estado, monto y moneda);
  - un aviso repetido no puede acreditar dos veces;
  - todo lo recibido queda registrado, aceptado o rechazado, porque es la unica
    evidencia que va a existir.

Los tests de aca fijan las propiedades del modelo que hacen eso posible.
Ver docs/HANDY_RESPUESTAS.md.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from v2.models.pago import Pago, PagoNotificacion
from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.enums import ProveedorPago, EstadoPago, EstadoInscripcionPrograma

UYU = 858
USD = 840


def ahora():
    return datetime.now(ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo")))


def nuevo_pago(session, programa=None, alumno=None, **kwargs):
    datos = dict(
        proveedor=ProveedorPago.HANDY,
        moneda=UYU,
        monto_total=Decimal("5000.00"),
        monto_gravado=Decimal("4098.36"),
        concepto="Curso de Analista Programador",
    )
    if programa is not None:
        datos["programa_id"] = programa.id
    if alumno is not None:
        datos["alumno_id"] = alumno.id
    datos.update(kwargs)

    pago = Pago(**datos)
    session.add(pago)
    session.commit()
    session.refresh(pago)
    return pago


class TestIdentificadorPropio:
    """
    La referencia la generamos nosotros y es la clave de conciliacion: es el
    TransactionExternalId de Handy y el external_reference de MercadoPago.
    """

    def test_se_genera_sola(self, session, programa):
        pago = nuevo_pago(session, programa)

        assert pago.referencia_externa
        assert len(pago.referencia_externa) == 36  # UUID con guiones

    def test_dos_pagos_no_comparten_referencia(self, session, programa):
        uno = nuevo_pago(session, programa)
        otro = nuevo_pago(session, programa)

        assert uno.referencia_externa != otro.referencia_externa

    def test_la_referencia_es_unica_en_la_base(self, session, programa):
        """
        Es la restriccion que sostiene la idempotencia: sin ella, un aviso
        repetido podria terminar acreditando dos veces.
        """
        uno = nuevo_pago(session, programa)

        with pytest.raises(IntegrityError):
            nuevo_pago(session, programa, referencia_externa=uno.referencia_externa)
        session.rollback()


class TestEstados:
    def test_arranca_iniciado(self, session, programa):
        assert nuevo_pago(session, programa).estado == EstadoPago.INICIADO

    def test_guarda_el_codigo_crudo_del_proveedor(self, session, programa):
        """
        El estado interno se normaliza, pero el codigo del proveedor se conserva
        sin interpretar: si manana hay que discutir con Handy, es lo que vale.
        """
        pago = nuevo_pago(session, programa, estado=EstadoPago.PAGADO,
                          estado_proveedor="1")

        assert pago.estado == EstadoPago.PAGADO
        assert pago.estado_proveedor == "1"

    def test_pendiente_admite_vencimiento(self, session, programa):
        """Redpagos genera una orden que el alumno paga despues en el local."""
        vence = ahora() + timedelta(days=3)
        pago = nuevo_pago(session, programa, estado=EstadoPago.PENDIENTE,
                          fecha_vencimiento=vence, medio_pago="Redpagos")

        assert pago.estado == EstadoPago.PENDIENTE
        assert pago.fecha_vencimiento is not None


class TestElPagoHabilitaLaInscripcion:
    """
    Decision tomada: el pago habilita la inscripcion. El vinculo se completa
    cuando el cobro se acredita, no antes.
    """

    def test_al_crearse_todavia_no_hay_inscripcion(self, session, programa, alumno):
        pago = nuevo_pago(session, programa, alumno)

        assert pago.inscripcion_programa_id is None

    def test_al_acreditarse_se_vincula(self, session, programa, alumno):
        pago = nuevo_pago(session, programa, alumno)

        inscripcion = InscripcionPrograma(
            alumno_id=alumno.id, programa_id=programa.id,
            anio_ingreso=2026, estado=EstadoInscripcionPrograma.ACTIVA,
        )
        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)

        pago.estado = EstadoPago.PAGADO
        pago.fecha_pago = ahora()
        pago.inscripcion_programa_id = inscripcion.id
        session.add(pago)
        session.commit()
        session.refresh(pago)

        assert pago.inscripcion_programa_id == inscripcion.id
        assert pago.estado == EstadoPago.PAGADO

    def test_se_puede_encontrar_el_pago_de_una_inscripcion(
        self, session, programa, alumno
    ):
        """Ante un reclamo, hay que poder ir de la inscripcion al cobro."""
        inscripcion = InscripcionPrograma(
            alumno_id=alumno.id, programa_id=programa.id, anio_ingreso=2026,
        )
        session.add(inscripcion)
        session.commit()
        session.refresh(inscripcion)

        nuevo_pago(session, programa, alumno, estado=EstadoPago.PAGADO,
                   inscripcion_programa_id=inscripcion.id)

        encontrado = session.exec(
            select(Pago).where(Pago.inscripcion_programa_id == inscripcion.id)
        ).first()
        assert encontrado is not None


class TestCompraSinAlumno:
    """
    Al momento de pagar puede no existir todavia el alumno: la venta puede
    llegar desde el CRM, de alguien que recien consulta por Instagram.
    """

    def test_se_puede_cobrar_sin_alumno(self, session, programa):
        pago = nuevo_pago(session, programa,
                          email_comprador="interesado@gmail.com")

        assert pago.alumno_id is None
        assert pago.email_comprador == "interesado@gmail.com"

    def test_se_puede_cobrar_algo_que_no_es_un_programa(self, session):
        pago = nuevo_pago(session, concepto="Certificacion Certiport")

        assert pago.programa_id is None
        assert pago.concepto == "Certificacion Certiport"


class TestVariosProveedores:
    def test_conviven_handy_y_mercadopago(self, session, programa):
        handy = nuevo_pago(session, programa, proveedor=ProveedorPago.HANDY)
        mp = nuevo_pago(session, programa, proveedor=ProveedorPago.MERCADOPAGO)

        assert handy.proveedor == ProveedorPago.HANDY
        assert mp.proveedor == ProveedorPago.MERCADOPAGO

    def test_se_puede_filtrar_por_proveedor(self, session, programa):
        nuevo_pago(session, programa, proveedor=ProveedorPago.HANDY)
        nuevo_pago(session, programa, proveedor=ProveedorPago.HANDY)
        nuevo_pago(session, programa, proveedor=ProveedorPago.MERCADOPAGO)

        de_handy = session.exec(
            select(Pago).where(Pago.proveedor == ProveedorPago.HANDY)
        ).all()
        assert len(de_handy) == 2

    def test_moneda_en_dolares(self, session, programa):
        pago = nuevo_pago(session, programa, moneda=USD,
                          monto_total=Decimal("120.00"))
        assert pago.moneda == USD


class TestLogDeNotificaciones:
    """
    Sin reintentos ni consulta de estado del lado de Handy, este log es la unica
    evidencia que va a existir ante un reclamo o una diferencia.
    """

    def test_guarda_el_cuerpo_crudo(self, session, programa):
        pago = nuevo_pago(session, programa)
        cuerpo = {
            "TransactionExternalId": pago.referencia_externa,
            "PurchaseData": {"Status": 1, "TotalAmount": 5000, "Currency": 858},
            "InstrumentData": {"IssuerName": "MasterCard"},
        }

        notif = PagoNotificacion(
            pago_id=pago.id, referencia_externa=pago.referencia_externa,
            proveedor=ProveedorPago.HANDY, cuerpo=cuerpo, aceptada=True,
        )
        session.add(notif)
        session.commit()
        session.refresh(notif)

        assert notif.cuerpo["PurchaseData"]["Status"] == 1

    def test_una_notificacion_rechazada_se_guarda_igual(self, session):
        """
        El caso que mas importa: un aviso que no corresponde a ningun pago
        nuestro. Es la señal de que alguien esta probando, y hay que conservarlo.
        """
        notif = PagoNotificacion(
            pago_id=None,
            referencia_externa="00000000-0000-0000-0000-000000000000",
            proveedor=ProveedorPago.HANDY,
            cuerpo={"PurchaseData": {"Status": 1}},
            aceptada=False,
            motivo_rechazo="La referencia no existe en nuestro registro",
            ip_origen="203.0.113.45",
        )
        session.add(notif)
        session.commit()
        session.refresh(notif)

        assert notif.id is not None
        assert notif.pago_id is None
        assert notif.aceptada is False

    def test_un_pago_puede_tener_varias_notificaciones(self, session, programa):
        """Redpagos manda al menos dos: el pendiente y despues el acreditado."""
        pago = nuevo_pago(session, programa)

        for estado in (3, 1):
            session.add(PagoNotificacion(
                pago_id=pago.id, referencia_externa=pago.referencia_externa,
                proveedor=ProveedorPago.HANDY,
                cuerpo={"PurchaseData": {"Status": estado}}, aceptada=True,
            ))
        session.commit()
        session.refresh(pago)

        assert len(pago.notificaciones) == 2

    def test_se_pueden_contar_los_rechazos(self, session):
        """Un patron de rechazos es lo que dispara la alerta al equipo."""
        for _ in range(3):
            session.add(PagoNotificacion(
                proveedor=ProveedorPago.HANDY, aceptada=False,
                motivo_rechazo="Referencia inexistente",
            ))
        session.add(PagoNotificacion(proveedor=ProveedorPago.HANDY, aceptada=True))
        session.commit()

        rechazadas = session.exec(
            select(PagoNotificacion).where(PagoNotificacion.aceptada == False)
        ).all()
        assert len(rechazadas) == 3


class TestInformeDePendientes:
    """
    Sin reintentos ni consulta de estado, cotejar a mano contra el panel de Handy
    es el unico mecanismo de recuperacion. Este listado es su insumo.
    """

    def test_encuentra_los_que_quedaron_sin_resolver(self, session, programa):
        viejo = nuevo_pago(session, programa)
        viejo.fecha_creacion = ahora() - timedelta(hours=6)
        session.add(viejo)

        nuevo_pago(session, programa)  # reciente, todavia no preocupa
        nuevo_pago(session, programa, estado=EstadoPago.PAGADO)  # resuelto
        session.commit()

        corte = ahora() - timedelta(hours=2)
        pendientes = session.exec(
            select(Pago).where(
                Pago.estado.in_([EstadoPago.INICIADO, EstadoPago.PENDIENTE]),
                Pago.fecha_creacion < corte,
            )
        ).all()

        assert len(pendientes) == 1
        assert pendientes[0].id == viejo.id
