"""
CERTIX en la oferta academica (v1, careers): el respaldo de la division de
certificados del instituto. Es un booleano aparte del tipo de oferta: se tiene
que poder cargar, editar, ver en las respuestas y recuperar por filtros.
"""
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from database.database import get_services, get_session
from database.models.career import Area, Career, CareerType
from database.services.auth.dependencies import require_admin_role
from database.services.career_files_service import CareerFilesService
from database.services.carrer_service import CareerService
from routes import career as rutas_career


class CacheFalso:
    """Sin Redis: nada esta cacheado y guardar no hace nada."""
    def __getattr__(self, nombre):
        return lambda *a, **k: None


def carrera(nombre, tipo=CareerType.CAREER, certix=False, publicada=True):
    return Career(careerType=tipo, area=Area.IT, name=nombre, subtitle="-", aboutCourse1="-",
                  imageLink="https://img", creator=1, published=publicada, certix=certix,
                  publicationDate=date(2026, 1, 1) if publicada else None)


@pytest.fixture(name="cliente")
def fixture_cliente(engine, session, tmp_path):
    ofertas = {
        "ap": carrera("Analista Programador", certix=True),
        "excel": carrera("Excel", CareerType.COURSE, certix=True),
        "tgde": carrera("TGDE"),
        "borrador": carrera("Borrador CERTIX", certix=True, publicada=False),
    }
    session.add_all(ofertas.values())
    session.commit()
    ids = {k: v.careerId for k, v in ofertas.items()}

    servicios = SimpleNamespace(
        careerService=CareerService(), cacheService=CacheFalso(),
        careerFilesService=CareerFilesService(base_path=str(tmp_path), base_url="http://testserver"),
        supabaseService=SimpleNamespace(upload_image=_subir_imagen, rollback=lambda **k: None),
    )
    app = FastAPI()
    app.include_router(rutas_career.router)
    app.dependency_overrides[get_services] = lambda: servicios
    app.dependency_overrides[require_admin_role] = lambda: SimpleNamespace(userId=1, email="admin@ctc")

    def sesion():
        with Session(engine) as s:
            yield s
    app.dependency_overrides[get_session] = sesion
    return SimpleNamespace(http=TestClient(app), ids=ids)


async def _subir_imagen(image, folder):
    return "https://img/nueva.webp"


def ids_de(respuesta):
    """Los filtros devuelven una lista o un objeto con `data`: el test no depende de eso."""
    datos = respuesta.get("data", respuesta) if isinstance(respuesta, dict) else respuesta
    return {c["careerId"] for c in datos}


def filtro(*condiciones, **extra):
    return {"conditions": list(condiciones), "limit": 100, **extra}


CERTIX = {"attribute": "certix", "operator": "eq", "value": True}


class TestFiltros:
    def test_publico_trae_solo_las_publicadas_con_certix(self, cliente):
        r = cliente.http.post("/careers/public/filters", json=filtro(CERTIX))
        assert r.status_code == 200, r.text
        assert ids_de(r.json()) == {cliente.ids["ap"], cliente.ids["excel"]}

    def test_admin_trae_tambien_los_borradores(self, cliente):
        r = cliente.http.post("/careers/admin/filters", json=filtro(CERTIX))
        assert r.status_code == 200, r.text
        assert ids_de(r.json()) == {cliente.ids["ap"], cliente.ids["excel"], cliente.ids["borrador"]}

    def test_combinado_con_el_tipo(self, cliente):
        r = cliente.http.post("/careers/public/filters", json=filtro(
            CERTIX, {"attribute": "careerType", "operator": "eq", "value": "career"}))
        assert ids_de(r.json()) == {cliente.ids["ap"]}

    def test_las_que_no_tienen_certix(self, cliente):
        r = cliente.http.post("/careers/public/filters",
                              json=filtro({"attribute": "certix", "operator": "eq", "value": False}))
        assert ids_de(r.json()) == {cliente.ids["tgde"]}

    def test_el_campo_viene_en_la_respuesta_de_filtros(self, cliente):
        r = cliente.http.post("/careers/public/filters", json=filtro(CERTIX, fields=["careerId", "name", "certix"]))
        datos = r.json().get("data", r.json()) if isinstance(r.json(), dict) else r.json()
        assert datos and all(c["certix"] is True for c in datos)


class TestRespuestas:
    def test_listado_publico(self, cliente):
        r = cliente.http.get("/careers/careers", params={"limit": 50})
        assert r.status_code == 200, r.text
        por_id = {c["careerId"]: c["certix"] for c in r.json()}
        assert por_id[cliente.ids["ap"]] is True and por_id[cliente.ids["tgde"]] is False

    def test_detalle_optimizado(self, cliente):
        """Se arma campo por campo: si no se agrega a mano, vendria siempre en false."""
        r = cliente.http.get(f"/careers/career-optimized/{cliente.ids['excel']}")
        assert r.status_code == 200, r.text
        assert r.json()["certix"] is True

    def test_detalle_admin(self, cliente):
        r = cliente.http.get(f"/careers/admin/{cliente.ids['borrador']}")
        assert r.status_code == 200, r.text
        assert r.json()["certix"] is True


class TestCargaYEdicion:
    def test_alta_con_certix(self, cliente):
        r = cliente.http.post("/careers/create", data={
            "name": "Soporte IT", "subtitle": "Curso", "aboutCourse1": "-", "published": "true",
            "careerType": "course", "area": "it", "certix": "true",
        }, files={"image": ("img.png", b"\x89PNG\r\n\x1a\n", "image/png")})
        assert r.status_code == 201, r.text
        assert r.json()["certix"] is True

    def test_alta_sin_decir_nada_queda_sin_certix(self, cliente):
        r = cliente.http.post("/careers/create", data={
            "name": "Corel", "subtitle": "Curso", "aboutCourse1": "-", "published": "false",
        }, files={"image": ("img.png", b"\x89PNG\r\n\x1a\n", "image/png")})
        assert r.status_code == 201, r.text
        assert r.json()["certix"] is False

    def test_editar_prende_y_apaga(self, cliente):
        cid = cliente.ids["tgde"]
        r = cliente.http.put(f"/careers/{cid}", json={"certix": True})
        assert r.status_code == 200, r.text
        assert r.json()["certix"] is True
        # Editar otra cosa no lo toca
        r = cliente.http.put(f"/careers/{cid}", json={"subtitle": "Nuevo"})
        assert r.json()["certix"] is True
        r = cliente.http.put(f"/careers/{cid}", json={"certix": False})
        assert r.json()["certix"] is False
