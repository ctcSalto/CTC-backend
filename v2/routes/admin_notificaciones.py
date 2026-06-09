"""
Endpoints de administración de notificaciones.
Permite a admin ver pendientes, enviar calificaciones, y enviar emails manuales.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.enums import TipoNotificacion


router = APIRouter(
    prefix="/v2/admin/notificaciones",
    tags=["v2 - Admin Notificaciones"],
)


# ── Schemas de request ──────────────────────────────────────────────────────

class CalificacionBatchRequest(BaseModel):
    inscripcion_ids: list[int]


class EnvioIndividualRequest(BaseModel):
    usuario_id: int
    asunto: str
    mensaje: str  # HTML del cuerpo del email


class EnvioMasivoRequest(BaseModel):
    filtro: dict  # {programa_id?, instancia_cursado_id?}
    asunto: str
    mensaje: str  # HTML del cuerpo del email


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get(
    "/pendientes",
    summary="Calificaciones pendientes de notificar",
    description="Retorna inscripciones con estado final (exonerado, a_examen, aprobado, reprobado) "
                "que aún no fueron notificadas al estudiante.",
)
async def get_pendientes(
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
    current_usuario: UsuarioRead = Depends(require_administrativo),
):
    return v2_services.notificationService.get_pendientes_calificacion(session)


@router.post(
    "/calificacion/batch",
    summary="Enviar notificaciones de calificación en lote",
    description="Envía emails de calificación a múltiples inscripciones.",
)
async def enviar_calificacion_batch(
    body: CalificacionBatchRequest,
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
    current_usuario: UsuarioRead = Depends(require_administrativo),
):
    enviados = 0
    errores = []

    for inscripcion_id in body.inscripcion_ids:
        try:
            resultado = v2_services.notificationService.notificar_calificacion(
                inscripcion_id, current_usuario.id, session
            )
            if resultado["ok"]:
                enviados += 1
            else:
                errores.append({
                    "inscripcion_id": inscripcion_id,
                    "error": resultado.get("error", "Error desconocido"),
                })
        except ValueError as e:
            errores.append({"inscripcion_id": inscripcion_id, "error": str(e)})

    return {"enviados": enviados, "errores": errores}


@router.post(
    "/calificacion/{inscripcion_id}",
    summary="Enviar notificación de calificación",
    description="Envía email al estudiante informando su calificación. "
                "Si el estado es EXONERADO, envía template de exoneración.",
)
async def enviar_calificacion(
    inscripcion_id: int,
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
    current_usuario: UsuarioRead = Depends(require_administrativo),
):
    try:
        resultado = v2_services.notificationService.notificar_calificacion(
            inscripcion_id, current_usuario.id, session
        )
        if not resultado["ok"]:
            raise HTTPException(status_code=502, detail=resultado.get("error", "Error al enviar email"))
        return {"message": "Notificación enviada correctamente"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/individual",
    summary="Enviar email individual a un estudiante",
    description="Envía un email libre (asunto y mensaje personalizado) a un estudiante.",
)
async def enviar_individual(
    body: EnvioIndividualRequest,
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
    current_usuario: UsuarioRead = Depends(require_administrativo),
):
    try:
        resultado = v2_services.notificationService.enviar_individual(
            body.usuario_id, body.asunto, body.mensaje, current_usuario.id, session
        )
        if not resultado["ok"]:
            raise HTTPException(status_code=502, detail=resultado.get("error", "Error al enviar email"))
        return {"message": "Email enviado correctamente"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/masivo",
    summary="Enviar email masivo a un grupo de estudiantes",
    description="Envía un email a todos los estudiantes que coincidan con el filtro. "
                "Filtros: programa_id (alumnos activos del programa) o "
                "instancia_cursado_id (alumnos cursando esa materia).",
)
async def enviar_masivo(
    body: EnvioMasivoRequest,
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
    current_usuario: UsuarioRead = Depends(require_administrativo),
):
    if not body.filtro.get("programa_id") and not body.filtro.get("instancia_cursado_id"):
        raise HTTPException(
            status_code=400,
            detail="Debe especificar al menos un filtro: programa_id o instancia_cursado_id",
        )

    resultado = v2_services.notificationService.enviar_masivo(
        body.filtro, body.asunto, body.mensaje, current_usuario.id, session
    )
    return resultado


@router.get(
    "/historial",
    summary="Historial de notificaciones enviadas",
    description="Retorna el log paginado de todas las notificaciones enviadas.",
)
async def get_historial(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    tipo: Optional[TipoNotificacion] = Query(default=None),
    usuario_id: Optional[int] = Query(default=None),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
    current_usuario: UsuarioRead = Depends(require_administrativo),
):
    return v2_services.notificationService.get_historial(
        session, page=page, per_page=per_page, tipo=tipo, usuario_id=usuario_id
    )
