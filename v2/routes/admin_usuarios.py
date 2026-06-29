"""
Endpoints de administracion de usuarios para dashboards de alumnos/docentes,
y creacion manual de usuarios sin cuenta de Google.

Caso de uso: ponentes que dan una charla puntual (necesitan figurar como
docente pero nunca inician sesion) o asistentes a charlas (necesitan figurar
como alumno sin requerir usuario). El admin los registra manualmente y, si
esa persona luego inicia sesion con Google usando el mismo email, el sistema
vincula la cuenta automaticamente (ver v2/routes/auth_google.py).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import UsuarioRead
from v2.models.enums import RolUsuario


router = APIRouter(
    prefix="/v2/admin/usuarios",
    tags=["v2 - Admin Usuarios"],
)


# ── Schemas de request ──────────────────────────────────────────────────────

class UsuarioManualCreate(BaseModel):
    email: str
    nombre: str
    apellido: str
    rol: RolUsuario
    documento: Optional[str] = None
    telefono: Optional[str] = None
    email_personal: Optional[str] = None


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post(
    "/manual",
    summary="Crear usuario manualmente (sin cuenta de Google)",
    description="Crea un usuario y su perfil (alumno/docente/administrativo) sin "
                "requerir login de Google. Util para ponentes que dan una charla "
                "sin necesitar usuario, o asistentes a charlas que deben quedar "
                "registrados. Si la persona luego inicia sesion con Google usando "
                "el mismo email, el sistema vincula la cuenta automaticamente.",
)
async def crear_usuario_manual(
    body: UsuarioManualCreate,
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
    current_usuario: UsuarioRead = Depends(require_administrativo),
):
    try:
        usuario = v2_services.usuarioService.create_manual(
            email=body.email,
            nombre=body.nombre,
            apellido=body.apellido,
            rol=body.rol,
            session=session,
            documento=body.documento,
            telefono=body.telefono,
            email_personal=body.email_personal,
        )
        return UsuarioRead.model_validate(usuario)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/alumnos",
    summary="Listar alumnos (dashboard)",
    description="Lista paginada de alumnos con datos de usuario embebidos. "
                "Incluye alumnos con cuenta de Google y los creados manualmente "
                "(campo tiene_login distingue unos de otros).",
)
async def listar_alumnos(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    search: Optional[str] = Query(default=None, description="Busca por nombre, apellido o email"),
    activo: Optional[bool] = Query(default=None),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
    current_usuario: UsuarioRead = Depends(require_administrativo),
):
    return v2_services.usuarioService.get_alumnos_dashboard(
        session, page=page, per_page=per_page, search=search, activo=activo
    )


@router.get(
    "/docentes",
    summary="Listar docentes (dashboard)",
    description="Lista paginada de docentes con datos de usuario embebidos. "
                "Incluye docentes con cuenta de Google y los creados manualmente, "
                "por ejemplo ponentes que dieron una charla puntual (campo "
                "tiene_login distingue unos de otros).",
)
async def listar_docentes(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    search: Optional[str] = Query(default=None, description="Busca por nombre, apellido o email"),
    activo: Optional[bool] = Query(default=None),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
    current_usuario: UsuarioRead = Depends(require_administrativo),
):
    return v2_services.usuarioService.get_docentes_dashboard(
        session, page=page, per_page=per_page, search=search, activo=activo
    )
