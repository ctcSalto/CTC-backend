"""
Registro propio de los cobros. Agnostico del proveedor.

POR QUE EXISTE
--------------
Handy no firma sus notificaciones, no reintenta si la entrega falla y no expone
ningun endpoint para consultar el estado de un pago. Sin un registro propio:

  - no hay contra que validar un aviso de "pago exitoso", y
  - un aviso perdido no deja NINGUN rastro, con el pago cobrado del lado de
    Handy e invisible del nuestro.

Ver docs/HANDY_RESPUESTAS.md.

POR QUE AGNOSTICO DEL PROVEEDOR
-------------------------------
MercadoPago se queda aunque no se use para cursos, y a futuro puede sumarse otra
pasarela para vender al exterior. La columna `proveedor` no cuesta nada hoy;
migrar despues una tabla llena de pagos reales a un modelo generico, si.

La conciliacion es facil porque el identificador es NUESTRO en los dos casos:
`TransactionExternalId` en Handy, `external_reference` en MercadoPago. Es el
mismo `referencia_externa` de aca.
"""
from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import os
from zoneinfo import ZoneInfo

from v2.models.enums import ProveedorPago, EstadoPago

if TYPE_CHECKING:
    from v2.models.alumno import Alumno
    from v2.models.programa import Programa
    from v2.models.inscripcion_programa import InscripcionPrograma


def get_uruguay_tz():
    return ZoneInfo(os.getenv('TIME_ZONE', 'America/Montevideo'))


# ── Modelos de tabla ─────────────────────────────────────────────────────────

class Pago(SQLModel, table=True):
    __tablename__ = "pago"

    id: Optional[int] = Field(default=None, primary_key=True)

    # El identificador lo generamos nosotros y viaja al proveedor. Unico: es la
    # clave de conciliacion y lo que sostiene la idempotencia del webhook.
    referencia_externa: str = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True, max_length=36,
        description="UUID propio. TransactionExternalId en Handy, external_reference en MercadoPago",
    )
    proveedor: ProveedorPago = Field(index=True, description="Quien cobra")
    proveedor_id: Optional[str] = Field(
        default=None, max_length=100,
        description="Identificador del lado del proveedor, si lo devuelve",
    )

    estado: EstadoPago = Field(
        default=EstadoPago.INICIADO, index=True,
        description="Estado interno normalizado",
    )
    estado_proveedor: Optional[str] = Field(
        default=None, max_length=50,
        description="Codigo crudo del proveedor, sin interpretar",
    )

    moneda: int = Field(description="ISO 4217 numerico: 858 UYU, 840 USD")
    monto_total: Decimal = Field(
        max_digits=12, decimal_places=2, description="Total con IVA",
    )
    monto_gravado: Decimal = Field(
        default=Decimal("0"), max_digits=12, decimal_places=2,
        description="Monto gravado. 0 si esta exento",
    )

    concepto: str = Field(max_length=255, description="Que se esta comprando")

    # Que se compra. Nullable porque puede venderse algo que no sea un programa.
    programa_id: Optional[int] = Field(
        default=None, foreign_key="programa.id", index=True,
        description="Programa que se esta comprando",
    )

    # Quien compra. Nullable a proposito: al momento de pagar puede no existir
    # todavia el alumno, sobre todo en una venta que llega desde el CRM.
    alumno_id: Optional[int] = Field(
        default=None, foreign_key="alumno.id", index=True,
    )
    email_comprador: Optional[str] = Field(
        default=None, max_length=255,
        description="Para poder contactar ante un problema con el cobro",
    )

    # El pago habilita la inscripcion: se completa cuando el cobro se acredita.
    # Nullable porque al crear el pago la inscripcion todavia no existe.
    inscripcion_programa_id: Optional[int] = Field(
        default=None, foreign_key="inscripcion_programa.id", index=True,
        description="Inscripcion habilitada por este pago, una vez acreditado",
    )

    url_pago: Optional[str] = Field(
        default=None, max_length=500, description="Link que devuelve el proveedor",
    )
    numero_factura: Optional[int] = Field(
        default=None, description="InvoiceNumber en Handy",
    )
    medio_pago: Optional[str] = Field(
        default=None, max_length=100,
        description="Como pago: Mastercard, Redpagos, ITAU...",
    )

    fecha_creacion: datetime = Field(
        default_factory=lambda: datetime.now(get_uruguay_tz()), index=True,
    )
    fecha_actualizacion: Optional[datetime] = Field(default=None)
    fecha_pago: Optional[datetime] = Field(
        default=None, description="Cuando se acredito",
    )
    # Redpagos genera una orden con vencimiento que el alumno paga despues en el
    # local: entre que elige el curso y paga pueden pasar dias.
    fecha_vencimiento: Optional[datetime] = Field(
        default=None, description="Solo para pagos offline como Redpagos",
    )

    id_rastreo: Optional[str] = Field(
        default_factory=lambda: str(uuid4()),
        unique=True, index=True, description="UUID de trazabilidad",
    )

    # Relaciones
    notificaciones: List["PagoNotificacion"] = Relationship(back_populates="pago")


