"""
Cobros. Hoy solo Handy; el modelo es agnostico del proveedor.

LAS TRES REGLAS QUE SALEN DE LO QUE HANDY NO OFRECE
---------------------------------------------------
Handy no firma las notificaciones, no reintenta si la entrega falla y no tiene
endpoint de consulta (docs/HANDY_RESPUESTAS.md). Entonces:

1. Un aviso se acepta SOLO si contrasta contra una fila nuestra: la referencia
   existe, el estado admite la transicion, y el monto y la moneda coinciden con
   lo que originamos. Es la unica validacion posible.

2. procesar_notificacion NUNCA lanza. Persiste el aviso en crudo antes de
   tocar nada, y si el procesamiento falla lo deja registrado y devuelve
   igual. Un error nuestro no puede costar un aviso que Handy no va a repetir.

3. La idempotencia es por estado, no por contador: un aviso repetido cae en
   "misma transicion" y se acepta sin efecto. Un aviso que pide una transicion
   invalida (PAGADO -> INICIADO) se rechaza y queda registrado.

4. Lo que Handy no avisa lo cierra bedelia a mano, con registro. Un aviso
   perdido no se recupera solo: bedelia lo ve en el informe de pendientes,
   lo verifica en el panel de Handy y lo concilia con conciliar_manual. Eso
   pasa por la misma maquina de estados que un aviso real y deja una
   PagoNotificacion con origen "conciliacion_manual" y quien lo hizo.

EL PAGO HABILITA LA INSCRIPCION
-------------------------------
Al pasar a PAGADO, si el pago tiene alumno y programa, se crea la
InscripcionPrograma y se vincula. Si no tiene alumno —venta desde el CRM a
alguien que todavia no existe— queda PAGADO sin inscripcion, y bedelia lo
resuelve desde el informe.
"""
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List
from zoneinfo import ZoneInfo

from sqlmodel import Session, select, col

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.pago import Pago, PagoNotificacion, PagoCreate, PagoConciliacion
from v2.models.usuario import UsuarioRead
from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.programa import Programa
from v2.models.alumno import Alumno
from v2.models.enums import ProveedorPago, EstadoPago, EstadoInscripcionPrograma
from external_services.handy_api.client import HandyClient, HandyError


def get_uruguay_tz():
    return ZoneInfo(os.getenv('TIME_ZONE', 'America/Montevideo'))


# Transiciones validas. Lo que no esta aca se rechaza. Repetir el estado actual
# se acepta sin efecto: asi un aviso duplicado no hace nada y tampoco es error.
TRANSICIONES = {
    EstadoPago.INICIADO: {EstadoPago.PENDIENTE, EstadoPago.PAGADO, EstadoPago.FALLIDO},
    EstadoPago.PENDIENTE: {EstadoPago.PAGADO, EstadoPago.FALLIDO},
    EstadoPago.PAGADO: {EstadoPago.DEVUELTO},
    EstadoPago.FALLIDO: set(),
    EstadoPago.DEVUELTO: set(),
}

# Status de Handy (PurchaseData.Status) -> estado interno
ESTADO_HANDY = {
    0: EstadoPago.INICIADO,
    1: EstadoPago.PAGADO,
    2: EstadoPago.FALLIDO,
    3: EstadoPago.PENDIENTE,
}

# Si el alumno clickea "pagar" veinte veces, se reutiliza el intento abierto en
# vez de generar veinte links. Pasado este tiempo se considera abandonado y se
# genera uno nuevo.
VENTANA_REUSO = timedelta(minutes=30)

# Handy solo devuelve hasta estos montos, una vez por venta y solo tarjeta
# (manual v2.0). Se chequea aca para dar un mensaje claro antes de llamar.
TOPE_DEVOLUCION = {858: Decimal("10000"), 840: Decimal("250")}

# Lo que bedelia puede cargar a mano: lo que puede ver en el panel de Handy
ESTADOS_CONCILIABLES = {EstadoPago.PAGADO, EstadoPago.FALLIDO, EstadoPago.DEVUELTO}


class ResultadoNotificacion:
    """Lo que devuelve procesar_notificacion. Nunca es una excepcion."""

    def __init__(self, aceptada: bool, motivo: str, pago: Optional[Pago] = None,
                 notificacion: Optional[PagoNotificacion] = None):
        self.aceptada = aceptada
        self.motivo = motivo
        self.pago = pago
        self.notificacion = notificacion

    def __repr__(self):
        return f"<ResultadoNotificacion aceptada={self.aceptada} motivo={self.motivo!r}>"


