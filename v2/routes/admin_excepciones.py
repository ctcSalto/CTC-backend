"""
Excepciones de previatura: bedelia habilita a un alumno a cursar una materia sin
tener aprobada una previatura puntual.

La excepcion habilita la INSCRIPCION y nada mas. La aprobacion que el alumno
consiga cursando bajo excepcion no habilita la materia siguiente mientras la
previatura original siga sin aprobar; el dia que la apruebe, la cadena se
completa y la siguiente se habilita sola.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session
from typing import Optional

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.excepcion_previatura import (
    ExcepcionPreviaturaCreate,
    ExcepcionPreviaturaRevocar,
    ExcepcionPreviaturaRead,
)

router = APIRouter(
    prefix="/v2/admin/excepciones-previatura",
    tags=["v2 - Admin Excepciones de Previatura"],
)


@router.post(
    "",
    response_model=ExcepcionPreviaturaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Otorgar una excepcion de previatura",
    description="Habilita a un alumno a cursar una materia sin tener aprobada una "
                "previatura puntual, solo para el anio lectivo indicado. El motivo "
                "es obligatorio y queda registrado junto con quien la otorgo.",
)
async def otorgar_excepcion(
    data: ExcepcionPreviaturaCreate,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        return v2_services.excepcionPreviaturaService.otorgar(
            data, otorgada_por_id=current_usuario.id, session=session
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{excepcion_id}/revocar",
    response_model=ExcepcionPreviaturaRead,
    summary="Revocar una excepcion",
    description="Da de baja la excepcion. No afecta a las inscripciones ya hechas "
                "al amparo de ella: lo que deja de valer es la habilitacion para "
                "inscribirse de nuevo.",
)
async def revocar_excepcion(
    excepcion_id: int,
    data: ExcepcionPreviaturaRevocar,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        return v2_services.excepcionPreviaturaService.revocar(
            excepcion_id, data.motivo, current_usuario.id, session
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/alumno/{alumno_id}",
    summary="Excepciones de un alumno",
    description="Con los nombres de la materia y de la materia previa resueltos.",
)
async def excepciones_de_alumno(
    alumno_id: int,
    anio_lectivo: Optional[int] = Query(
        default=None, description="Filtra por año lectivo"
    ),
    incluir_revocadas: bool = Query(
        default=False, description="Incluye las dadas de baja, para auditoría"
    ),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return v2_services.excepcionPreviaturaService.listar_de_alumno(
        alumno_id, session,
        anio_lectivo=anio_lectivo,
        incluir_revocadas=incluir_revocadas,
    )
