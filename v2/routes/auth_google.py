"""
Endpoints de autenticacion Google OAuth 2.0 para el portal academico.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session
from starlette.middleware.sessions import SessionMiddleware

from database.database import get_session, get_services
from v2.services import V2Services, get_v2_services
from v2.auth.google_oauth import (
    get_google_client,
    validate_google_domain,
    extract_user_data,
    get_role_from_ou,
    lookup_moodle_id,
    GOOGLE_REDIRECT_URI,
)
from v2.auth.security import create_v2_token, blacklist_v2_token, verify_v2_token
from v2.auth.dependencies import get_current_usuario
from v2.models.usuario import UsuarioRead

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


router = APIRouter(prefix="/v2/auth", tags=["v2 - Autenticacion"])
security = HTTPBearer()


@router.get("/google/login")
async def google_login(request: Request):
    """Inicia el flujo OAuth. Redirige al usuario a Google para autenticarse."""
    google = get_google_client()
    return await google.authorize_redirect(request, GOOGLE_REDIRECT_URI)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """
    Callback de Google OAuth. Recibe el code, valida dominio,
    obtiene OU via n8n, crea/actualiza usuario, y retorna JWT.
    """
    google = get_google_client()

    try:
        token = await google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error al autenticar con Google: {str(e)}",
        )

    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudieron obtener los datos del usuario de Google",
        )

    # 1. Validar dominio institucional
    if not validate_google_domain(user_info):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo se permiten cuentas @ctcsalto.edu.uy",
        )

    # 2. Extraer datos del usuario
    google_data = extract_user_data(user_info)

    # 3. Obtener OU y rol via n8n
    ou_path, rol = get_role_from_ou(google_data["email"])

    # 4. Buscar moodle_id
    moodle_id = lookup_moodle_id(google_data["email"])

    # 5. Buscar o crear usuario
    usuario = v2_services.usuarioService.get_by_google_id(google_data["google_id"], session)

    if usuario is None:
        # Fallback: buscar por email (por si se creo manualmente)
        usuario = v2_services.usuarioService.get_by_email(google_data["email"], session)

    if usuario is None:
        # Crear nuevo usuario
        usuario = v2_services.usuarioService.create_from_google(
            google_id=google_data["google_id"],
            email=google_data["email"],
            nombre=google_data["nombre"],
            apellido=google_data["apellido"],
            foto_url=google_data["foto_url"],
            ou_google=ou_path,
            rol=rol,
            moodle_id=moodle_id,
            session=session,
        )
        print(f"[OK] Usuario v2 creado: {usuario.email} (rol: {rol.value})")
    else:
        # Actualizar datos en cada login (re-sync rol, foto, etc.)
        usuario = v2_services.usuarioService.update_on_login(
            usuario=usuario,
            nombre=google_data["nombre"],
            apellido=google_data["apellido"],
            foto_url=google_data["foto_url"],
            ou_google=ou_path,
            rol=rol,
            moodle_id=moodle_id,
            session=session,
        )
        print(f"[OK] Usuario v2 actualizado: {usuario.email} (rol: {rol.value})")

    # 6. Verificar que el usuario este activo
    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta esta desactivada. Contacta al administrador.",
        )

    # 7. Generar JWT v2
    jwt_token = create_v2_token(
        email=usuario.email,
        usuario_id=usuario.id,
        rol=usuario.rol.value,
    )

    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "usuario": UsuarioRead.model_validate(usuario).model_dump(),
    }


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_usuario: UsuarioRead = Depends(get_current_usuario),
    services=Depends(get_services),
):
    """Revoca el token JWT actual (lo agrega al blacklist de Redis)."""
    token = credentials.credentials
    success = blacklist_v2_token(token, services.redisService)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al revocar el token",
        )

    return {"message": "Sesion cerrada exitosamente"}


@router.get("/me", response_model=UsuarioRead)
async def get_me(current_usuario: UsuarioRead = Depends(get_current_usuario)):
    """Retorna los datos del usuario autenticado."""
    return current_usuario
