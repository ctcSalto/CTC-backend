"""
Prueba de punta a punta del cobro con Handy, contra el ambiente de TESTING.

Crea un cobro real en la base (la que apunte DATABASE_URL), le pide el link a
Handy y lo imprime. Despues, alguien paga ese link con la tarjeta de prueba del
manual, Handy manda el aviso al webhook del backend publico, y con --estado se
ve si llego y que hizo.

Uso:
    python -m v2.scripts.probar_pago_handy                       crea un cobro y muestra el link
    python -m v2.scripts.probar_pago_handy --monto 250           otro monto (UYU)
    python -m v2.scripts.probar_pago_handy --estado <referencia> estado del cobro y avisos recibidos
    python -m v2.scripts.probar_pago_handy --pendientes          cobros sin resolucion

Necesita en el .env (o en el entorno):
    DATABASE_URL           la misma base que usa el backend publico (develop)
    BASE_URL               la URL PUBLICA del backend, la que Handy puede alcanzar
    HANDY_BASE_URL         https://api.payments.arriba.uy/api/v2  (testing)
    HANDY_MERCHANT_SECRET  el secret de testing del manual
    HANDY_WEBHOOK_SECRETO  EL MISMO que tiene el backend publico: el callback lo
                           lleva en la ruta, y si no coincide el webhook responde 404

El script no muestra los valores de las variables, solo si estan.
"""
import argparse
import os
import sys
from decimal import Decimal
from urllib.parse import urlparse

# Cargar .env antes de importar nada del proyecto
try:
    from dotenv import load_dotenv
    if os.path.exists(".env"):
        load_dotenv(override=True)
except ImportError:
    pass

from sqlmodel import select

from database.database import get_db_session
from v2.models.pago import Pago, PagoNotificacion, PagoCreate
from v2.models.enums import ProveedorPago
from v2.services.pago_service import PagoService

VARIABLES = ["DATABASE_URL", "BASE_URL", "HANDY_BASE_URL", "HANDY_MERCHANT_SECRET", "HANDY_WEBHOOK_SECRETO"]


def verificar_entorno() -> bool:
    faltan = [v for v in VARIABLES if not os.getenv(v)]
    for v in VARIABLES:
        print(f"  {v:<24} {'falta' if v in faltan else 'ok'}")
    if faltan:
        print("\nFaltan variables. Sin eso no se puede armar el callback o llamar a Handy.")
        return False

    host = urlparse(os.getenv("BASE_URL", "")).hostname or ""
    if host in ("localhost", "127.0.0.1") or host.endswith(".local") or host.endswith(".invalid"):
        print(f"\nBASE_URL apunta a {host}: Handy no va a poder llegar al webhook.")
        print("Tiene que ser la URL publica del backend (la de Easypanel).")
        return False

    if "arriba.uy" not in os.getenv("HANDY_BASE_URL", ""):
        print("\nHANDY_BASE_URL no es el ambiente de testing (api.payments.arriba.uy).")
        print("Este script es para probar; no lo corras contra produccion.")
        return False
    return True


def crear(monto: Decimal, email: str | None, concepto: str, sin_factura: bool = False):
    servicio = PagoService()
    if sin_factura:
        # Hipotesis del 18/09/2026: el secret de testing es compartido por todos
        # los integradores, y Plexo podria rechazar un InvoiceNumber repetido
        # (respuesta 6 de Handy). Mandamos el id del cobro como factura, y los
        # ids chicos (1, 2, 3...) ya existen seguro en ese comercio de prueba.
        # Con esto el cobro va sin InvoiceNumber, para descartarlo.
        original = servicio.handy.crear_pago
        servicio.handy.crear_pago = lambda **kw: original(**{**kw, "numero_factura": None})
        print("\n(sin InvoiceNumber)")
    print(f"\nCallback: {servicio.callback_url().rsplit('/', 1)[0]}/<secreto>")

    with get_db_session() as session:
        pago = servicio.iniciar_pago(PagoCreate(
            proveedor=ProveedorPago.HANDY,
            moneda=858,
            monto_total=monto,
            monto_gravado=(monto / Decimal("1.22")).quantize(Decimal("0.01")),
            concepto=concepto,
            email_comprador=email,
        ), session)

        print(f"\nCobro creado: id={pago.id}  estado={pago.estado.value}")
        print(f"Referencia:   {pago.referencia_externa}")
        print(f"\nLink de pago:\n  {pago.url_pago}")
        print(
            "\nPagalo con la tarjeta de prueba del manual de Handy (Mastercard de testing)."
            "\nDespues, para ver si llego el aviso:"
            f"\n  python -m v2.scripts.probar_pago_handy --estado {pago.referencia_externa}"
        )


