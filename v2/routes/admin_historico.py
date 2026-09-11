"""
Legajo historico: consulta de la planilla de escolaridades que bedelia
llevaba antes del portal (2004-2026).

Solo lectura. Los datos no se cuelgan de programas ni materias vigentes: son
tablas propias (historico_*) cargadas una vez con
v2/scripts/importar_historico.py. Ver docs/HISTORICO_ESCOLARIDADES.md.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.historico import LegajoHistoricoRead

router = APIRouter(
    prefix="/v2/admin/historico",
    tags=["v2 - Admin Historico"],
)


@router.get(
    "/alumnos",
    summary="Buscar personas en el historico",
    description="`q` con digitos busca por cedula (prefijo); con letras busca en el "
                "nombre sin distinguir acentos. `plan` deja solo a quienes tienen "
                "resultados en ese plan. Cada fila trae los planes con resultados y "
                "el rango de fechas, para reconocer a la persona antes de abrir el legajo.",
)
async def buscar_alumnos(
    q: Optional[str] = Query(default=None, min_length=2, description="Cedula o parte del nombre"),
    plan: Optional[str] = Query(default=None, description="Codigo de plan, ej: 'AP 2011'"),
    solo_con_resultados: bool = Query(default=False, description="Excluye a quienes no tienen ninguna acta"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return v2_services.historicoService.buscar_alumnos(
        session, q=q, plan=plan, solo_con_resultados=solo_con_resultados,
        limit=limit, offset=offset,
    )


@router.get(
    "/alumnos/{cedula}",
    response_model=LegajoHistoricoRead,
    summary="Legajo historico de una persona",
    description="Datos de la persona, resumen por plan (creditos aprobados, "
                "revalidados y promedio, con la misma regla que el certificado de "
                "escolaridad que emitia bedelia) y todas las actas ordenadas por "
                "fecha. La cedula puede venir con puntos y guion.",
)
async def legajo(
    cedula: str,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    legajo = v2_services.historicoService.legajo(session, cedula)
    if not legajo:
        raise HTTPException(status_code=404, detail="No hay legajo historico para esa cedula")
    return legajo


@router.get(
    "/planes",
    summary="Planes historicos",
    description="Los codigos de plan tal como los usaba la planilla, con carrera, "
                "creditos requeridos y cuantos alumnos y actas tiene cada uno.",
)
async def listar_planes(
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return v2_services.historicoService.listar_planes(session)


@router.get(
    "/materias",
    summary="Materias historicas",
    description="Nombres de materia distintos, para armar filtros. Son los de la "
                "planilla: hay variantes de una misma materia entre planes.",
)
async def listar_materias(
    plan: Optional[str] = Query(default=None, description="Limita a un plan"),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return v2_services.historicoService.listar_materias(session, plan=plan)


@router.get(
    "/resultados",
    summary="Buscar actas",
    description="Filas sueltas, sin pasar por el alumno: quienes rindieron una "
                "materia, que hay en un acta, que se cargo entre dos fechas. "
                "Ordenadas de la mas reciente a la mas vieja.",
)
async def buscar_resultados(
    cedula: Optional[str] = Query(default=None),
    plan: Optional[str] = Query(default=None, description="Codigo de plan exacto"),
    materia: Optional[str] = Query(default=None, description="Parte del nombre"),
    tipo_evaluacion: Optional[str] = Query(default=None, description="CUR, EXA, TALLER, REV, DIP"),
    resultado: Optional[str] = Query(default=None, description="APR, EXO, ELI, NSP, REV, EXA, PEND"),
    acta: Optional[str] = Query(default=None, description="Numero de acta exacto"),
    desde: Optional[date] = Query(default=None),
    hasta: Optional[date] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    return v2_services.historicoService.buscar_resultados(
        session, cedula=cedula, plan=plan, materia=materia,
        tipo_evaluacion=tipo_evaluacion, resultado=resultado, acta=acta,
        desde=desde, hasta=hasta, limit=limit, offset=offset,
    )
