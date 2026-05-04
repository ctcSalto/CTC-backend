from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.instancia_cursado import (
    InstanciaCursadoCreate,
    InstanciaCursadoUpdate,
    InstanciaCursadoRead,
)

router = APIRouter(
    prefix="/v2/admin/instancias-cursado",
    tags=["v2 - Instancias de Cursado"],
)


@router.post("/", response_model=InstanciaCursadoRead)
async def crear_instancia_cursado(
    data: InstanciaCursadoCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Crear una nueva instancia de cursado para una materia en un año lectivo."""
    from v2.models.instancia_cursado import InstanciaCursado
    instancia = InstanciaCursado(**data.model_dump(exclude_unset=True))
    session.add(instancia)
    session.flush()
    session.refresh(instancia)
    return instancia


@router.get("/", response_model=List[InstanciaCursadoRead])
async def listar_instancias_cursado(
    materia_id: int = None,
    anio_lectivo: int = None,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Listar instancias de cursado con filtros opcionales."""
    from sqlmodel import select
    from v2.models.instancia_cursado import InstanciaCursado
    query = select(InstanciaCursado)
    if materia_id:
        query = query.where(InstanciaCursado.materia_id == materia_id)
    if anio_lectivo:
        query = query.where(InstanciaCursado.anio_lectivo == anio_lectivo)
    return list(session.exec(query).all())


@router.get("/{instancia_id}", response_model=InstanciaCursadoRead)
async def obtener_instancia_cursado(
    instancia_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    session: Session = Depends(get_session),
):
    """Obtener detalle de una instancia de cursado."""
    from v2.models.instancia_cursado import InstanciaCursado
    instancia = session.get(InstanciaCursado, instancia_id)
    if not instancia:
        raise HTTPException(status_code=404, detail="Instancia de cursado no encontrada")
    return instancia


@router.put("/{instancia_id}", response_model=InstanciaCursadoRead)
async def actualizar_instancia_cursado(
    instancia_id: int,
    data: InstanciaCursadoUpdate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    session: Session = Depends(get_session),
):
    """Actualizar una instancia de cursado."""
    from v2.models.instancia_cursado import InstanciaCursado
    instancia = session.get(InstanciaCursado, instancia_id)
    if not instancia:
        raise HTTPException(status_code=404, detail="Instancia de cursado no encontrada")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(instancia, key, value)
    session.flush()
    session.refresh(instancia)
    return instancia


@router.delete("/{instancia_id}")
async def eliminar_instancia_cursado(
    instancia_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    session: Session = Depends(get_session),
):
    """Eliminar una instancia de cursado."""
    from v2.models.instancia_cursado import InstanciaCursado
    instancia = session.get(InstanciaCursado, instancia_id)
    if not instancia:
        raise HTTPException(status_code=404, detail="Instancia de cursado no encontrada")
    session.delete(instancia)
    session.flush()
    return {"ok": True, "detail": "Instancia de cursado eliminada"}
