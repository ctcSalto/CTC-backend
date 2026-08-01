import os
import io
import unicodedata
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import UploadFile, HTTPException
from sqlmodel import Session, select

from v2.models.documento_usuario import DocumentoUsuario, DocumentoUsuarioRead
from v2.models.enums import TipoDocumento, RolUsuario

try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def get_uruguay_tz():
    tz_name = os.getenv('TIME_ZONE', 'America/Montevideo')
    return ZoneInfo(tz_name)


# Tipos MIME permitidos
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

# MIME types que son imagenes procesables
IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# La extension SIEMPRE sale del tipo real detectado, nunca del nombre que mando
# el cliente: con el nombre se podian guardar archivos .html o .php declarando
# content-type de PDF, y una extension con barras hacia atras terminaba en un 500.
EXTENSION_POR_MIME = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}

# Firmas de los formatos aceptados. El header content-type lo elige quien sube,
# asi que no sirve como validacion: hay que mirar el contenido.
FIRMAS = {
    b"%PDF-": "application/pdf",
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}

# Carpetas por tipo de documento
FOLDER_POR_TIPO = {
    TipoDocumento.FORMULA_69A: "formula_69a",
    TipoDocumento.ESCOLARIDAD: "escolaridad",
    TipoDocumento.CONSTANCIA_CONVENIO: "constancia_convenio",
    TipoDocumento.CEDULA: "cedula",
    TipoDocumento.TITULO: "titulo",
    TipoDocumento.OTRO: "otros",
}

# Carpeta raiz por rol
CARPETA_ROL = {
    RolUsuario.ESTUDIANTE: "alumnos",
    RolUsuario.DOCENTE: "profesores",
    RolUsuario.ADMINISTRATIVO: "administrativos",
}


