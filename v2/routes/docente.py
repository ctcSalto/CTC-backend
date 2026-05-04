from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_docente_or_admin
from v2.models.usuario import UsuarioRead
from v2.models.calificacion import CalificacionRead, CalificacionBatchItem
from v2.models.docente_materia import DocenteMateria
from v2.models.inscripcion_materia import InscripcionMateria, InscripcionMateriaRead
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.equipo import EquipoCreate
from v2.models.inscripcion_examen import InscripcionExamenRead, CalificarExamenRequest

router = APIRouter(
    prefix="/v2/portal/docente",
    tags=["v2 - Portal Docente"],
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _validar_docente_instancia_cursado(docente_id: int, instancia_cursado_id: int, session: Session):
    """Valida que el docente esté asignado a la instancia de cursado."""
    asignacion = session.exec(
        select(DocenteMateria).where(
            DocenteMateria.docente_id == docente_id,
            DocenteMateria.instancia_cursado_id == instancia_cursado_id,
        )
    ).first()
    return asignacion is not None


def _validar_docente_materia(docente_id: int, materia_id: int, session: Session):
    """Valida que el docente esté asignado a alguna instancia de la materia."""
    asignacion = session.exec(
        select(DocenteMateria)
        .join(InstanciaCursado, DocenteMateria.instancia_cursado_id == InstanciaCursado.id)
        .where(
            DocenteMateria.docente_id == docente_id,
            InstanciaCursado.materia_id == materia_id,
        )
    ).first()
    return asignacion is not None


# ── Schemas ──────────────────────────────────────────────────────────────────

class CalificacionRequest(BaseModel):
    inscripcion_id: int
    instancia_evaluacion_id: int
    nota: Decimal
    equipo_id: Optional[int] = None
    observaciones: Optional[str] = None


class CalificacionBatchRequest(BaseModel):
    instancia_evaluacion_id: int
    calificaciones: List[CalificacionBatchItem]


class NotaFinalDirectaRequest(BaseModel):
    inscripcion_id: int
    nota: Decimal


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/mi-perfil")
async def mi_perfil(
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    session: Session = Depends(get_session),
):
    """Información del perfil del docente"""
    from v2.models.profesor import Profesor
    perfil_profesor = session.exec(
        select(Profesor).where(Profesor.usuario_id == current_usuario.id)
    ).first()

    return {
        **current_usuario.model_dump(),
        "perfil_profesor": {
            "profesor_id": perfil_profesor.id,
            "cargo": perfil_profesor.cargo.value if perfil_profesor.cargo else None,
            "dedicacion": perfil_profesor.dedicacion.value if perfil_profesor.dedicacion else None,
            "especialidad": perfil_profesor.especialidad,
        } if perfil_profesor else None,
    }


@router.get("/mis-programas")
async def mis_programas(
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    session: Session = Depends(get_session),
):
    """Programas donde el docente es coordinador"""
    from v2.models.profesor import Profesor
    from v2.models.programa import Programa
    from v2.models.materia import Materia

    profesor = session.exec(
        select(Profesor).where(Profesor.usuario_id == current_usuario.id)
    ).first()
    if not profesor:
        return []

    programas = session.exec(
        select(Programa).where(Programa.coordinador_id == profesor.id)
    ).all()

    resultado = []
    for prog in programas:
        cant_materias = len(list(session.exec(
            select(Materia).where(Materia.programa_id == prog.id)
        ).all()))
        resultado.append({
            "programa_id": prog.id,
            "nombre": prog.nombre,
            "tipo": prog.tipo.value,
            "area": prog.area.value if prog.area else None,
            "cantidad_materias": cant_materias,
        })
    return resultado


@router.get("/mis-materias")
async def mis_materias(
    anio_lectivo: int = Query(..., description="Año lectivo"),
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    session: Session = Depends(get_session),
):
    """Materias asignadas al docente en un año lectivo (via instancias de cursado)"""
    from v2.models.materia import Materia

    asignaciones = session.exec(
        select(DocenteMateria)
        .join(InstanciaCursado, DocenteMateria.instancia_cursado_id == InstanciaCursado.id)
        .where(
            DocenteMateria.docente_id == current_usuario.id,
            InstanciaCursado.anio_lectivo == anio_lectivo,
        )
    ).all()

    resultado = []
    for a in asignaciones:
        ic = session.get(InstanciaCursado, a.instancia_cursado_id)
        if not ic:
            continue
        materia = session.get(Materia, ic.materia_id)
        if materia:
            resultado.append({
                "asignacion_id": a.id,
                "instancia_cursado_id": ic.id,
                "materia_id": materia.id,
                "nombre": materia.nombre,
                "codigo": materia.codigo,
                "semestre": materia.semestre,
                "anio_lectivo": ic.anio_lectivo,
                "salon": ic.salon,
                "horario": ic.horario,
                "estado": ic.estado.value,
                "rol_docente": a.rol_docente.value,
            })

    return resultado


@router.get("/instancia-cursado/{instancia_cursado_id}/alumnos")
async def alumnos_instancia(
    instancia_cursado_id: int,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    session: Session = Depends(get_session),
):
    """Lista de alumnos inscriptos en una instancia de cursado"""
    from v2.models.enums import RolUsuario
    from v2.models.usuario import Usuario

    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_instancia_cursado(current_usuario.id, instancia_cursado_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta instancia de cursado")

    inscripciones = session.exec(
        select(InscripcionMateria).where(
            InscripcionMateria.instancia_cursado_id == instancia_cursado_id,
        )
    ).all()

    resultado = []
    for insc in inscripciones:
        usuario = session.exec(
            select(Usuario).where(Usuario.id == insc.usuario_id)
        ).first()
        resultado.append({
            "inscripcion_id": insc.id,
            "usuario_id": insc.usuario_id,
            "nombre": usuario.nombre if usuario else "",
            "apellido": usuario.apellido if usuario else "",
            "estado": insc.estado.value,
            "nota_curso": float(insc.nota_curso) if insc.nota_curso else None,
        })

    return resultado


@router.get("/instancia-cursado/{instancia_cursado_id}/detalle")
async def detalle_instancia(
    instancia_cursado_id: int,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Detalle completo de una instancia de cursado (info, alumnos, evaluaciones)"""
    from v2.models.enums import RolUsuario
    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_instancia_cursado(current_usuario.id, instancia_cursado_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta instancia de cursado")

    try:
        return v2_services.instanciaCursadoService.get_detalle_completo(instancia_cursado_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/instancia-cursado/{instancia_cursado_id}/resultados")
async def resultados_instancia(
    instancia_cursado_id: int,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Tabla completa de resultados (acta de cursado) para el frontend"""
    from v2.models.enums import RolUsuario
    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_instancia_cursado(current_usuario.id, instancia_cursado_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta instancia de cursado")

    try:
        return v2_services.instanciaCursadoService.get_resultados(instancia_cursado_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/instancia-cursado/{instancia_cursado_id}/estadisticas")
async def estadisticas_instancia(
    instancia_cursado_id: int,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Estadísticas de aprobación/asistencia de una instancia de cursado"""
    from v2.models.enums import RolUsuario
    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_instancia_cursado(current_usuario.id, instancia_cursado_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta instancia de cursado")

    try:
        instancia = v2_services.instanciaCursadoService.actualizar_estadisticas(instancia_cursado_id, session)
        return instancia.estadisticas
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/instancia-cursado/{instancia_cursado_id}/calificaciones")
async def calificaciones_instancia(
    instancia_cursado_id: int,
    instancia_evaluacion_id: int = Query(..., description="ID de la instancia de evaluación"),
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Notas de todos los alumnos en una instancia de evaluación específica"""
    from v2.models.enums import RolUsuario
    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_instancia_cursado(current_usuario.id, instancia_cursado_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta instancia de cursado")

    return v2_services.calificacionService.get_calificaciones_instancia_cursado(
        instancia_cursado_id, instancia_evaluacion_id, session
    )


@router.post("/instancia-cursado/{instancia_cursado_id}/calificaciones", response_model=CalificacionRead)
async def cargar_calificacion(
    instancia_cursado_id: int,
    data: CalificacionRequest,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Cargar nota individual"""
    from v2.models.enums import RolUsuario
    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_instancia_cursado(current_usuario.id, instancia_cursado_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta instancia de cursado")

    try:
        return v2_services.calificacionService.guardar_calificacion(
            docente_id=current_usuario.id,
            inscripcion_id=data.inscripcion_id,
            instancia_evaluacion_id=data.instancia_evaluacion_id,
            nota=data.nota,
            session=session,
            equipo_id=data.equipo_id,
            observaciones=data.observaciones,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/instancia-cursado/{instancia_cursado_id}/calificaciones/batch")
async def cargar_calificaciones_batch(
    instancia_cursado_id: int,
    data: CalificacionBatchRequest,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Carga masiva de notas para una instancia"""
    from v2.models.enums import RolUsuario
    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_instancia_cursado(current_usuario.id, instancia_cursado_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta instancia de cursado")

    return v2_services.calificacionService.guardar_batch(
        docente_id=current_usuario.id,
        instancia_evaluacion_id=data.instancia_evaluacion_id,
        calificaciones=data.calificaciones,
        session=session,
    )


@router.post("/instancia-cursado/{instancia_cursado_id}/nota-final-directa", response_model=InscripcionMateriaRead)
async def cargar_nota_final_directa(
    instancia_cursado_id: int,
    data: NotaFinalDirectaRequest,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Cargar nota final ya promediada directamente (sin parciales)"""
    from v2.models.enums import RolUsuario
    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_instancia_cursado(current_usuario.id, instancia_cursado_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta instancia de cursado")

    try:
        return v2_services.calificacionService.cargar_nota_final_directa(
            docente_id=current_usuario.id,
            inscripcion_id=data.inscripcion_id,
            nota=data.nota,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/instancia-cursado/{instancia_cursado_id}/equipos")
async def equipos_instancia(
    instancia_cursado_id: int,
    instancia_evaluacion_id: int = Query(..., description="ID de la instancia grupal"),
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Equipos de una instancia de evaluación grupal"""
    return v2_services.equipoService.get_equipos_instancia(instancia_evaluacion_id, session)


@router.post("/instancia-cursado/{instancia_cursado_id}/equipos")
async def crear_equipo(
    instancia_cursado_id: int,
    data: EquipoCreate,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Crear equipo para instancia grupal"""
    try:
        equipo = v2_services.equipoService.create_equipo(
            instancia_evaluacion_id=data.instancia_evaluacion_id,
            nombre=data.nombre,
            miembros_ids=data.miembros_ids,
            session=session,
        )
        return {"id": equipo.id, "nombre": equipo.nombre, "instancia_evaluacion_id": equipo.instancia_evaluacion_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/instancia-cursado/{instancia_cursado_id}/equipos/{equipo_id}", status_code=204)
async def eliminar_equipo(
    instancia_cursado_id: int,
    equipo_id: int,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Eliminar equipo"""
    try:
        v2_services.equipoService.delete_equipo(equipo_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -- Faltas --------------------------------------------------------------------

class FaltaRequest(BaseModel):
    inscripcion_id: int


@router.post("/instancia-cursado/{instancia_cursado_id}/faltas", response_model=InscripcionMateriaRead)
async def registrar_falta(
    instancia_cursado_id: int,
    data: FaltaRequest,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Registrar una falta a un alumno"""
    from v2.models.enums import RolUsuario
    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_instancia_cursado(current_usuario.id, instancia_cursado_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta instancia de cursado")

    try:
        return v2_services.inscripcionService.registrar_falta(data.inscripcion_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/instancia-cursado/{instancia_cursado_id}/faltas", response_model=InscripcionMateriaRead)
async def quitar_falta(
    instancia_cursado_id: int,
    data: FaltaRequest,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Quitar una falta a un alumno"""
    from v2.models.enums import RolUsuario
    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_instancia_cursado(current_usuario.id, instancia_cursado_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta instancia de cursado")

    try:
        return v2_services.inscripcionService.quitar_falta(data.inscripcion_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -- Examenes ------------------------------------------------------------------

@router.get("/materia/{materia_id}/examenes")
async def examenes_materia(
    materia_id: int,
    instancia_examen_id: int = Query(..., description="ID de la instancia de examen"),
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Lista de inscriptos a examen en una materia para una instancia de examen"""
    from v2.models.enums import RolUsuario
    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_materia(current_usuario.id, materia_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta materia")

    return v2_services.inscripcionExamenService.get_examenes_instancia(
        instancia_examen_id=instancia_examen_id,
        session=session,
    )


@router.post("/materia/{materia_id}/examenes/{inscripcion_examen_id}/calificar", response_model=InscripcionExamenRead)
async def calificar_examen_docente(
    materia_id: int,
    inscripcion_examen_id: int,
    data: CalificarExamenRequest,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Calificar un examen (docente o admin)"""
    from v2.models.enums import RolUsuario
    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_materia(current_usuario.id, materia_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta materia")

    try:
        return v2_services.inscripcionExamenService.calificar_examen(
            inscripcion_examen_id=inscripcion_examen_id,
            nota_examen=data.nota_examen,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/materia/{materia_id}/examenes/{inscripcion_examen_id}/ausente", response_model=InscripcionExamenRead)
async def marcar_ausente_docente(
    materia_id: int,
    inscripcion_examen_id: int,
    current_usuario: UsuarioRead = Depends(require_docente_or_admin),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Marcar como ausente (docente o admin)"""
    from v2.models.enums import RolUsuario
    if current_usuario.rol != RolUsuario.ADMINISTRATIVO:
        if not _validar_docente_materia(current_usuario.id, materia_id, session):
            raise HTTPException(status_code=403, detail="No esta asignado a esta materia")

    try:
        return v2_services.inscripcionExamenService.marcar_ausente(
            inscripcion_examen_id=inscripcion_examen_id,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
