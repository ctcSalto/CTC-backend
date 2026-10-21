"""
Archivos descargables de la oferta academica (v1, careers): validacion por
contenido, disco y los tres endpoints. Va en v2/tests porque es la suite que
corre `pytest` (los test_fase*.py de la raiz necesitan un servidor levantado).
"""
import io
import zipfile
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.database import get_services, get_session
from database.models.career import Area, Career, CareerType
from database.services.auth.dependencies import require_admin_role
from database.services.career_files_service import (
    ArchivoInvalido, CareerFilesService, MAX_ARCHIVOS_POR_CARRERA, detectar_extension,
)
from database.services.carrer_service import CareerService
from routes import career as rutas_career

PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 40


def zip_con(archivos: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for nombre, contenido in archivos.items():
            z.writestr(nombre, contenido)
    return buffer.getvalue()


DOCX = zip_con({"[Content_Types].xml": "<Types/>", "word/document.xml": "<w:document/>"})
XLSX = zip_con({"[Content_Types].xml": "<Types/>", "xl/workbook.xml": "<workbook/>"})
ODT = zip_con({"mimetype": "application/vnd.oasis.opendocument.text", "content.xml": "<x/>"})


class TestDeteccion:
    @pytest.mark.parametrize("contenido, nombre, esperada", [
        (PDF, "programa.pdf", "pdf"),
        (PDF, "programa.docx", "pdf"),          # manda el contenido, no el nombre
        (DOCX, "plan.docx", "docx"),
        (XLSX, "costos", "xlsx"),
        (ODT, "plan.odt", "odt"),
        (OLE, "plan viejo.doc", "doc"),
        (OLE, "planilla.XLS", "xls"),
        (PNG, "folleto.png", "png"),
        (b"\xff\xd8\xff\xe0" + b"\x00" * 10, "foto.jpg", "jpg"),
    ])
    def test_acepta(self, contenido, nombre, esperada):
        assert detectar_extension(contenido, nombre) == esperada

    @pytest.mark.parametrize("contenido, nombre", [
        (b"<html><script>alert(1)</script></html>", "programa.pdf"),
        (zip_con({"virus.exe": "MZ"}), "programa.zip"),
        (OLE, "programa.exe"),                  # OLE que no dice ser Office
        (b"MZ\x90\x00", "instalador.exe"),
        (b"PK\x03\x04roto", "plan.docx"),
    ])
    def test_rechaza(self, contenido, nombre):
        assert detectar_extension(contenido, nombre) is None


class TestServicio:
    def test_valida_tamano_y_vacio(self, tmp_path):
        servicio = CareerFilesService(base_path=str(tmp_path), base_url="", max_mb=1)
        with pytest.raises(ArchivoInvalido, match="vacio"):
            servicio.validar(b"", "a.pdf")
        with pytest.raises(ArchivoInvalido, match="1 MB"):
            servicio.validar(b"%PDF-" + b"0" * (1024 * 1024 + 1), "grande.pdf")
        with pytest.raises(ArchivoInvalido, match="Se aceptan: .*pdf"):
            servicio.validar(b"hola", "nota.txt")

    def test_guarda_sirve_y_borra(self, tmp_path):
        servicio = CareerFilesService(base_path=str(tmp_path), base_url="https://api.ctc.uy/")
        url, = servicio.guardar(7, [servicio.validar(PDF, "Plan de Estudios 2026 (versión final).pdf")])
        assert url.startswith("https://api.ctc.uy/careers/files/7/")
        assert url.endswith("_plan_de_estudios_2026_version_final.pdf")

        nombre = servicio.nombre_de_url(7, url)
        ruta, tipo, en_navegador, para_descargar = servicio.ruta(7, nombre)
        assert ruta.read_bytes() == PDF
        assert (tipo, en_navegador, para_descargar) == ("application/pdf", True, "plan_de_estudios_2026_version_final.pdf")

        servicio.borrar(7, nombre)
        assert servicio.ruta(7, nombre) is None

    @pytest.mark.parametrize("nombre", ["../../etc/passwd", "..%2F..%2Fx.pdf", "abc.pdf", "0123abcd_x.html",
                                        "0123abcd_../x.pdf", "0123abcd_x.pdf/.."])
    def test_nombres_peligrosos_no_llegan_al_disco(self, tmp_path, nombre):
        servicio = CareerFilesService(base_path=str(tmp_path), base_url="")
        assert servicio.ruta(1, nombre) is None

    def test_la_url_tiene_que_ser_de_esa_carrera(self, tmp_path):
        servicio = CareerFilesService(base_path=str(tmp_path), base_url="https://x")
        url, = servicio.guardar(3, [servicio.validar(PDF, "a.pdf")])
        assert servicio.nombre_de_url(4, url) is None


# ── Endpoints ────────────────────────────────────────────────────────────────

@pytest.fixture(name="cliente")
def fixture_cliente(engine, session, tmp_path):
    carrera = Career(careerType=CareerType.COURSE, area=Area.IT, name="Excel", subtitle="Curso",
                     aboutCourse1="...", imageLink="https://img", creator=1, published=True,
                     publicationDate=date(2026, 1, 1))
    session.add(carrera)
    session.commit()
    session.refresh(carrera)

    invalidaciones = []
    servicios = SimpleNamespace(
        careerService=CareerService(),
        careerFilesService=CareerFilesService(base_path=str(tmp_path), base_url="http://testserver"),
        cacheService=SimpleNamespace(invalidate_all_careers=lambda: invalidaciones.append(1)),
    )
    app = FastAPI()
    app.include_router(rutas_career.router)
    app.dependency_overrides[get_services] = lambda: servicios
    app.dependency_overrides[require_admin_role] = lambda: SimpleNamespace(userId=1, email="admin@ctc")

    from sqlmodel import Session

    def sesion():
        with Session(engine) as s:
            yield s
    app.dependency_overrides[get_session] = sesion
    return SimpleNamespace(http=TestClient(app), career_id=carrera.careerId, invalidaciones=invalidaciones,
                           servicios=servicios)


class TestEndpoints:
    def test_subir_descargar_y_quitar(self, cliente):
        c = cliente
        r = c.http.post(f"/careers/{c.career_id}/files", files=[
            ("files", ("Programa 2026.pdf", PDF, "application/pdf")),
            ("files", ("Plan.docx", DOCX, "application/octet-stream")),
        ])
        assert r.status_code == 200, r.text
        urls = r.json()["files"]
        assert len(urls) == 2 and c.invalidaciones

        # Publico: el PDF se abre en el navegador, el Word se descarga
        pdf = c.http.get(urls[0].replace("http://testserver", ""))
        assert pdf.status_code == 200 and pdf.content == PDF
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.headers["content-disposition"].startswith("inline")
        assert pdf.headers["x-content-type-options"] == "nosniff"
        word = c.http.get(urls[1].replace("http://testserver", ""))
        assert word.headers["content-disposition"].startswith("attachment")
        assert "plan.docx" in word.headers["content-disposition"]

        r = c.http.delete(f"/careers/{c.career_id}/files", params={"url": urls[0]})
        assert r.status_code == 200 and r.json()["files"] == [urls[1]]
        assert c.http.get(urls[0].replace("http://testserver", "")).status_code == 404

    def test_uno_invalido_no_guarda_ninguno(self, cliente):
        c = cliente
        r = c.http.post(f"/careers/{c.career_id}/files", files=[
            ("files", ("bien.pdf", PDF, "application/pdf")),
            ("files", ("trucho.pdf", b"<html></html>", "application/pdf")),
        ])
        assert r.status_code == 400 and "trucho.pdf" in r.json()["detail"]
        carpeta = c.servicios.careerFilesService.base_path / str(c.career_id)
        assert not carpeta.exists() or not any(carpeta.iterdir())

    def test_tope_de_archivos(self, cliente):
        c = cliente
        r = c.http.post(f"/careers/{c.career_id}/files",
                        files=[("files", (f"a{i}.pdf", PDF, "application/pdf"))
                               for i in range(MAX_ARCHIVOS_POR_CARRERA + 1)])
        assert r.status_code == 400 and "hasta" in r.json()["detail"]

    def test_quitar_una_url_ajena(self, cliente):
        r = cliente.http.delete(f"/careers/{cliente.career_id}/files", params={"url": "https://otro/x.pdf"})
        assert r.status_code == 404

    def test_carrera_inexistente(self, cliente):
        r = cliente.http.post("/careers/9999/files", files=[("files", ("a.pdf", PDF, "application/pdf"))])
        assert r.status_code == 404

    def test_reordenar_y_quitar_de_paso(self, cliente):
        c = cliente
        urls = c.http.post(f"/careers/{c.career_id}/files", files=[
            ("files", (f"a{i}.pdf", PDF, "application/pdf")) for i in range(3)]).json()["files"]
        r = c.http.put(f"/careers/{c.career_id}/files", json={"files": [urls[2], urls[0]]})
        assert r.status_code == 200 and r.json()["files"] == [urls[2], urls[0]]
        # La que no vino se borro del disco
        assert c.http.get(urls[1].replace("http://testserver", "")).status_code == 404
        assert c.http.get(urls[0].replace("http://testserver", "")).status_code == 200

    def test_reordenar_no_acepta_urls_ajenas_ni_repetidas(self, cliente):
        c = cliente
        url, = c.http.post(f"/careers/{c.career_id}/files",
                           files=[("files", ("a.pdf", PDF, "application/pdf"))]).json()["files"]
        assert c.http.put(f"/careers/{c.career_id}/files", json={"files": [url, "https://otro/x.pdf"]}).status_code == 400
        assert c.http.put(f"/careers/{c.career_id}/files", json={"files": [url, url]}).status_code == 400

    def test_reemplazar_en_la_misma_posicion(self, cliente):
        c = cliente
        urls = c.http.post(f"/careers/{c.career_id}/files", files=[
            ("files", ("viejo.pdf", PDF, "application/pdf")),
            ("files", ("otro.pdf", PDF, "application/pdf"))]).json()["files"]
        r = c.http.put(f"/careers/{c.career_id}/files/replace", params={"url": urls[0]},
                       files={"file": ("Plan nuevo.docx", DOCX, "application/octet-stream")})
        assert r.status_code == 200, r.text
        nuevas = r.json()["files"]
        assert nuevas[1] == urls[1] and nuevas[0].endswith("_plan_nuevo.docx")
        assert c.http.get(urls[0].replace("http://testserver", "")).status_code == 404
        assert c.http.get(nuevas[0].replace("http://testserver", "")).status_code == 200

    def test_reemplazar_con_un_tipo_invalido_no_toca_nada(self, cliente):
        c = cliente
        url, = c.http.post(f"/careers/{c.career_id}/files",
                           files=[("files", ("a.pdf", PDF, "application/pdf"))]).json()["files"]
        r = c.http.put(f"/careers/{c.career_id}/files/replace", params={"url": url},
                       files={"file": ("trucho.pdf", b"<html></html>", "application/pdf")})
        assert r.status_code == 400
        assert c.http.get(url.replace("http://testserver", "")).status_code == 200
