from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.instancia_examen import (
    InstanciaExamenCreate,
    InstanciaExamenUpdate,
    InstanciaExamenRead,
    InstanciaExamen,
)
from v2.models.docente_instancia_examen import DocenteInstanciaExamenCreate, DocenteInstanciaExamenRead

router = APIRouter(
    prefix="/v2/admin/instancias-examen",
    tags=["v2 - Instancias de Examen"],
)


@router.post("/", response_model=InstanciaExamenRead, status_code=status.HTTP_201_CREATED)
async def crear_instancia_examen(
    data: InstanciaExamenCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    session: Session = Depends(get_session),
):
    """Crear una nueva instancia de examen para una materia."""
    instancia = InstanciaExamen(**data.model_dump(exclude_unset=True))
    session.add(instancia)
    session.flush()
    session.refresh(instancia)
    return instancia


@router.get("/materia/{materia_id}", response_model=List[InstanciaExamenRead])
async def listar_instancias_materia(
    materia_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Listar instancias de examen de una materia."""
    return v2_services.instanciaExamenService.get_instancias_materia(materia_id, session)


@router.get("/activas", response_model=List[InstanciaExamenRead])
async def listar_instancias_activas(
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Listar instancias con inscripción abierta."""
    return v2_services.instanciaExamenService.get_activas(session)


@router.get("/{instancia_id}", response_model=InstanciaExamenRead)
async def obtener_instancia_examen(
    instancia_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    session: Session = Depends(get_session),
):
    """Obtener detalle de una instancia de examen."""
    instancia = session.get(InstanciaExamen, instancia_id)
    if not instancia:
        raise HTTPException(status_code=404, detail="Instancia de examen no encontrada")
    return instancia


@router.put("/{instancia_id}", response_model=InstanciaExamenRead)
async def actualizar_instancia_examen(
    instancia_id: int,
    data: InstanciaExamenUpdate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    session: Session = Depends(get_session),
):
    """Actualizar una instancia de examen."""
    instancia = session.get(InstanciaExamen, instancia_id)
    if not instancia:
        raise HTTPException(status_code=404, detail="Instancia de examen no encontrada")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(instancia, key, value)
    session.flush()
    session.refresh(instancia)
    return instancia


@router.delete("/{instancia_id}")
async def eliminar_instancia_examen(
    instancia_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    session: Session = Depends(get_session),
):
    """Eliminar una instancia de examen."""
    instancia = session.get(InstanciaExamen, instancia_id)
    if not instancia:
        raise HTTPException(status_code=404, detail="Instancia de examen no encontrada")
    session.delete(instancia)
    session.flush()
    return {"ok": True, "detail": "Instancia de examen eliminada"}


@router.post("/{instancia_id}/profesores", response_model=DocenteInstanciaExamenRead)
async def asignar_profesor(
    instancia_id: int,
    data: DocenteInstanciaExamenCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Asignar un profesor a una instancia de examen."""
    try:
        return v2_services.instanciaExamenService.asignar_profesor(
            instancia_id, data.profesor_id, session
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{instancia_id}/inscriptos")
async def inscriptos_examen(
    instancia_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Lista de inscriptos a una instancia de examen."""
    return v2_services.inscripcionExamenService.get_examenes_instancia(
        instancia_id, session
    )
