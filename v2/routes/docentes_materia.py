from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.docente_materia import (
    DocenteMateriaCreate,
    DocenteMateriaUpdate,
    DocenteMateriaRead,
)

router = APIRouter(
    prefix="/v2/admin/docentes-materia",
    tags=["v2 - Docentes por Materia"],
)


@router.post("", response_model=DocenteMateriaRead, status_code=status.HTTP_201_CREATED)
async def assign_docente(
    data: DocenteMateriaCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        return v2_services.docenteMateriaService.assign(data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/instancia-cursado/{instancia_cursado_id}", response_model=List[DocenteMateriaRead])
async def get_docentes_instancia_cursado(
    instancia_cursado_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Obtener docentes asignados a una instancia de cursado."""
    return v2_services.docenteMateriaService.get_by_instancia_cursado(
        instancia_cursado_id, session
    )


@router.put("/{asignacion_id}", response_model=DocenteMateriaRead)
async def update_asignacion(
    asignacion_id: int,
    data: DocenteMateriaUpdate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        return v2_services.docenteMateriaService.update(asignacion_id, data, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{asignacion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asignacion(
    asignacion_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        v2_services.docenteMateriaService.delete(asignacion_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
