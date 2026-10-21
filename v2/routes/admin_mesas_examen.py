"""
Mesas de examen: el periodo contra el que se cuenta el tope de examenes.

Un alumno no puede anotarse a mas de N examenes de la misma mesa. Antes el
periodo se infería del mes calendario de la fecha del examen, lo que contaba mal
en dos casos: una mesa que cruza fin de mes y dos mesas dentro de un mismo mes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session
from typing import Optional

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.mesa_examen import (
    MesaExamenCreate, MesaExamenUpdate, MesaExamenRead,
)

router = APIRouter(
    prefix="/v2/admin/mesas-examen",
    tags=["v2 - Admin Mesas de Examen"],
)


@router.post(
    "",
    response_model=MesaExamenRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una mesa de examen",
    description="La ventana de inscripcion que se cargue aca se copia a los "
                "examenes que se creen dentro de la mesa, para no repetirla en "
                "cada uno. `max_examenes` en null usa el tope general.",
)
async def crear_mesa(
    data: MesaExamenCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        return v2_services.mesaExamenService.crear(data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "",
    summary="Listar mesas de examen",
    description="Con la cantidad de examenes asignados a cada una.",
)
async def listar_mesas(
    anio_lectivo: Optional[int] = Query(default=None, description="Filtra por año"),
    incluir_inactivas: bool = Query(default=False),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return v2_services.mesaExamenService.listar(
        session, anio_lectivo=anio_lectivo, incluir_inactivas=incluir_inactivas
    )


@router.get("/{mesa_id}", response_model=MesaExamenRead)
async def obtener_mesa(
    mesa_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    mesa = v2_services.mesaExamenService.get_by_id(mesa_id, session)
    if not mesa:
        raise HTTPException(status_code=404, detail="Mesa de examen no encontrada")
    return mesa


@router.put(
    "/{mesa_id}",
    response_model=MesaExamenRead,
    summary="Actualizar una mesa",
    description="Cambiar la ventana NO reescribe la de los examenes ya creados: "
                "esa copia se hace al crear cada examen.",
)
async def actualizar_mesa(
    mesa_id: int,
    data: MesaExamenUpdate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        return v2_services.mesaExamenService.actualizar(mesa_id, data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{mesa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar una mesa",
    description="Solo si no tiene examenes asignados. Para dar de baja una mesa "
                "con examenes, marcala como inactiva.",
)
async def eliminar_mesa(
    mesa_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        v2_services.mesaExamenService.eliminar(mesa_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
