from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_estudiante, get_current_alumno
from v2.models.alumno import Alumno
from v2.models.usuario import UsuarioRead
from v2.models.inscripcion_materia import InscripcionMateriaRead
from v2.models.calificacion import CalificacionRead
from v2.models.inscripcion_examen import InscripcionExamenRead
from v2.models.documento_usuario import DocumentoUsuarioRead
from v2.models.enums import TipoDocumento

router = APIRouter(
    prefix="/v2/portal/estudiante",
    tags=["v2 - Portal Estudiante"],
)


class InscribirseRequest(BaseModel):
    instancia_cursado_id: int


# -- Perfil y programas -------------------------------------------------------

@router.get("/mi-perfil")
async def mi_perfil(
    current_usuario: UsuarioRead = Depends(require_estudiante),
    session: Session = Depends(get_session),
):
    """Información del perfil del estudiante"""
    from v2.models.alumno import Alumno
    perfil_alumno = session.exec(
        select(Alumno).where(Alumno.usuario_id == current_usuario.id)
    ).first()

    return {
        **current_usuario.model_dump(),
        "perfil_alumno": {
            "alumno_id": perfil_alumno.id,
            "fecha_ingreso": perfil_alumno.fecha_ingreso.isoformat() if perfil_alumno.fecha_ingreso else None,
        } if perfil_alumno else None,
    }