class PagoService(BaseServiceWithFilters[Pago]):
    def __init__(self, cliente_handy: Optional[HandyClient] = None):
        super().__init__(Pago)
        self.handy = cliente_handy or HandyClient()

    # ── Configuracion ─────────────────────────────────────────────────────────

    @staticmethod
    def callback_url() -> str:
        """
        A donde Handy manda los avisos. Lleva un segmento secreto en la ruta:
        no es autenticacion, pero saca del juego a quien escanea rutas.
        """
        base = os.getenv("BASE_URL", "").rstrip("/")
        secreto = os.getenv("HANDY_WEBHOOK_SECRETO", "")
        if not base or not secreto:
            raise ValueError("Faltan BASE_URL o HANDY_WEBHOOK_SECRETO para armar el callback")
        return f"{base}/v2/pagos/handy/webhook/{secreto}"

    @staticmethod
    def secreto_webhook_valido(secreto: str) -> bool:
        esperado = os.getenv("HANDY_WEBHOOK_SECRETO", "")
        return bool(esperado) and secreto == esperado

    # ── Iniciar un cobro ──────────────────────────────────────────────────────

    def iniciar_pago(self, data: PagoCreate, session: Session) -> Pago:
        """
        Crea el registro y le pide a Handy el link. Devuelve el Pago con
        url_pago cargada, listo para redirigir al comprador.

        Si ya hay un intento abierto y reciente para el mismo comprador y
        programa, se devuelve ese en vez de crear otro.
        """
        if data.proveedor != ProveedorPago.HANDY:
            raise ValueError(f"Proveedor {data.proveedor.value} no implementado todavia")

        if data.programa_id is not None:
            programa = session.get(Programa, data.programa_id)
            if not programa:
                raise ValueError(f"Programa {data.programa_id} no encontrado")
        if data.alumno_id is not None and not session.get(Alumno, data.alumno_id):
            raise ValueError(f"Alumno {data.alumno_id} no encontrado")

        abierto = self._intento_abierto(data, session)
        if abierto:
            return abierto

        pago = Pago(
            proveedor=data.proveedor,
            moneda=data.moneda,
            monto_total=data.monto_total,
            monto_gravado=data.monto_gravado if data.monto_gravado is not None else Decimal("0"),
            concepto=data.concepto,
            programa_id=data.programa_id,
            alumno_id=data.alumno_id,
            email_comprador=data.email_comprador,
        )
        session.add(pago)
        session.flush()   # para tener el id, que usamos como numero de factura
        session.refresh(pago)

        try:
            link = self.handy.crear_pago(
                referencia_externa=pago.referencia_externa,
                moneda=pago.moneda,
                monto_total=pago.monto_total,
                monto_gravado=pago.monto_gravado,
                concepto=pago.concepto,
                callback_url=self.callback_url(),
                site_url=os.getenv("HANDY_SITE_URL", os.getenv("BASE_URL", "")),
                commerce_name=os.getenv("HANDY_COMMERCE_NAME", "CTC Salto"),
                numero_factura=pago.id,
            )
        except (HandyError, ValueError) as e:
            # Queda registrado que fallo al crear: nunca hubo link, no hay nada
            # que conciliar, pero sirve para depurar.
            pago.estado = EstadoPago.FALLIDO
            pago.estado_proveedor = "error_creacion"
            pago.fecha_actualizacion = datetime.now(get_uruguay_tz())
            session.add(pago)
            session.commit()
            raise ValueError(f"No se pudo generar el link de pago: {e}")

        pago.url_pago = link.url
        pago.numero_factura = pago.id
        session.add(pago)
        session.commit()
        session.refresh(pago)
        return pago

    def _intento_abierto(self, data: PagoCreate, session: Session) -> Optional[Pago]:
        """El caso de los veinte clics: un solo cobro abierto por compra."""
        if data.programa_id is None:
            return None
        if data.alumno_id is None and not data.email_comprador:
            return None

        desde = datetime.now(get_uruguay_tz()) - VENTANA_REUSO
        stmt = select(Pago).where(
            Pago.proveedor == data.proveedor,
            Pago.programa_id == data.programa_id,
            Pago.estado == EstadoPago.INICIADO,
            Pago.fecha_creacion >= desde,
            col(Pago.url_pago).is_not(None),
        )
        if data.alumno_id is not None:
            stmt = stmt.where(Pago.alumno_id == data.alumno_id)
        else:
            stmt = stmt.where(Pago.email_comprador == data.email_comprador)

        return session.exec(stmt.order_by(col(Pago.fecha_creacion).desc())).first()

    # ── Webhook ───────────────────────────────────────────────────────────────

    def procesar_notificacion(
        self, cuerpo: dict, session: Session, ip_origen: Optional[str] = None,
    ) -> ResultadoNotificacion:
        """
        Procesa un aviso de Handy. NUNCA lanza.

        Orden deliberado: primero se guarda el aviso crudo y se hace commit.
        Recien despues se valida y se procesa. Si algo falla en el medio, el
        aviso ya esta guardado y el informe de pendientes lo va a encontrar.
        """
        notificacion = PagoNotificacion(
            proveedor=ProveedorPago.HANDY,
            cuerpo=cuerpo if isinstance(cuerpo, dict) else {"_crudo": str(cuerpo)},
            referencia_externa=self._referencia_de(cuerpo),
            ip_origen=ip_origen,
        )
        session.add(notificacion)
        session.commit()
        session.refresh(notificacion)

        try:
            resultado = self._aplicar_notificacion(cuerpo, notificacion, session)
        except Exception as e:  # noqa: BLE001 - a proposito: nunca lanzar
            session.rollback()
            resultado = ResultadoNotificacion(
                False, f"Error interno al procesar: {type(e).__name__}: {e}"[:255],
                notificacion=notificacion,
            )

        notificacion.aceptada = resultado.aceptada
        notificacion.motivo_rechazo = None if resultado.aceptada else resultado.motivo
        if resultado.pago is not None:
            notificacion.pago_id = resultado.pago.id
        session.add(notificacion)
        session.commit()
        resultado.notificacion = notificacion
        return resultado

    @staticmethod
    def _referencia_de(cuerpo) -> Optional[str]:
        if not isinstance(cuerpo, dict):
            return None
        ref = cuerpo.get("TransactionExternalId")
        return str(ref)[:100] if ref else None

    def _aplicar_notificacion(
        self, cuerpo: dict, notificacion: PagoNotificacion, session: Session,
    ) -> ResultadoNotificacion:
        if not isinstance(cuerpo, dict):
            return ResultadoNotificacion(False, "El cuerpo no es un objeto JSON")

        referencia = self._referencia_de(cuerpo)
        if not referencia:
            return ResultadoNotificacion(False, "Falta TransactionExternalId")

        pago = session.exec(
            select(Pago).where(Pago.referencia_externa == referencia)
        ).first()
        if not pago:
            # El caso que mas importa registrar: alguien manda una referencia
            # que no es nuestra. Puede ser un error de Handy o alguien probando.
            return ResultadoNotificacion(
                False, "La referencia no corresponde a ningun pago nuestro"
            )

        # Aviso de devolucion: forma distinta, sin PurchaseData
        if "PurchaseData" not in cuerpo and "Success" in cuerpo:
            return self._aplicar_devolucion(cuerpo, pago, session)

        datos = cuerpo.get("PurchaseData") or {}
        estado_nuevo = ESTADO_HANDY.get(datos.get("Status"))
        if estado_nuevo is None:
            return ResultadoNotificacion(
                False, f"Status desconocido: {datos.get('Status')!r}", pago=pago
            )

        # La unica validacion posible sin firma: que el aviso hable del monto y
        # la moneda que nosotros originamos.
        problema = self._verificar_montos(pago, datos)
        if problema:
            return ResultadoNotificacion(False, problema, pago=pago)

        return self._transicionar(
            pago, estado_nuevo, session,
            estado_proveedor=str(datos.get("Status")),
            medio_pago=(cuerpo.get("InstrumentData") or {}).get("IssuerName"),
            vencimiento=(cuerpo.get("InstrumentData") or {}).get("Expiration"),
        )

    def _aplicar_devolucion(
        self, cuerpo: dict, pago: Pago, session: Session,
    ) -> ResultadoNotificacion:
        if not cuerpo.get("Success"):
            # Devolucion fallida: se registra, no cambia el estado
            return ResultadoNotificacion(
                True, f"Devolucion fallida segun Handy: {cuerpo.get('Message', '')}"[:255],
                pago=pago,
            )
        return self._transicionar(
            pago, EstadoPago.DEVUELTO, session, estado_proveedor="devolucion",
        )

    @staticmethod
    def _verificar_montos(pago: Pago, datos: dict) -> Optional[str]:
        moneda = datos.get("Currency")
        if moneda is not None and int(moneda) != pago.moneda:
            return f"Moneda distinta: aviso={moneda}, registro={pago.moneda}"

        total = datos.get("TotalAmount")
        if total is not None:
            try:
                if Decimal(str(total)) != Decimal(pago.monto_total):
                    return f"Monto distinto: aviso={total}, registro={pago.monto_total}"
            except (ValueError, ArithmeticError):
                return f"Monto ilegible: {total!r}"
        return None

    def _transicionar(
        self, pago: Pago, estado_nuevo: EstadoPago, session: Session,
        estado_proveedor: Optional[str] = None,
        medio_pago: Optional[str] = None,
        vencimiento: Optional[str] = None,
    ) -> ResultadoNotificacion:
        actual = pago.estado

        # Idempotencia: el mismo aviso dos veces no hace nada, y no es error
        if estado_nuevo == actual:
            return ResultadoNotificacion(
                True, f"Ya estaba en {actual.value}; aviso repetido, sin efecto", pago=pago,
            )

        if estado_nuevo not in TRANSICIONES[actual]:
            return ResultadoNotificacion(
                False,
                f"Transicion invalida: {actual.value} -> {estado_nuevo.value}",
                pago=pago,
            )

        ahora = datetime.now(get_uruguay_tz())
        pago.estado = estado_nuevo
        pago.estado_proveedor = estado_proveedor
        pago.fecha_actualizacion = ahora
        if medio_pago:
            pago.medio_pago = medio_pago[:100]
        if vencimiento:
            pago.fecha_vencimiento = self._parsear_fecha(vencimiento)

        motivo = f"{actual.value} -> {estado_nuevo.value}"

        if estado_nuevo == EstadoPago.PAGADO:
            pago.fecha_pago = ahora
            inscripcion = self._habilitar_inscripcion(pago, session)
            if inscripcion is not None:
                pago.inscripcion_programa_id = inscripcion.id
                motivo += f"; inscripcion {inscripcion.id} habilitada"
            elif pago.programa_id is not None and pago.alumno_id is None:
                motivo += "; sin alumno, la inscripcion la resuelve bedelia"

        session.add(pago)
        session.commit()
        session.refresh(pago)
        return ResultadoNotificacion(True, motivo, pago=pago)

    def _habilitar_inscripcion(
        self, pago: Pago, session: Session,
    ) -> Optional[InscripcionPrograma]:
        """
        El pago habilita la inscripcion. Si ya habia una activa, se vincula a
        esa en vez de duplicarla: pagar dos veces el mismo curso no inscribe
        dos veces.
        """
        if pago.alumno_id is None or pago.programa_id is None:
            return None

        existente = session.exec(
            select(InscripcionPrograma).where(
                InscripcionPrograma.alumno_id == pago.alumno_id,
                InscripcionPrograma.programa_id == pago.programa_id,
                InscripcionPrograma.estado == EstadoInscripcionPrograma.ACTIVA,
            )
        ).first()
        if existente:
            return existente

        inscripcion = InscripcionPrograma(
            alumno_id=pago.alumno_id,
            programa_id=pago.programa_id,
            anio_ingreso=datetime.now(get_uruguay_tz()).year,
        )
        session.add(inscripcion)
        session.flush()
        session.refresh(inscripcion)
        return inscripcion

    @staticmethod
    def _parsear_fecha(valor: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    # ── Conciliacion manual ───────────────────────────────────────────────────

    def conciliar_manual(
        self, pago_id: int, data: PagoConciliacion, usuario: UsuarioRead, session: Session,
    ) -> Pago:
        """
        Cierra a mano un cobro cuyo aviso se perdio, despues de verificarlo en
        el panel de Handy. Pasa por la misma maquina de estados que un aviso
        real (una transicion invalida se rechaza igual) y, si queda PAGADO,
        habilita la inscripcion igual que lo haria el webhook.

        Queda registrado como una PagoNotificacion aceptada con origen
        "conciliacion_manual", el usuario y el motivo: es la evidencia de por
        que cambio el estado sin aviso del proveedor.
        """
        pago = session.get(Pago, pago_id)
        if not pago:
            raise ValueError(f"Pago {pago_id} no encontrado")
        if data.estado not in ESTADOS_CONCILIABLES:
            raise ValueError(
                f"Solo se puede conciliar a {', '.join(e.value for e in ESTADOS_CONCILIABLES)}"
            )
        if data.estado == pago.estado:
            raise ValueError(f"El pago ya esta en {pago.estado.value}")
        if data.estado not in TRANSICIONES[pago.estado]:
            raise ValueError(
                f"Transicion invalida: {pago.estado.value} -> {data.estado.value}"
            )

        registro = PagoNotificacion(
            pago_id=pago.id,
            proveedor=pago.proveedor,
            referencia_externa=pago.referencia_externa,
            cuerpo={
                "origen": "conciliacion_manual",
                "usuario_id": usuario.id,
                "usuario_email": usuario.email,
                "estado_anterior": pago.estado.value,
                "estado": data.estado.value,
                "motivo": data.motivo,
                "proveedor_id": data.proveedor_id,
            },
            aceptada=True,
        )
        session.add(registro)

        if data.proveedor_id:
            pago.proveedor_id = data.proveedor_id
        resultado = self._transicionar(
            pago, data.estado, session, estado_proveedor="conciliacion_manual",
        )
        if not resultado.aceptada:   # no deberia pasar: ya se valido arriba
            session.rollback()
            raise ValueError(resultado.motivo)
        return resultado.pago

    # ── Devolucion ────────────────────────────────────────────────────────────

    def devolver(self, pago_id: int, usuario: UsuarioRead, session: Session) -> Pago:
        """
        Le pide a Handy la devolucion de un cobro acreditado. El estado NO
        cambia aca: Handy responde si acepto el pedido, y el resultado real
        llega despues por el webhook (cuerpo con Success), que es el que pasa
        el pago a DEVUELTO. Mientras tanto queda estado_proveedor =
        "devolucion_solicitada" para no pedirla dos veces.

        Restricciones de Handy: una sola vez por venta, solo tarjeta, tope
        UYU 10.000 / USD 250.
        """
        pago = session.get(Pago, pago_id)
        if not pago:
            raise ValueError(f"Pago {pago_id} no encontrado")
        if pago.estado != EstadoPago.PAGADO:
            raise ValueError(f"Solo se devuelve un pago en PAGADO; este esta en {pago.estado.value}")
        if pago.estado_proveedor == "devolucion_solicitada":
            raise ValueError("La devolucion ya se pidio; Handy la resuelve por webhook")
        tope = TOPE_DEVOLUCION.get(pago.moneda)
        if tope is not None and Decimal(pago.monto_total) > tope:
            raise ValueError(
                f"Handy no devuelve mas de {tope} en moneda {pago.moneda}; "
                f"este pago es de {pago.monto_total}. Hay que hacerlo por fuera."
            )

        try:
            respuesta = self.handy.devolver_pago(pago.referencia_externa, self.callback_url())
        except (HandyError, ValueError) as e:
            raise ValueError(f"Handy rechazo la devolucion: {e}")

        registro = PagoNotificacion(
            pago_id=pago.id,
            proveedor=pago.proveedor,
            referencia_externa=pago.referencia_externa,
            cuerpo={
                "origen": "solicitud_devolucion",
                "usuario_id": usuario.id,
                "usuario_email": usuario.email,
                "respuesta_handy": respuesta if isinstance(respuesta, dict) else str(respuesta),
            },
            aceptada=True,
        )
        session.add(registro)

        pago.estado_proveedor = "devolucion_solicitada"
        pago.fecha_actualizacion = datetime.now(get_uruguay_tz())
        session.add(pago)
        session.commit()
        session.refresh(pago)
        return pago

    # ── Consultas ─────────────────────────────────────────────────────────────

    def get_by_referencia(self, referencia: str, session: Session) -> Optional[Pago]:
        return session.exec(
            select(Pago).where(Pago.referencia_externa == referencia)
        ).first()

    def pendientes(self, session: Session, horas: int = 2) -> List[Pago]:
        """
        Cobros iniciados que no recibieron resolucion pasado cierto tiempo.

        Es el insumo del unico mecanismo de recuperacion que existe: cotejar a
        mano contra el panel de Handy. Sin reintentos ni consulta de estado, un
        aviso perdido solo se descubre por aca.
        """
        corte = datetime.now(get_uruguay_tz()) - timedelta(hours=horas)
        return list(session.exec(
            select(Pago).where(
                col(Pago.estado).in_([EstadoPago.INICIADO, EstadoPago.PENDIENTE]),
                Pago.fecha_creacion < corte,
            ).order_by(Pago.fecha_creacion)
        ).all())

    def pagos_sin_inscripcion(self, session: Session) -> List[Pago]:
        """Pagados con programa pero sin inscripcion: ventas sin alumno todavia."""
        return list(session.exec(
            select(Pago).where(
                Pago.estado == EstadoPago.PAGADO,
                col(Pago.programa_id).is_not(None),
                col(Pago.inscripcion_programa_id).is_(None),
            ).order_by(Pago.fecha_pago)
        ).all())

    def rechazos_recientes(self, session: Session, horas: int = 24) -> int:
        """Cuantos avisos se rechazaron ultimamente. Muchos = alguien probando."""
        corte = datetime.now(get_uruguay_tz()) - timedelta(hours=horas)
        return len(session.exec(
            select(PagoNotificacion.id).where(
                PagoNotificacion.aceptada == False,
                PagoNotificacion.fecha_recepcion >= corte,
            )
        ).all())
