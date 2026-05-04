from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.inscripcion_examen import InscripcionExamenCreate, InscripcionExamenRead, CalificarExamenRequest

router = APIRouter(
    prefix="/v2/admin/examenes",
    tags=["v2 - Administracion de Examenes"],
)


# -- Inscripcion manual (admin) -----------------------------------------------

@router.post("/inscribir", response_model=InscripcionExamenRead, status_code=status.HTTP_201_CREATED)
async def inscribir_examen_admin(
    data: InscripcionExamenCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Inscribir a un estudiante a examen (admin, sin validar periodo activo)"""
    try:
        return v2_services.inscripcionExamenService.inscribir_examen(
            inscripcion_materia_id=data.inscripcion_materia_id,
            instancia_examen_id=data.instancia_examen_id,
            session=session,
            bypass_periodo=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -- Calificar examen ---------------------------------------------------------

@router.post("/{inscripcion_examen_id}/calificar", response_model=InscripcionExamenRead)
async def calificar_examen(
    inscripcion_examen_id: int,
    data: CalificarExamenRequest,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Calificar un examen. Actualiza estado inscripcion materia automaticamente."""
    try:
        return v2_services.inscripcionExamenService.calificar_examen(
            inscripcion_examen_id=inscripcion_examen_id,
            nota_examen=data.nota_examen,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -- Marcar ausente -----------------------------------------------------------

@router.post("/{inscripcion_examen_id}/ausente", response_model=InscripcionExamenRead)
async def marcar_ausente(
    inscripcion_examen_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Marcar como ausente. La materia queda en A_EXAMEN."""
    try:
        return v2_services.inscripcionExamenService.marcar_ausente(
            inscripcion_examen_id=inscripcion_examen_id,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -- Listar examenes de una instancia -----------------------------------------

@router.get("/instancia/{instancia_examen_id}")
async def examenes_instancia(
    instancia_examen_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Lista de inscripciones a examen de una instancia de examen"""
    return v2_services.inscripcionExamenService.get_examenes_instancia(
        instancia_examen_id=instancia_examen_id,
        session=session,
    )


# -- Desinscribir (admin) -----------------------------------------------------

@router.delete("/{inscripcion_examen_id}", status_code=status.HTTP_204_NO_CONTENT)
async def desinscribir_examen(
    inscripcion_examen_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Desinscribir de examen (solo si esta en estado INSCRIPTO)"""
    try:
        v2_services.inscripcionExamenService.desinscribir_examen(
            inscripcion_examen_id=inscripcion_examen_id,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
