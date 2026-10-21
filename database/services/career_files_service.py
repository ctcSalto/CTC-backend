"""
Archivos descargables de la oferta académica (pedido de dirección, 08/10/2026).

El sitio público muestra cada carrera o curso con sus archivos (el programa,
el plan de estudios, un folleto) y el visitante los descarga. Se guardan en la
VPS, no en Supabase: en

    OFERTA_ARCHIVOS_PATH  (default: DOCUMENTOS_BASE_PATH/oferta_academica)

una carpeta por carrera, y se sirven públicamente en
GET /careers/files/{careerId}/{nombre}. En producción DOCUMENTOS_BASE_PATH ya
apunta al volumen persistente (/var/ctc/documentos), así que no hace falta
otro volumen; sin volumen, Easypanel borra los archivos en cada despliegue.

Lo que se acepta lo decide el CONTENIDO del archivo, nunca el nombre ni el
content-type que manda quien sube (los dos los elige el cliente). Mismo
criterio que v2/services/local_file_service.py:

    PDF                 %PDF-
    Word, Excel, PPT    ZIP con la estructura de Office (word/, xl/, ppt/)
    OpenDocument        ZIP con el archivo `mimetype` de ODF
    Office viejo        contenedor OLE (doc, xls, ppt); acá la extensión sí sale
                        del nombre, porque el formato no dice cuál de los tres es
    Imágenes            JPG, PNG, WebP

Un ZIP cualquiera, un ejecutable o un HTML no pasan: se sirven en un dominio
público y un HTML ahí es un vector de phishing.

El nombre en disco es `<8 hex>_<nombre-original-saneado>.<ext>`: el prefijo
evita choques y que se adivinen URLs, y el resto conserva un nombre legible
para la descarga.
"""
import io
import os
import re
import shutil
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import uuid4

TIPOS = {
    # extension: (content-type, se abre en el navegador)
    "pdf": ("application/pdf", True),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", False),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", False),
    "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", False),
    "doc": ("application/msword", False),
    "xls": ("application/vnd.ms-excel", False),
    "ppt": ("application/vnd.ms-powerpoint", False),
    "odt": ("application/vnd.oasis.opendocument.text", False),
    "ods": ("application/vnd.oasis.opendocument.spreadsheet", False),
    "odp": ("application/vnd.oasis.opendocument.presentation", False),
    "jpg": ("image/jpeg", True),
    "png": ("image/png", True),
    "webp": ("image/webp", True),
}
EXTENSIONES_ACEPTADAS = ", ".join(sorted(TIPOS))

FIRMA_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
CARPETA_OOXML = {"word/": "docx", "xl/": "xlsx", "ppt/": "pptx"}
MIMETYPE_ODF = {
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/vnd.oasis.opendocument.presentation": "odp",
}

# Lo que puede tener un nombre guardado. Sirve para validar el {nombre} de la
# URL publica antes de tocar el disco: nada de barras, puntos de mas ni '..'.
RE_NOMBRE_GUARDADO = re.compile(r"^[0-9a-f]{8}_[a-z0-9_-]{1,80}\.(" + "|".join(TIPOS) + r")$")

MAX_ARCHIVOS_POR_CARRERA = 20


class ArchivoInvalido(ValueError):
    """El archivo no se acepta: el mensaje es para mostrarle al administrador."""


@dataclass
class ArchivoValidado:
    contenido: bytes
    extension: str
    nombre_original: str


def _saneado(texto: str) -> str:
    """'Plan de Estudios 2026 (versión final)' -> 'plan_de_estudios_2026_version_final'."""
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    limpio = re.sub(r"[^a-z0-9-]+", "_", sin_acentos.lower()).strip("_-")
    return (limpio or "archivo")[:80].strip("_-") or "archivo"


def detectar_extension(contenido: bytes, nombre: str) -> Optional[str]:
    """La extension que corresponde al contenido, o None si no es un tipo aceptado."""
    if contenido.startswith(b"%PDF-"):
        return "pdf"
    if contenido.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
        return "webp"
    if contenido.startswith(FIRMA_OLE):
        # doc, xls y ppt comparten el contenedor: el nombre dice cual es, y si
        # no es ninguno de los tres no se acepta
        extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
        return extension if extension in ("doc", "xls", "ppt") else None
    if contenido.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                nombres = z.namelist()
                if "mimetype" in nombres:
                    return MIMETYPE_ODF.get(z.read("mimetype").decode("ascii", "ignore").strip())
                if "[Content_Types].xml" in nombres:
                    for carpeta, extension in CARPETA_OOXML.items():
                        if any(n.startswith(carpeta) for n in nombres):
                            return extension
        except (zipfile.BadZipFile, KeyError, OSError):
            return None
    return None