def estado(referencia: str):
    with get_db_session() as session:
        pago = session.exec(select(Pago).where(Pago.referencia_externa == referencia)).first()
        if not pago:
            print(f"No hay ningun cobro con referencia {referencia}")
            sys.exit(1)

        print(f"\nCobro id={pago.id}  referencia={pago.referencia_externa}")
        print(f"  estado              {pago.estado.value}")
        print(f"  estado_proveedor    {pago.estado_proveedor}")
        print(f"  monto               {pago.monto_total} ({pago.moneda})")
        print(f"  medio_pago          {pago.medio_pago}")
        print(f"  fecha_creacion      {pago.fecha_creacion}")
        print(f"  fecha_pago          {pago.fecha_pago}")
        print(f"  inscripcion         {pago.inscripcion_programa_id}")

        avisos = session.exec(
            select(PagoNotificacion).where(PagoNotificacion.pago_id == pago.id)
            .order_by(PagoNotificacion.fecha_recepcion)
        ).all()
        # Los que llegaron con la referencia pero no se pudieron vincular
        sueltos = session.exec(
            select(PagoNotificacion).where(
                PagoNotificacion.referencia_externa == referencia,
                PagoNotificacion.pago_id.is_(None),  # type: ignore[union-attr]
            )
        ).all()

        if not avisos and not sueltos:
            print("\nTodavia no llego ningun aviso de Handy.")
            print("Si ya pagaste hace mas de un minuto, revisar: BASE_URL publica, el secreto")
            print("del webhook igual en el backend y aca, y los logs del backend.")
            return

        print(f"\nAvisos recibidos: {len(avisos) + len(sueltos)}")
        for a in list(avisos) + list(sueltos):
            cuerpo = a.cuerpo or {}
            datos = cuerpo.get("PurchaseData") or {}
            instrumento = cuerpo.get("InstrumentData") or {}
            print(f"  {a.fecha_recepcion}  {'ACEPTADO' if a.aceptada else 'RECHAZADO'}  "
                  f"origen={cuerpo.get('origen', 'handy')}  ip={a.ip_origen}")
            if datos:
                print(f"      Status={datos.get('Status')}  TotalAmount={datos.get('TotalAmount')}  "
                      f"Currency={datos.get('Currency')}  emisor={instrumento.get('IssuerName')}")
            if "Success" in cuerpo:
                print(f"      Devolucion: Success={cuerpo.get('Success')}  {cuerpo.get('Message', '')}")
            if a.motivo_rechazo:
                print(f"      motivo: {a.motivo_rechazo}")


def pendientes():
    with get_db_session() as session:
        filas = PagoService().pendientes(session, horas=0)
        if not filas:
            print("No hay cobros sin resolucion.")
            return
        print(f"{len(filas)} cobros sin resolucion:")
        for p in filas:
            print(f"  id={p.id:<5} {p.estado.value:<9} {p.fecha_creacion:%Y-%m-%d %H:%M}  "
                  f"{p.monto_total:>10} {p.moneda}  {p.concepto[:40]}  ref={p.referencia_externa}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--monto", type=Decimal, default=Decimal("100.00"), help="Monto en UYU (default 100)")
    parser.add_argument("--email", default=None, help="Email del comprador de prueba (opcional)")
    parser.add_argument("--concepto", default="Prueba de integracion Handy (testing)")
    parser.add_argument("--estado", metavar="REFERENCIA", help="Ver el estado de un cobro y sus avisos")
    parser.add_argument("--pendientes", action="store_true", help="Listar cobros sin resolucion")
    parser.add_argument("--sin-factura", action="store_true",
                        help="No mandar InvoiceNumber (descarta rechazos por factura repetida en el comercio de prueba)")
    args = parser.parse_args()

    if args.estado:
        estado(args.estado)
        return
    if args.pendientes:
        pendientes()
        return

    print("Variables de entorno:")
    if not verificar_entorno():
        sys.exit(1)
    try:
        crear(args.monto, args.email, args.concepto, sin_factura=args.sin_factura)
    except ValueError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
