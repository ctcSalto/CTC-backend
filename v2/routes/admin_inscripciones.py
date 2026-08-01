from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from pydantic import BaseModel, Field
from typing import Optional

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_docente_or_admin, require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.inscripcion_materia import (
    InscripcionMateriaRead,
    MarcarInasistenciaRequest,
    MarcarAbandonoRequest,
    EscolaridadRead,
)

router = APIRouter(
    prefix="/v2/admin/inscripciones",
    tags=["v2 - Admin Inscripciones"],
)


class InscripcionManualRequest(BaseModel):
    alumno_id: int
    instancia_cursado_id: int


class BajaProgramaRequest(BaseModel):
    motivo: str = Field(min_length=1, max_length=255)
    cerrar_materias: bool = Field(
        default=True,
        description="Cierra como abandono las materias EN CURSO del alumno en ese "
                    "programa. Desactivar solo si la baja no implica soltar las cursadas",
    )


class BajaProgramaResponse(BaseModel):
    inscripcion_programa_id: int
    alumno_id: int
    programa_id: int
    estado: str
    fecha_baja: Optional[str] = None
    motivo_baja: Optional[str] = None
    materias_cerradas: int


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


@router.get("/escolaridad/{alumno_id}", response_model=EscolaridadRead)
async def escolaridad_alumno(
    alumno_id: int,
    programa_id: int = Query(..., description="ID del programa"),
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Consultar escolaridad de cualquier alumno (admin/docente)"""
    return v2_services.inscripcionService.get_escolaridad(
        alumno_id, programa_id, session
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
            alumno_id=data.alumno_id,
            instancia_cursado_id=data.instancia_cursado_id,
            session=session,
            skip_periodo=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -- Baja de programa ---------------------------------------------------------

@router.post(
    "/programa/{inscripcion_programa_id}/baja",
    response_model=BajaProgramaResponse,
    summary="Dar de baja a un alumno de un programa",
    description="Registra la baja con fecha y motivo. Por defecto cierra tambien "
                "las materias que el alumno tenga EN CURSO en ese programa, "
                "dejandolas en abandono. Las materias de otros programas no se "
                "tocan. Envia notificacion al alumno (best-effort).",
)
async def dar_de_baja_programa(
    inscripcion_programa_id: int,
    data: BajaProgramaRequest,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    try:
        inscripcion = v2_services.inscripcionProgramaService.dar_de_baja(
            inscripcion_id=inscripcion_programa_id,
            motivo=data.motivo,
            session=session,
            cerrar_materias=data.cerrar_materias,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return BajaProgramaResponse(
        inscripcion_programa_id=inscripcion.id,
        alumno_id=inscripcion.alumno_id,
        programa_id=inscripcion.programa_id,
        estado=inscripcion.estado.value,
        fecha_baja=inscripcion.fecha_baja.isoformat() if inscripcion.fecha_baja else None,
        motivo_baja=inscripcion.motivo_baja,
        materias_cerradas=getattr(inscripcion, "materias_cerradas", 0),
    )


# -- Verificacion de egreso --------------------------------------------------

@router.get("/verificar-egreso/{alumno_id}")
async def verificar_egreso(
    alumno_id: int,
    programa_id: int = Query(..., description="ID del programa"),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Verificar si un alumno cumple requisitos de egreso en un programa"""
    try:
        return v2_services.egresoService.verificar_egreso(
            alumno_id, programa_id, session
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