@router.get("/mis-programas")
async def mis_programas(
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Programas a los que el estudiante está inscripto"""
    from v2.models.programa import Programa
    inscripciones = v2_services.inscripcionProgramaService.get_programas_alumno(alumno.id, session)
    resultado = []
    for insc in inscripciones:
        programa = session.get(Programa, insc.programa_id)
        resultado.append({
            "inscripcion_id": insc.id,
            "programa_id": insc.programa_id,
            "nombre": programa.nombre if programa else "",
            "tipo": programa.tipo.value if programa else "",
            "area": programa.area.value if programa and programa.area else None,
            "estado": insc.estado.value,
            "anio_ingreso": insc.anio_ingreso,
            "fecha_inscripcion": insc.fecha_inscripcion.isoformat(),
        })
    return resultado


@router.get("/programa/{programa_id}")
async def ver_programa(
    programa_id: int,
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Ver info de un programa al que está inscripto (con materias)"""
    from v2.models.inscripcion_programa import InscripcionPrograma
    from v2.models.enums import EstadoInscripcionPrograma

    inscripcion = session.exec(
        select(InscripcionPrograma).where(
            InscripcionPrograma.alumno_id == alumno.id,
            InscripcionPrograma.programa_id == programa_id,
            InscripcionPrograma.estado == EstadoInscripcionPrograma.ACTIVA,
        )
    ).first()
    if not inscripcion:
        raise HTTPException(status_code=403, detail="No estas inscripto en este programa")

    programa = v2_services.programaService.get_con_materias(programa_id, session)
    if not programa:
        raise HTTPException(status_code=404, detail="Programa no encontrado")
    return programa


@router.get("/programa/{programa_id}/previaturas")
async def mapa_previaturas(
    programa_id: int,
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Mapa de previaturas con estado del alumno en cada materia"""
    return v2_services.inscripcionService.get_mapa_previaturas(
        alumno.id, programa_id, session
    )


# -- Materias ------------------------------------------------------------------

@router.get("/mis-materias")
async def mis_materias(
    anio_lectivo: int = Query(..., description="Año lectivo"),
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Materias inscriptas del estudiante en un año lectivo"""
    return v2_services.inscripcionService.get_mis_materias(
        alumno.id, anio_lectivo, session
    )


@router.get("/mi-materia/{inscripcion_id}")
async def mi_materia_detalle(
    inscripcion_id: int,
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Detalle completo de una materia (notas, faltas, estado)"""
    try:
        return v2_services.inscripcionService.get_detalle_materia(
            inscripcion_id, alumno.id, session
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/mi-escolaridad")
async def mi_escolaridad(
    programa_id: int = Query(..., description="ID del programa"),
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Vista de escolaridad completa del estudiante en un programa"""
    return v2_services.inscripcionService.get_escolaridad(
        alumno.id, programa_id, session
    )


@router.get("/materias-disponibles")
async def materias_disponibles(
    programa_id: int = Query(..., description="ID del programa"),
    anio_lectivo: int = Query(..., description="Anio lectivo"),
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Materias a las que el estudiante puede inscribirse"""
    return v2_services.inscripcionService.get_materias_disponibles(
        alumno.id, programa_id, anio_lectivo, session
    )


@router.post("/inscribirse-materia", response_model=InscripcionMateriaRead)
async def inscribirse_materia(
    data: InscribirseRequest,
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Inscribirse a una materia via instancia de cursado (valida previaturas y periodo activo)"""
    try:
        return v2_services.inscripcionService.inscribir_materia(
            alumno_id=alumno.id,
            instancia_cursado_id=data.instancia_cursado_id,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/mis-calificaciones/{inscripcion_id}")
async def mis_calificaciones(
    inscripcion_id: int,
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Calificaciones del estudiante en una inscripción"""
    from v2.models.inscripcion_materia import InscripcionMateria
    inscripcion = session.get(InscripcionMateria, inscripcion_id)
    if not inscripcion:
        raise HTTPException(status_code=404, detail="Inscripcion no encontrada")
    if inscripcion.alumno_id != alumno.id:
        raise HTTPException(status_code=403, detail="No es tu inscripcion")

    calificaciones = v2_services.calificacionService.get_calificaciones_inscripcion(
        inscripcion_id, session
    )
    return [CalificacionRead.model_validate(c) for c in calificaciones]


# -- Examenes ------------------------------------------------------------------

class InscribirseExamenRequest(BaseModel):
    inscripcion_materia_id: int
    instancia_examen_id: int


@router.post("/inscribirse-examen", response_model=InscripcionExamenRead, status_code=201)
async def inscribirse_examen(
    data: InscribirseExamenRequest,
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Inscribirse a un examen (valida periodo activo y estado A_EXAMEN)"""
    from v2.models.inscripcion_materia import InscripcionMateria
    inscripcion = session.get(InscripcionMateria, data.inscripcion_materia_id)
    if not inscripcion:
        raise HTTPException(status_code=404, detail="Inscripcion a materia no encontrada")
    if inscripcion.alumno_id != alumno.id:
        raise HTTPException(status_code=403, detail="No es tu inscripcion")

    try:
        return v2_services.inscripcionExamenService.inscribir_examen(
            inscripcion_materia_id=data.inscripcion_materia_id,
            instancia_examen_id=data.instancia_examen_id,
            session=session,
            bypass_periodo=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/mis-examenes/{inscripcion_id}")
async def mis_examenes(
    inscripcion_id: int,
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Historial de examenes de una inscripcion a materia"""
    from v2.models.inscripcion_materia import InscripcionMateria
    inscripcion = session.get(InscripcionMateria, inscripcion_id)
    if not inscripcion:
        raise HTTPException(status_code=404, detail="Inscripcion no encontrada")
    if inscripcion.alumno_id != alumno.id:
        raise HTTPException(status_code=403, detail="No es tu inscripcion")

    examenes = v2_services.inscripcionExamenService.get_examenes_estudiante(
        inscripcion_id, session
    )
    return [InscripcionExamenRead.model_validate(e) for e in examenes]


@router.delete("/desinscribir-examen/{inscripcion_examen_id}", status_code=204)
async def desinscribir_examen(
    inscripcion_examen_id: int,
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Desinscribirse de un examen (solo si esta en estado INSCRIPTO)"""
    ie = v2_services.inscripcionExamenService.get_by_id(inscripcion_examen_id, session)
    if not ie:
        raise HTTPException(status_code=404, detail="Inscripcion a examen no encontrada")

    from v2.models.inscripcion_materia import InscripcionMateria
    inscripcion = session.get(InscripcionMateria, ie.inscripcion_materia_id)
    if not inscripcion or inscripcion.alumno_id != alumno.id:
        raise HTTPException(status_code=403, detail="No es tu inscripcion")

    try:
        v2_services.inscripcionExamenService.desinscribir_examen(
            inscripcion_examen_id, session
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/desinscribir-materia/{inscripcion_id}", status_code=204)
async def desinscribir_materia(
    inscripcion_id: int,
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Desinscribirse de una materia (solo si está CURSANDO y dentro de período activo)"""
    try:
        v2_services.inscripcionService.desinscribir_materia(
            inscripcion_id, alumno.id, session
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/examenes-disponibles")
async def examenes_disponibles(
    programa_id: int = Query(..., description="ID del programa"),
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Instancias de examen disponibles para el alumno (materias en estado A_EXAMEN, inscripción abierta)"""
    from v2.models.inscripcion_materia import InscripcionMateria
    from v2.models.instancia_cursado import InstanciaCursado
    from v2.models.instancia_examen import InstanciaExamen
    from v2.models.inscripcion_examen import InscripcionExamen
    from v2.models.materia import Materia
    from v2.models.enums import EstadoInscripcionMateria, EstadoInscripcionExamen
    from datetime import datetime
    import os
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(os.getenv('TIME_ZONE', 'America/Montevideo'))
    ahora = datetime.now(tz).replace(tzinfo=None)

    # Inscripciones en estado A_EXAMEN del alumno en materias del programa
    inscripciones = session.exec(
        select(InscripcionMateria, InstanciaCursado, Materia)
        .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
        .join(Materia, InstanciaCursado.materia_id == Materia.id)
        .where(
            InscripcionMateria.alumno_id == alumno.id,
            InscripcionMateria.estado == EstadoInscripcionMateria.A_EXAMEN,
            Materia.programa_id == programa_id,
        )
    ).all()

    resultado = []
    for insc, ic, materia in inscripciones:
        # Buscar instancias de examen abiertas para esta materia
        instancias = session.exec(
            select(InstanciaExamen).where(
                InstanciaExamen.materia_id == materia.id,
                InstanciaExamen.habilitado == True,
                InstanciaExamen.fecha_inicio_inscripcion <= ahora,
                InstanciaExamen.fecha_fin_inscripcion >= ahora,
            )
        ).all()

        for inst_ex in instancias:
            # Verificar si ya está inscripto
            ya_inscripto = session.exec(
                select(InscripcionExamen).where(
                    InscripcionExamen.inscripcion_materia_id == insc.id,
                    InscripcionExamen.instancia_examen_id == inst_ex.id,
                    InscripcionExamen.estado == EstadoInscripcionExamen.INSCRIPTO,
                )
            ).first()

            resultado.append({
                "instancia_examen_id": inst_ex.id,
                "inscripcion_materia_id": insc.id,
                "materia_id": materia.id,
                "materia_nombre": materia.nombre,
                "materia_codigo": materia.codigo,
                "nombre_examen": inst_ex.nombre,
                "fecha_examen": inst_ex.fecha_examen.isoformat() if inst_ex.fecha_examen else None,
                "hora": inst_ex.hora,
                "salon": inst_ex.salon,
                "modalidad": inst_ex.modalidad.value if inst_ex.modalidad else None,
                "tipo": inst_ex.tipo.value if inst_ex.tipo else None,
                "ya_inscripto": ya_inscripto is not None,
            })

    return resultado


@router.get("/todos-mis-examenes")
async def todos_mis_examenes(
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    session: Session = Depends(get_session),
):
    """Todos los exámenes del alumno (todas las materias), ordenados por fecha"""
    from v2.models.inscripcion_materia import InscripcionMateria
    from v2.models.instancia_cursado import InstanciaCursado
    from v2.models.instancia_examen import InstanciaExamen
    from v2.models.inscripcion_examen import InscripcionExamen
    from v2.models.materia import Materia

    examenes = session.exec(
        select(InscripcionExamen, InscripcionMateria, InstanciaExamen)
        .join(InscripcionMateria, InscripcionExamen.inscripcion_materia_id == InscripcionMateria.id)
        .join(InstanciaExamen, InscripcionExamen.instancia_examen_id == InstanciaExamen.id)
        .where(InscripcionMateria.alumno_id == alumno.id)
        .order_by(InstanciaExamen.fecha_examen.desc())
    ).all()

    resultado = []
    for ie, im, inst_ex in examenes:
        ic = session.get(InstanciaCursado, im.instancia_cursado_id)
        materia = session.get(Materia, ic.materia_id) if ic else None
        resultado.append({
            "inscripcion_examen_id": ie.id,
            "inscripcion_materia_id": im.id,
            "materia_nombre": materia.nombre if materia else "",
            "materia_codigo": materia.codigo if materia else "",
            "nombre_examen": inst_ex.nombre,
            "fecha_examen": inst_ex.fecha_examen.isoformat() if inst_ex.fecha_examen else None,
            "estado": ie.estado.value,
            "nota_examen": float(ie.nota_examen) if ie.nota_examen is not None else None,
        })

    return resultado


# -- Egreso -------------------------------------------------------------------

@router.get("/mi-egreso")
async def mi_egreso(
    programa_id: int = Query(..., description="ID del programa"),
    current_usuario: UsuarioRead = Depends(require_estudiante),
    alumno: Alumno = Depends(get_current_alumno),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Verificar mi progreso de egreso en un programa"""
    try:
        return v2_services.egresoService.verificar_egreso(
            alumno.id, programa_id, session
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -- Documentos ----------------------------------------------------------------

@router.post("/documentos", response_model=DocumentoUsuarioRead, status_code=201)
async def subir_documento(
    archivo: UploadFile = File(...),
    tipo: TipoDocumento = Form(...),
    descripcion: Optional[str] = Form(None),
    current_usuario: UsuarioRead = Depends(require_estudiante),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Subir un documento propio (PDF o imagen). Las imagenes se convierten a WebP automaticamente."""
    # Los documentos pertenecen a la persona (usuario), no al perfil academico
    return await v2_services.localFileService.upload(
        archivo=archivo,
        usuario_id=current_usuario.id,
        nombre=current_usuario.nombre,
        apellido=current_usuario.apellido,
        rol=current_usuario.rol,
        tipo=tipo,
        subido_por=current_usuario.id,
        session=session,
        descripcion=descripcion,
    )


@router.get("/mis-documentos", response_model=list[DocumentoUsuarioRead])
async def mis_documentos(
    tipo: Optional[TipoDocumento] = Query(None, description="Filtrar por tipo de documento"),
    current_usuario: UsuarioRead = Depends(require_estudiante),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Listar mis documentos subidos"""
    return v2_services.localFileService.list_documentos(
        current_usuario.id, session, tipo=tipo
    )


@router.get("/documentos/{documento_id}")
async def descargar_documento(
    documento_id: int,
    current_usuario: UsuarioRead = Depends(require_estudiante),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Descargar un documento propio"""
    doc = v2_services.localFileService.get_documento(documento_id, session)
    if not doc or not doc.activo:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    if doc.usuario_id != current_usuario.id:
        raise HTTPException(status_code=403, detail="No es tu documento")

    path = v2_services.localFileService.download_path(doc)
    return FileResponse(
        path=str(path),
        media_type=doc.mime_type,
        filename=doc.nombre_original,
    )