class CareerFilesService:

    def __init__(self, base_path: Optional[str] = None, base_url: Optional[str] = None,
                 max_mb: Optional[int] = None):
        documentos = os.getenv("DOCUMENTOS_BASE_PATH", "./documentos_dev")
        self.base_path = Path(base_path or os.getenv("OFERTA_ARCHIVOS_PATH")
                              or os.path.join(documentos, "oferta_academica"))
        self.base_url = (base_url if base_url is not None else os.getenv("BASE_URL", "")).rstrip("/")
        self.max_mb = max_mb or int(os.getenv("OFERTA_ARCHIVOS_MAX_MB", "20"))

    # ── Validacion ───────────────────────────────────────────────────────────

    def validar(self, contenido: bytes, nombre: str) -> ArchivoValidado:
        nombre = (nombre or "").strip() or "archivo"
        if not contenido:
            raise ArchivoInvalido(f"'{nombre}' esta vacio.")
        if len(contenido) > self.max_mb * 1024 * 1024:
            raise ArchivoInvalido(f"'{nombre}' pesa mas de {self.max_mb} MB.")
        extension = detectar_extension(contenido, nombre)
        if extension is None:
            raise ArchivoInvalido(
                f"'{nombre}' no es de un tipo aceptado. Se aceptan: {EXTENSIONES_ACEPTADAS}.")
        return ArchivoValidado(contenido=contenido, extension=extension, nombre_original=nombre)

    # ── Disco y URLs ─────────────────────────────────────────────────────────

    def _carpeta(self, career_id: int) -> Path:
        return self.base_path / str(int(career_id))

    def url_de(self, career_id: int, nombre_guardado: str) -> str:
        return f"{self.base_url}/careers/files/{int(career_id)}/{nombre_guardado}"

    def guardar(self, career_id: int, archivos: List[ArchivoValidado]) -> List[str]:
        """Escribe los archivos ya validados y devuelve sus URLs, en el mismo orden."""
        carpeta = self._carpeta(career_id)
        carpeta.mkdir(parents=True, exist_ok=True)
        urls = []
        for archivo in archivos:
            stem = archivo.nombre_original.rsplit(".", 1)[0] if "." in archivo.nombre_original else archivo.nombre_original
            nombre = f"{uuid4().hex[:8]}_{_saneado(stem)}.{archivo.extension}"
            (carpeta / nombre).write_bytes(archivo.contenido)
            urls.append(self.url_de(career_id, nombre))
        return urls

    def nombre_de_url(self, career_id: int, url: str) -> Optional[str]:
        """El nombre guardado de una URL de esta carrera, o None si no es una."""
        prefijo = f"/careers/files/{int(career_id)}/"
        if prefijo not in url:
            return None
        nombre = url.rsplit(prefijo, 1)[1]
        return nombre if RE_NOMBRE_GUARDADO.match(nombre) else None

    def ruta(self, career_id: int, nombre: str) -> Optional[Tuple[Path, str, bool, str]]:
        """
        (ruta, content-type, se_abre_en_navegador, nombre_para_descargar) de un
        archivo guardado, o None si el nombre no es valido o el archivo no esta.
        """
        if not RE_NOMBRE_GUARDADO.match(nombre or ""):
            return None
        carpeta = self._carpeta(career_id).resolve()
        ruta = (carpeta / nombre).resolve()
        if ruta.parent != carpeta or not ruta.is_file():
            return None
        extension = nombre.rsplit(".", 1)[1]
        tipo, en_navegador = TIPOS[extension]
        return ruta, tipo, en_navegador, nombre.split("_", 1)[1]

    def borrar(self, career_id: int, nombre: str) -> None:
        encontrado = self.ruta(career_id, nombre)
        if encontrado:
            encontrado[0].unlink(missing_ok=True)

    def borrar_todos(self, career_id: int) -> None:
        shutil.rmtree(self._carpeta(career_id), ignore_errors=True)