class LocalFileService:

    def __init__(self):
        self.base_path = os.getenv("DOCUMENTOS_BASE_PATH", "./documentos_dev")
        self.max_size_mb = int(os.getenv("DOCUMENTOS_MAX_SIZE_MB", "10"))
        self.max_size_bytes = self.max_size_mb * 1024 * 1024
        self.webp_quality = 85
        self.max_dimension = 2000

    # ── Utilidades ────────────────────────────────────────────────────────

    @staticmethod
    def sanitize_name(texto: str) -> str:
        """Normaliza texto para nombre de carpeta: sin acentos, minusculas, espacios -> _"""
        # Quitar acentos
        nfkd = unicodedata.normalize('NFKD', texto)
        sin_acentos = ''.join(c for c in nfkd if not unicodedata.combining(c))
        # Minusculas, reemplazar espacios y caracteres especiales
        limpio = re.sub(r'[^a-z0-9]', '_', sin_acentos.lower())
        # Eliminar underscores multiples
        limpio = re.sub(r'_+', '_', limpio).strip('_')
        return limpio

    def _get_user_folder(self, usuario_id: int, nombre: str, apellido: str, rol: RolUsuario) -> str:
        """Genera la ruta de carpeta del usuario: alumnos/1_perez_juan/"""
        carpeta_rol = CARPETA_ROL.get(rol, "otros")
        nombre_s = self.sanitize_name(nombre)
        apellido_s = self.sanitize_name(apellido)
        return f"{carpeta_rol}/{usuario_id}_{apellido_s}_{nombre_s}"

    def _ensure_directory(self, relative_path: str) -> Path:
        """Crea el directorio si no existe y retorna la ruta absoluta"""
        full_path = Path(self.base_path) / relative_path
        full_path.mkdir(parents=True, exist_ok=True)
        return full_path

    @staticmethod
    def detectar_mime_real(contenido: bytes) -> Optional[str]:
        """
        Deduce el tipo del archivo por su contenido.

        WebP se chequea aparte porque su firma no es un prefijo continuo:
        son los bytes 'RIFF' seguidos del tamano y recien despues 'WEBP'.
        """
        for firma, mime in FIRMAS.items():
            if contenido.startswith(firma):
                return mime
        if contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
            return "image/webp"
        return None

    def _process_image(self, file_content: bytes) -> bytes:
        """Procesa imagen: WebP, EXIF transpose, resize max 2000px"""
        if not PIL_AVAILABLE:
            return file_content

        image = Image.open(io.BytesIO(file_content))

        # Modo color compatible con WebP
        if image.mode in ('RGBA', 'LA', 'P'):
            if image.mode == 'P':
                image = image.convert('RGBA')
        elif image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')

        # Rotacion EXIF
        image = ImageOps.exif_transpose(image)

        # Resize si supera max_dimension
        w, h = image.size
        if w > self.max_dimension or h > self.max_dimension:
            image.thumbnail((self.max_dimension, self.max_dimension), Image.LANCZOS)

        # Guardar como WebP
        buffer = io.BytesIO()
        save_kwargs = {
            'format': 'WebP',
            'quality': self.webp_quality,
            'optimize': True,
            'method': 6,
        }
        if image.mode == 'RGBA':
            save_kwargs['lossless'] = False
        image.save(buffer, **save_kwargs)

        return buffer.getvalue()

    # ── Operaciones principales ───────────────────────────────────────────

    async def upload(
        self,
        archivo: UploadFile,
        usuario_id: int,
        nombre: str,
        apellido: str,
        rol: RolUsuario,
        tipo: TipoDocumento,
        subido_por: int,
        session: Session,
        descripcion: Optional[str] = None,
    ) -> DocumentoUsuarioRead:
        """Sube un archivo al disco y crea el registro en BD"""

        # Filtro barato antes de leer el cuerpo. No es la validacion real: el
        # content-type lo elige quien sube y se puede mentir.
        if archivo.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de archivo no permitido: {archivo.content_type}. "
                       f"Permitidos: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
            )

        # Leer contenido
        contenido = await archivo.read()

        # Validar tamano
        if len(contenido) > self.max_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Archivo demasiado grande ({len(contenido) / 1024 / 1024:.1f} MB). "
                       f"Maximo: {self.max_size_mb} MB"
            )

        # Validacion de verdad: por contenido. Sin esto se podia guardar un .html
        # o un .php declarando content-type de PDF, y la whitelist no servia de nada.
        mime_real = self.detectar_mime_real(contenido)
        if mime_real is None:
            raise HTTPException(
                status_code=400,
                detail="El contenido del archivo no corresponde a un PDF ni a una "
                       "imagen valida (JPEG, PNG, WebP o GIF)",
            )
        if mime_real != archivo.content_type:
            raise HTTPException(
                status_code=400,
                detail=f"El archivo dice ser {archivo.content_type} pero su contenido "
                       f"es {mime_real}",
            )

        # Determinar carpeta
        user_folder = self._get_user_folder(usuario_id, nombre, apellido, rol)
        tipo_folder = FOLDER_POR_TIPO.get(tipo, "otros")
        relative_dir = f"{user_folder}/{tipo_folder}"

        # Procesar segun tipo
        ahora = datetime.now(get_uruguay_tz())
        fecha_str = ahora.strftime("%Y-%m-%d")
        es_imagen = mime_real in IMAGE_MIME_TYPES
        mime_final = mime_real

        if es_imagen and mime_real != "image/webp":
            try:
                contenido = self._process_image(contenido)
                mime_final = "image/webp"
            except Exception:
                # Fallback: se guarda el original con la extension de su tipo real
                mime_final = mime_real

        # La extension sale SIEMPRE del tipo detectado. Tomarla del nombre que
        # manda el cliente permitia guardar .html/.php, y una extension con
        # barras terminaba en un FileNotFoundError sin manejar (500).
        ext = EXTENSION_POR_MIME[mime_final]
        nombre_archivo = f"{fecha_str}_{tipo_folder}.{ext}"

        # Si ya existe un archivo con el mismo nombre, agregar sufijo
        ruta_relativa = f"{relative_dir}/{nombre_archivo}"
        abs_dir = self._ensure_directory(relative_dir)
        dest = abs_dir / nombre_archivo

        if dest.exists():
            base, ext_part = nombre_archivo.rsplit('.', 1)
            sufijo = 1
            while dest.exists():
                nombre_archivo = f"{base}_{sufijo}.{ext_part}"
                dest = abs_dir / nombre_archivo
                sufijo += 1
            ruta_relativa = f"{relative_dir}/{nombre_archivo}"

        # Escribir archivo
        dest.write_bytes(contenido)

        # Crear registro en BD
        documento = DocumentoUsuario(
            usuario_id=usuario_id,
            tipo=tipo,
            nombre_original=archivo.filename or "sin_nombre",
            ruta_relativa=ruta_relativa,
            mime_type=mime_final,
            tamanio_bytes=len(contenido),
            descripcion=descripcion,
            subido_por=subido_por,
            fecha_subida=ahora,
        )
        session.add(documento)
        session.commit()
        session.refresh(documento)

        return DocumentoUsuarioRead.model_validate(documento)

    def download_path(self, documento: DocumentoUsuario) -> Path:
        """Retorna la ruta absoluta del archivo para FileResponse"""
        full = Path(self.base_path) / documento.ruta_relativa
        if not full.exists():
            raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")
        return full

    def list_documentos(
        self,
        usuario_id: int,
        session: Session,
        tipo: Optional[TipoDocumento] = None,
    ) -> List[DocumentoUsuarioRead]:
        """Lista documentos activos de un usuario, opcionalmente filtrados por tipo"""
        stmt = select(DocumentoUsuario).where(
            DocumentoUsuario.usuario_id == usuario_id,
            DocumentoUsuario.activo == True,
        )
        if tipo:
            stmt = stmt.where(DocumentoUsuario.tipo == tipo)
        stmt = stmt.order_by(DocumentoUsuario.fecha_subida.desc())

        docs = session.exec(stmt).all()
        return [DocumentoUsuarioRead.model_validate(d) for d in docs]

    def get_documento(self, documento_id: int, session: Session) -> Optional[DocumentoUsuario]:
        """Obtiene un documento por ID"""
        return session.get(DocumentoUsuario, documento_id)

    def soft_delete(self, documento_id: int, session: Session) -> bool:
        """Marca un documento como inactivo (soft delete)"""
        doc = session.get(DocumentoUsuario, documento_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        doc.activo = False
        session.commit()
        return True

    def hard_delete(self, documento_id: int, session: Session) -> bool:
        """Elimina el registro y el archivo fisico"""
        doc = session.get(DocumentoUsuario, documento_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado")

        # Borrar archivo fisico
        full = Path(self.base_path) / doc.ruta_relativa
        if full.exists():
            full.unlink()

        session.delete(doc)
        session.commit()
        return True