class PagoNotificacion(SQLModel, table=True):
    """
    Todo lo que llega al webhook, aceptado o rechazado, tal cual llega.

    Handy no reintenta y no tiene consulta de estado: este log es la unica
    evidencia disponible ante un reclamo o una diferencia de conciliacion, y la
    unica forma de detectar que alguien esta probando direcciones.
    """
    __tablename__ = "pago_notificacion"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Nullable: un aviso rechazado puede no corresponder a ningun pago nuestro,
    # y justamente esos son los que interesa conservar.
    pago_id: Optional[int] = Field(
        default=None, foreign_key="pago.id", index=True,
    )
    referencia_externa: Optional[str] = Field(
        default=None, index=True, max_length=100,
        description="Lo que vino en el aviso, sin validar",
    )
    proveedor: ProveedorPago = Field(index=True)

    cuerpo: Optional[dict] = Field(
        default=None, sa_column=Column(JSON),
        description="Payload crudo, tal como llego",
    )
    aceptada: bool = Field(default=False, index=True)
    motivo_rechazo: Optional[str] = Field(default=None, max_length=255)
    ip_origen: Optional[str] = Field(
        default=None, max_length=45,
        description="Para investigar patrones de rechazo",
    )

    fecha_recepcion: datetime = Field(
        default_factory=lambda: datetime.now(get_uruguay_tz()), index=True,
    )

    # Relaciones
    pago: Optional["Pago"] = Relationship(back_populates="notificaciones")


# ── Schemas ──────────────────────────────────────────────────────────────────

class PagoCreate(SQLModel):
    proveedor: ProveedorPago
    moneda: int
    monto_total: Decimal
    monto_gravado: Optional[Decimal] = None
    concepto: str = Field(max_length=255)
    programa_id: Optional[int] = None
    alumno_id: Optional[int] = None
    email_comprador: Optional[str] = Field(default=None, max_length=255)


class PagoRead(SQLModel):
    id: int
    referencia_externa: str
    proveedor: ProveedorPago
    proveedor_id: Optional[str] = None
    estado: EstadoPago
    estado_proveedor: Optional[str] = None
    moneda: int
    monto_total: Decimal
    monto_gravado: Decimal
    concepto: str
    programa_id: Optional[int] = None
    alumno_id: Optional[int] = None
    email_comprador: Optional[str] = None
    inscripcion_programa_id: Optional[int] = None
    url_pago: Optional[str] = None
    numero_factura: Optional[int] = None
    medio_pago: Optional[str] = None
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = None
    fecha_pago: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None
    id_rastreo: Optional[str] = None


class PagoNotificacionRead(SQLModel):
    id: int
    pago_id: Optional[int] = None
    referencia_externa: Optional[str] = None
    proveedor: ProveedorPago
    aceptada: bool
    motivo_rechazo: Optional[str] = None
    ip_origen: Optional[str] = None
    fecha_recepcion: datetime
