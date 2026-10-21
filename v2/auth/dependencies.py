"""
Dependencies de autenticacion para el portal academico v2.
Sigue el patron de database/services/auth/dependencies.py
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select

from database.database import get_session, get_services
from v2.services import V2Services, get_v2_services
from v2.auth.security import verify_v2_token
from v2.models.usuario import UsuarioRead
from v2.models.alumno import Alumno
from v2.models.profesor import Profesor
from v2.models.enums import RolUsuario


security_v2 = HTTPBearer()


async def get_current_usuario(
    credentials: HTTPAuthorizationCredentials = Depends(security_v2),
    v2_services: V2Services = Depends(get_v2_services),
    services=Depends(get_services),
    session: Session = Depends(get_session),
) -> UsuarioRead:
    """Obtiene el usuario v2 actual desde el JWT."""
    try:
        token = credentials.credentials
        redis_service = services.redisService

        payload = verify_v2_token(token, redis_service)

        email = payload.get("sub")
        usuario = v2_services.usuarioService.get_by_email(email, session)

        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not usuario.activo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario inactivo",
            )

        return UsuarioRead.model_validate(usuario)

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error de autenticacion",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Factories de roles ───────────────────────────────────────────────────────

def require_rol(required_rol: RolUsuario):
    """Factory para requerir un rol especifico."""
    async def checker(current: UsuarioRead = Depends(get_current_usuario)):
        if current.rol != required_rol:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rol '{required_rol.value}' requerido. Rol actual: {current.rol.value}",
            )
        return current
    return checker


def require_roles(allowed: list[RolUsuario]):
    """Factory para permitir multiples roles."""
    async def checker(current: UsuarioRead = Depends(get_current_usuario)):
        if current.rol not in allowed:
            names = [r.value for r in allowed]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Se requiere uno de estos roles: {', '.join(names)}. Rol actual: {current.rol.value}",
            )
        return current
    return checker


# ── Dependencies pre-compuestas ──────────────────────────────────────────────

async def require_estudiante(current: UsuarioRead = Depends(get_current_usuario)) -> UsuarioRead:
    if current.rol != RolUsuario.ESTUDIANTE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol de estudiante requerido")
    return current


async def require_docente(current: UsuarioRead = Depends(get_current_usuario)) -> UsuarioRead:
    if current.rol != RolUsuario.DOCENTE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol de docente requerido")
    return current


async def require_administrativo(current: UsuarioRead = Depends(get_current_usuario)) -> UsuarioRead:
    if current.rol != RolUsuario.ADMINISTRATIVO:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol de administrativo requerido")
    return current


async def require_docente_or_admin(current: UsuarioRead = Depends(get_current_usuario)) -> UsuarioRead:
    if current.rol not in (RolUsuario.DOCENTE, RolUsuario.ADMINISTRATIVO):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol de docente o administrativo requerido")
    return current


# ── Perfiles academicos ──────────────────────────────────────────────────────
# Las entidades academicas (inscripciones, calificaciones, equipos, asignaciones
# docentes) referencian alumno.id / profesor.id, no usuario.id. El JWT identifica
# a la persona, asi que estas dependencies traducen persona -> sujeto academico
# una sola vez, en lugar de repetir el lookup en cada endpoint.

async def get_current_alumno(
    current: UsuarioRead = Depends(require_estudiante),
    session: Session = Depends(get_session),
) -> Alumno:
    """Perfil de alumno del usuario autenticado."""
    alumno = session.exec(
        select(Alumno).where(Alumno.usuario_id == current.id)
    ).first()
    if not alumno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tenes perfil de alumno. Contacta a administracion.",
        )
    return alumno


async def get_current_profesor(
    current: UsuarioRead = Depends(require_docente),
    session: Session = Depends(get_session),
) -> Profesor:
    """Perfil de profesor del usuario autenticado."""
    profesor = session.exec(
        select(Profesor).where(Profesor.usuario_id == current.id)
    ).first()
    if not profesor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tenes perfil de profesor. Contacta a administracion.",
        )
    return profesor
