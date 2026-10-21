"""
Validacion de archivos subidos.

El content-type de un multipart lo elige quien sube, asi que la whitelist de MIME
por si sola no valida nada: se podia guardar un .html o un .php declarando
application/pdf. Y la extension salia del nombre de archivo del cliente, con lo
que un nombre con barras terminaba en un FileNotFoundError sin manejar.
"""
import asyncio
import io
import os
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from v2.models.documento_usuario import DocumentoUsuario
from v2.models.enums import TipoDocumento, RolUsuario
from v2.services.local_file_service import LocalFileService
from sqlmodel import select


PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + b"IHDR" + b"\x00" * 40
GIF = b"GIF89a" + b"\x00" * 20
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 20
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 20
HTML = b"<html><script>alert(1)</script></html>"
PHP = b"<?php system($_GET[0]); ?>"


@pytest.fixture(name="carpeta_docs")
def fixture_carpeta_docs(monkeypatch):
    """Directorio temporal para no escribir en el almacenamiento real."""
    with tempfile.TemporaryDirectory(prefix="docs_test_") as carpeta:
        monkeypatch.setenv("DOCUMENTOS_BASE_PATH", carpeta)
        yield Path(carpeta)


def subir(session, carpeta_docs, filename, content_type, contenido):
    archivo = UploadFile(
        filename=filename,
        file=io.BytesIO(contenido),
        headers=Headers({"content-type": content_type}),
    )
    service = LocalFileService()
    return asyncio.run(service.upload(
        archivo=archivo, usuario_id=1, nombre="Juan", apellido="Perez",
        rol=RolUsuario.ESTUDIANTE, tipo=TipoDocumento.CEDULA,
        subido_por=1, session=session,
    ))


def archivos_en(carpeta):
    return sorted(p.name for p in carpeta.rglob("*") if p.is_file())


class TestDeteccionPorContenido:

    @pytest.mark.parametrize("contenido,esperado", [
        (PDF, "application/pdf"),
        (PNG, "image/png"),
        (GIF, "image/gif"),
        (WEBP, "image/webp"),
        (JPEG, "image/jpeg"),
        (HTML, None),
        (PHP, None),
        (b"", None),
    ])
    def test_detecta_el_tipo_real(self, contenido, esperado):
        assert LocalFileService.detectar_mime_real(contenido) == esperado

    def test_webp_no_es_un_prefijo_continuo(self):
        """La firma de WebP es RIFF + tamanio + WEBP, no un prefijo corrido."""
        assert LocalFileService.detectar_mime_real(b"RIFF") is None
        assert LocalFileService.detectar_mime_real(WEBP) == "image/webp"


class TestRechazoDeArchivosDisfrazados:

    def test_html_declarado_como_pdf(self, session, carpeta_docs):
        with pytest.raises(HTTPException) as exc:
            subir(session, carpeta_docs, "evil.html", "application/pdf", HTML)
        assert exc.value.status_code == 400
        assert "no corresponde" in exc.value.detail
        assert archivos_en(carpeta_docs) == []

    def test_php_declarado_como_pdf(self, session, carpeta_docs):
        with pytest.raises(HTTPException) as exc:
            subir(session, carpeta_docs, "shell.php", "application/pdf", PHP)
        assert exc.value.status_code == 400
        assert archivos_en(carpeta_docs) == []

    def test_html_declarado_como_imagen(self, session, carpeta_docs):
        with pytest.raises(HTTPException) as exc:
            subir(session, carpeta_docs, "foto.png", "image/png", HTML)
        assert exc.value.status_code == 400

    def test_contenido_valido_pero_tipo_que_no_coincide(self, session, carpeta_docs):
        """Un PDF real declarado como PNG tambien se rechaza."""
        with pytest.raises(HTTPException) as exc:
            subir(session, carpeta_docs, "x.pdf", "image/png", PDF)
        assert exc.value.status_code == 400
        assert "pero su contenido es" in exc.value.detail

    def test_mime_fuera_de_la_whitelist(self, session, carpeta_docs):
        with pytest.raises(HTTPException) as exc:
            subir(session, carpeta_docs, "x.exe", "application/x-msdownload", PDF)
        assert exc.value.status_code == 400
        assert "no permitido" in exc.value.detail


class TestNombreDeArchivo:

    @pytest.mark.parametrize("filename", [
        "x.pdf/../../../../evil.txt",
        "a.b/../../../evil",
        "../../../../etc/passwd",
        "sin_extension",
        "raro.HTML",
    ])
    def test_la_extension_no_sale_del_nombre_del_cliente(
        self, session, carpeta_docs, filename
    ):
        """
        Un PDF valido siempre se guarda como .pdf, sin importar como se llame el
        archivo original. Antes la extension salia del nombre y permitia .html,
        y un nombre con barras reventaba con un 500.
        """
        subir(session, carpeta_docs, filename, "application/pdf", PDF)

        guardados = archivos_en(carpeta_docs)
        assert len(guardados) == 1
        assert guardados[0].endswith(".pdf")

    def test_nada_escapa_del_directorio_base(self, session, carpeta_docs):
        subir(session, carpeta_docs, "../../../../evil.pdf", "application/pdf", PDF)

        escapados = list(carpeta_docs.parent.glob("evil*"))
        assert escapados == []

    def test_el_nombre_original_se_conserva_en_la_base(self, session, carpeta_docs):
        """Se guarda como dato, para mostrarlo, pero no se usa para el path."""
        subir(session, carpeta_docs, "mi cedula.pdf", "application/pdf", PDF)

        doc = session.exec(select(DocumentoUsuario)).first()
        assert doc.nombre_original == "mi cedula.pdf"
        assert doc.ruta_relativa.endswith(".pdf")
        assert ".." not in doc.ruta_relativa

    def test_subir_dos_veces_no_pisa_el_anterior(self, session, carpeta_docs):
        subir(session, carpeta_docs, "a.pdf", "application/pdf", PDF)
        subir(session, carpeta_docs, "b.pdf", "application/pdf", PDF)

        assert len(archivos_en(carpeta_docs)) == 2


class TestLimites:

    def test_archivo_demasiado_grande(self, session, carpeta_docs, monkeypatch):
        monkeypatch.setenv("DOCUMENTOS_MAX_SIZE_MB", "1")
        grande = PDF + b"\x00" * (2 * 1024 * 1024)

        with pytest.raises(HTTPException) as exc:
            subir(session, carpeta_docs, "grande.pdf", "application/pdf", grande)
        assert exc.value.status_code == 400
        assert "demasiado grande" in exc.value.detail
