from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlmodel import Session
from typing import Optional

from database.database import get_session
from v2.services import V2Services, get_v2_services
from v2.auth.dependencies import require_administrativo
from v2.models.usuario import Usuario, UsuarioRead
from v2.models.documento_usuario import DocumentoUsuarioRead
from v2.models.enums import TipoDocumento

router = APIRouter(
    prefix="/v2/admin/documentos",
    tags=["v2 - Admin Documentos"],
)


@router.post("/{usuario_id}", response_model=DocumentoUsuarioRead, status_code=201)
async def subir_documento_para_usuario(
    usuario_id: int,
    archivo: UploadFile = File(...),
    tipo: TipoDocumento = Form(...),
    descripcion: Optional[str] = Form(None),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Subir un documento para cualquier usuario (solo admin)"""
    usuario = session.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return await v2_services.localFileService.upload(
        archivo=archivo,
        usuario_id=usuario.id,
        nombre=usuario.nombre,
        apellido=usuario.apellido,
        rol=usuario.rol,
        tipo=tipo,
        subido_por=current_usuario.id,
        session=session,
        descripcion=descripcion,
    )


@router.get("/{usuario_id}", response_model=list[DocumentoUsuarioRead])
async def listar_documentos_usuario(
    usuario_id: int,
    tipo: Optional[TipoDocumento] = Query(None, description="Filtrar por tipo de documento"),
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Listar documentos de un usuario (solo admin)"""
    usuario = session.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return v2_services.localFileService.list_documentos(usuario_id, session, tipo=tipo)


@router.get("/descargar/{documento_id}")
async def descargar_documento_admin(
    documento_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Descargar cualquier documento (solo admin)"""
    doc = v2_services.localFileService.get_documento(documento_id, session)
    if not doc or not doc.activo:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    path = v2_services.localFileService.download_path(doc)
    return FileResponse(
        path=str(path),
        media_type=doc.mime_type,
        filename=doc.nombre_original,
    )


@router.delete("/{documento_id}", status_code=204)
async def eliminar_documento(
    documento_id: int,
    current_usuario: UsuarioRead = Depends(require_administrativo),
    v2_services: V2Services = Depends(get_v2_services),
    session: Session = Depends(get_session),
):
    """Eliminar un documento (soft delete, solo admin)"""
    v2_services.localFileService.soft_delete(documento_id, session)
