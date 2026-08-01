"""
Instancias de evaluacion de una cursada (parciales, obligatorio, nota de clase).

Las define el docente de la cursada en cada semestre, y bedelia tambien puede.
Antes todas las rutas eran solo para administrativo, asi que el profesor no podia
cargar las evaluaciones de sus propios cursos.

El prefijo sigue siendo /v2/admin/... por compatibilidad con lo que ya esta
integrando el frontend; el rol requerido es lo que cambio.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List

from database.database import get_session
from database.services.filter.filters import Filter
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo, require_docente_or_admin
from v2.models.usuario import UsuarioRead
from v2.models.enums import RolUsuario
from v2.models.materia_instancia_evaluacion import (
    InstanciaEvaluacionCreate,
    InstanciaEvaluacionUpdate,
    InstanciaEvaluacionRead,
)

router = APIRouter(
    prefix="/v2/admin/instancias-evaluacion",
    tags=["v2 - Instancias de Evaluacion"],
)


def _validar_acceso_a_cursada(
    current_usuario: UsuarioRead,
    instancia_cursado_id: int,
    v2_services: V2Services,
    session: Session,
) -> None:
    """
    Bedelia entra a cualquier cursada; el docente solo a las que dicta.

    Sin este chequeo, abrir las rutas al rol docente dejaria que cualquier
    profesor editara las evaluaciones de materias ajenas.
    """
    if current_usuario.rol == RolUsuario.ADMINISTRATIVO:
        return
    if not v2_services.docenteMateriaService.docente_asignado_a_cursada(
        current_usuario.id, instancia_cursado_id, session
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No esta asignado a esta instancia de cursado",
        )


def _cursada_de_la_evaluacion(
    instancia_id: int, v2_services: V2Services, session: Session
) -> int:
    """Resuelve a que cursada pertenece una evaluacion, para poder validar acceso."""
    instancia = v2_services.instanciaEvaluacionService.get_by_id(instancia_id, session)
    if not instancia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instancia de evaluacion {instancia_id} no encontrada",
        )
    return instancia.instancia_cursado_id


@router.post("", response_model=InstanciaEvaluacionRead, status_code=status.HTTP_201_CREATED)
async def create_instancia(
    data: InstanciaEvaluacionCreate,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """
    Crear una instancia de evaluacion (parcial, obligatorio, nota de clase) de una
    cursada. La suma de pesos no puede superar la nota maxima de la politica.
    """
    _validar_acceso_a_cursada(
        current_usuario, data.instancia_cursado_id, v2_services, session
    )
    try:
        return v2_services.instanciaEvaluacionService.create(data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/instancia-cursado/{instancia_cursado_id}", response_model=List[InstanciaEvaluacionRead])
async def get_instancias_by_instancia_cursado(
    instancia_cursado_id: int,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Obtener instancias de evaluación de una instancia de cursado."""
    _validar_acceso_a_cursada(
        current_usuario, instancia_cursado_id, v2_services, session
    )
    return v2_services.instanciaEvaluacionService.get_by_instancia_cursado(
        instancia_cursado_id, session
    )


@router.post("/filters")
async def filter_instancias(
    filters: Filter,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """
    Buscar instancias de evaluacion con filtros avanzados.

    Queda solo para administrativo: es una consulta libre sobre todas las
    cursadas y no hay forma de acotarla a las del docente que la llama.
    """
    return v2_services.instanciaEvaluacionService.get_with_filters_clean(session, filters)


@router.put("/{instancia_id}", response_model=InstanciaEvaluacionRead)
async def update_instancia(
    instancia_id: int,
    data: InstanciaEvaluacionUpdate,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Actualizar una instancia de evaluacion (nombre, peso, orden, grupal)."""
    instancia_cursado_id = _cursada_de_la_evaluacion(instancia_id, v2_services, session)
    _validar_acceso_a_cursada(
        current_usuario, instancia_cursado_id, v2_services, session
    )
    try:
        return v2_services.instanciaEvaluacionService.update(instancia_id, data, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{instancia_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instancia(
    instancia_id: int,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Eliminar una instancia de evaluacion. Falla si tiene calificaciones registradas."""
    instancia_cursado_id = _cursada_de_la_evaluacion(instancia_id, v2_services, session)
    _validar_acceso_a_cursada(
        current_usuario, instancia_cursado_id, v2_services, session
    )
    try:
        v2_services.instanciaEvaluacionService.delete(instancia_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
