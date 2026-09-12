"""
Cobros con Handy.

Tres superficies con tres niveles de acceso distintos:
  - el webhook, PUBLICO y sin auth (Handy no manda credenciales), protegido
    solo por el segmento secreto de la ruta;
  - el inicio de un cobro, desde el portal del alumno o desde admin;
  - los informes, solo admin.

EL WEBHOOK NUNCA DEVUELVE 500. Handy no reintenta si la entrega falla y no hay
forma de consultar despues que paso: un error nuestro costaria el aviso. Se
recibe, se persiste, se responde 200, y si algo salio mal queda en el registro
para que el informe de pendientes lo encuentre.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlmodel import Session
from typing import List, Optional

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import (
    require_administrativo, require_estudiante, get_current_usuario,
)
from v2.models.usuario import UsuarioRead
from v2.models.pago import PagoCreate, PagoRead, PagoNotificacionRead
from v2.models.enums import ProveedorPago
from v2.models.alumno import Alumno
from sqlmodel import select

router = APIRouter(tags=["v2 - Pagos"])


# ── Webhook ──────────────────────────────────────────────────────────────────

@router.post(
    "/v2/pagos/handy/webhook/{secreto}",
    summary="Webhook de Handy",
    description="Recibe los avisos de cambio de estado de un cobro. Publico: "
                "Handy no manda credenciales. Siempre responde 200.",
    include_in_schema=False,   # no publicar la ruta en /docs
)
async def webhook_handy(
    secreto: str,
    request: Request,
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    servicio = v2_services.pagoService

    # El segmento secreto es lo unico que separa esta ruta de un scanner. Si no
    # coincide, 404 y nada mas: no se confirma que la ruta exista.
    if not servicio.secreto_webhook_valido(secreto):
        raise HTTPException(status_code=404)

    ip = request.client.host if request.client else None
    try:
        cuerpo = await request.json()
    except Exception:  # noqa: BLE001
        cuerpo = {"_crudo": (await request.body())[:2000].decode("utf-8", "replace")}

    # procesar_notificacion nunca lanza; esto es cinturon y tirantes
    try:
        resultado = servicio.procesar_notificacion(cuerpo, session, ip_origen=ip)
        return JSONResponse(
            status_code=200,
            content={"recibido": True, "aceptado": resultado.aceptada},
        )
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=200, content={"recibido": True, "aceptado": False})


# ── Iniciar un cobro ─────────────────────────────────────────────────────────

class _PagoAlumnoBody(PagoCreate):
    """Lo que manda el alumno: no puede elegir a quien se le cobra."""
    proveedor: ProveedorPago = ProveedorPago.HANDY
    alumno_id: Optional[int] = None   # se pisa con el del token
    email_comprador: Optional[str] = None


@router.post(
    "/v2/portal/estudiante/pagos",
    response_model=PagoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar el pago de un programa",
    description="Genera el link de pago y lo devuelve en `url_pago`. Redirigir "
                "al alumno ahi. Si ya hay un intento abierto y reciente para el "
                "mismo programa, devuelve ese en vez de crear otro.",
)
async def iniciar_pago_alumno(
    data: _PagoAlumnoBody,
    current_usuario: UsuarioRead = Depends(require_estudiante),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    alumno = session.exec(
        select(Alumno).where(Alumno.usuario_id == current_usuario.id)
    ).first()
    if not alumno:
        raise HTTPException(status_code=403, detail="El usuario no tiene perfil de alumno")

    data.alumno_id = alumno.id
    data.email_comprador = current_usuario.email
    try:
        return v2_services.pagoService.iniciar_pago(data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/v2/admin/pagos",
    response_model=PagoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar un cobro desde administracion",
    description="Para ventas que no arrancan en el portal: por ejemplo, un "
                "interesado que llega desde el CRM y todavia no es alumno. "
                "`alumno_id` es opcional; sin el, el pago queda PAGADO sin "
                "inscripcion y aparece en el informe para resolverlo a mano.",
)
async def iniciar_pago_admin(
    data: PagoCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        return v2_services.pagoService.iniciar_pago(data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Consultas ────────────────────────────────────────────────────────────────

@router.get(
    "/v2/portal/estudiante/pagos",
    response_model=List[PagoRead],
    summary="Mis pagos",
)
async def mis_pagos(
    current_usuario: UsuarioRead = Depends(require_estudiante),
    session: Session = Depends(get_session),
):
    from v2.models.pago import Pago
    alumno = session.exec(
        select(Alumno).where(Alumno.usuario_id == current_usuario.id)
    ).first()
    if not alumno:
        return []
    return list(session.exec(
        select(Pago).where(Pago.alumno_id == alumno.id)
        .order_by(Pago.fecha_creacion.desc())
    ).all())


@router.get(
    "/v2/admin/pagos/{pago_id}",
    response_model=PagoRead,
    summary="Detalle de un pago",
)
async def detalle_pago(
    pago_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    from v2.models.pago import Pago
    pago = session.get(Pago, pago_id)
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    return pago


@router.get(
    "/v2/admin/pagos/{pago_id}/notificaciones",
    response_model=List[PagoNotificacionRead],
    summary="Avisos recibidos de un pago",
    description="Todo lo que Handy mando sobre este pago, aceptado o rechazado. "
                "Es la evidencia ante un reclamo.",
)
async def notificaciones_de_pago(
    pago_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    session: Session = Depends(get_session),
):
    from v2.models.pago import PagoNotificacion
    return list(session.exec(
        select(PagoNotificacion).where(PagoNotificacion.pago_id == pago_id)
        .order_by(PagoNotificacion.fecha_recepcion)
    ).all())


# ── Informes ─────────────────────────────────────────────────────────────────

@router.get(
    "/v2/admin/pagos/informes/pendientes",
    response_model=List[PagoRead],
    summary="Cobros sin resolucion",
    description="Iniciados o pendientes hace mas de N horas. Es el insumo para "
                "cotejar contra el panel de Handy: sin reintentos ni consulta de "
                "estado, un aviso perdido solo se descubre por aca.",
)
async def informe_pendientes(
    horas: int = Query(default=2, ge=1, le=720),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return v2_services.pagoService.pendientes(session, horas=horas)


@router.get(
    "/v2/admin/pagos/informes/sin-inscripcion",
    response_model=List[PagoRead],
    summary="Pagados sin inscripcion",
    description="Cobros acreditados de un programa que no tienen alumno "
                "asociado. Hay que crear el alumno y vincularlo a mano.",
)
async def informe_sin_inscripcion(
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return v2_services.pagoService.pagos_sin_inscripcion(session)


@router.get(
    "/v2/admin/pagos/informes/rechazos",
    summary="Avisos rechazados en las ultimas horas",
    description="Un numero alto es la señal de que alguien esta probando la ruta.",
)
async def informe_rechazos(
    horas: int = Query(default=24, ge=1, le=720),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return {"horas": horas, "rechazos": v2_services.pagoService.rechazos_recientes(session, horas)}
