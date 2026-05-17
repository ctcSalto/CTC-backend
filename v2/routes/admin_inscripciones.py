from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_docente_or_admin, require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.inscripcion_materia import (
    InscripcionMateriaRead,
    MarcarInasistenciaRequest,
    MarcarAbandonoRequest,
)

router = APIRouter(
    prefix="/v2/admin/inscripciones",
    tags=["v2 - Admin Inscripciones"],
)


class InscripcionManualRequest(BaseModel):
    usuario_id: int
    instancia_cursado_id: int


@router.post("/marcar-inasistencia", response_model=InscripcionMateriaRead)
async def marcar_inasistencia(
    data: MarcarInasistenciaRequest,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Marcar a un alumno como perdido por inasistencia"""
    try:
        return v2_services.inscripcionService.marcar_inasistencia(
            data.inscripcion_id, data.motivo, session
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/marcar-abandono", response_model=InscripcionMateriaRead)
async def marcar_abandono(
    data: MarcarAbandonoRequest,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Marcar a un alumno como abandono"""
    try:
        return v2_services.inscripcionService.marcar_abandono(
            data.inscripcion_id, data.motivo, session
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/escolaridad/{usuario_id}")
async def escolaridad_alumno(
    usuario_id: int,
    programa_id: int = Query(..., description="ID del programa"),
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Consultar escolaridad de cualquier alumno (admin/docente)"""
    return v2_services.inscripcionService.get_escolaridad(
        usuario_id, programa_id, session
    )


@router.post("/inscribir", response_model=InscripcionMateriaRead)
async def inscripcion_manual(
    data: InscripcionManualRequest,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Inscripcion manual por admin (salta validacion de periodo)"""
    try:
        return v2_services.inscripcionService.inscribir_materia(
            usuario_id=data.usuario_id,
            instancia_cursado_id=data.instancia_cursado_id,
            session=session,
            skip_periodo=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -- Verificacion de egreso --------------------------------------------------

@router.get("/verificar-egreso/{usuario_id}")
async def verificar_egreso(
    usuario_id: int,
    programa_id: int = Query(..., description="ID del programa"),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Verificar si un alumno cumple requisitos de egreso en un programa"""
    try:
        return v2_services.egresoService.verificar_egreso(
            usuario_id, programa_id, session
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -- Revalida ----------------------------------------------------------------

class RevalidarRequest(BaseModel):
    motivo: str


@router.post("/{inscripcion_id}/revalidar", response_model=InscripcionMateriaRead)
async def revalidar_materia(
    inscripcion_id: int,
    data: RevalidarRequest,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Revalidar (convalidar) una materia. Cambia estado a REVALIDADA, asigna creditos y registra motivo."""
    try:
        return v2_services.inscripcionService.revalidar_materia(
            inscripcion_id, data.motivo, session
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
