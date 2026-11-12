"""
Oferta académica por tipo (v1, careers): GET /careers/type/{tipo} (público) y
GET /careers/admin/type/{tipo} (admin). Antes daban 500 con cualquier tipo
porque CareerService no tenía get_careers_by_type.
"""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from database.database import get_services, get_session
from database.models.career import Area, Career, CareerType
from database.services.auth.dependencies import require_admin_role
from database.services.carrer_service import CareerService
from routes import career as rutas_career


class CacheFalso:
    """Sin Redis: nada está cacheado y guardar no hace nada."""
    def __getattr__(self, nombre):
        return lambda *a, **k: None


def oferta(nombre, tipo, publicada=True, fecha=date(2026, 1, 1)):
    return Career(careerType=tipo, area=Area.IT, name=nombre, subtitle="-", aboutCourse1="-",
                  imageLink="https://img", creator=1, published=publicada, publicationDate=fecha)


@pytest.fixture(name="cliente")
def fixture_cliente(engine, session):
    ofertas = {
        "ap": oferta("Analista Programador", CareerType.CAREER),
        "tgde": oferta("TGDE", CareerType.CAREER, fecha=None),
        "borrador": oferta("Borrador", CareerType.CAREER, publicada=False, fecha=None),
        "futura": oferta("Publica el año que viene", CareerType.CAREER, fecha=date.today() + timedelta(days=365)),
        "excel": oferta("Excel", CareerType.COURSE),
        "certix": oferta("Certificación X", CareerType.CERTIX),
    }
    session.add_all(ofertas.values())
    session.commit()
    ids = {k: v.careerId for k, v in ofertas.items()}

    servicios = SimpleNamespace(careerService=CareerService(), cacheService=CacheFalso())
    app = FastAPI()
    app.include_router(rutas_career.router)
    app.dependency_overrides[get_services] = lambda: servicios
    app.dependency_overrides[require_admin_role] = lambda: SimpleNamespace(userId=1, email="admin@ctc")

    def sesion():
        with Session(engine) as s:
            yield s
    app.dependency_overrides[get_session] = sesion
    return SimpleNamespace(http=TestClient(app), ids=ids)


def ids_de(r):
    assert r.status_code == 200, r.text
    return [c["careerId"] for c in r.json()]


class TestPublico:
    def test_solo_publicadas_y_ya_vigentes(self, cliente):
        """Ni borradores ni las que tienen fecha de publicación futura; la fecha nula sí."""
        r = cliente.http.get("/careers/type/career")
        assert ids_de(r) == [cliente.ids["ap"], cliente.ids["tgde"]]

    def test_solo_del_tipo_pedido(self, cliente):
        assert ids_de(cliente.http.get("/careers/type/course")) == [cliente.ids["excel"]]
        r = cliente.http.get("/careers/type/certix")
        assert ids_de(r) == [cliente.ids["certix"]]
        assert r.json()[0]["careerType"] == "certix"

    def test_tipo_sin_ofertas(self, cliente):
        assert ids_de(cliente.http.get("/careers/type/workshop")) == []

    def test_paginacion_sobre_las_visibles(self, cliente):
        """El filtro va en la consulta: la segunda página no se 'come' los borradores."""
        assert ids_de(cliente.http.get("/careers/type/career", params={"limit": 1})) == [cliente.ids["ap"]]
        r = cliente.http.get("/careers/type/career", params={"offset": 1, "limit": 1})
        assert ids_de(r) == [cliente.ids["tgde"]]

    def test_tipo_invalido(self, cliente):
        assert cliente.http.get("/careers/type/inexistente").status_code == 422


class TestAdmin:
    def test_trae_tambien_borradores_y_futuras(self, cliente):
        r = cliente.http.get("/careers/admin/type/career")
        i = cliente.ids
        assert ids_de(r) == [i["ap"], i["tgde"], i["borrador"], i["futura"]]

    def test_paginacion(self, cliente):
        r = cliente.http.get("/careers/admin/type/career", params={"offset": 2, "limit": 5})
        assert ids_de(r) == [cliente.ids["borrador"], cliente.ids["futura"]]

    def test_otros_tipos(self, cliente):
        assert ids_de(cliente.http.get("/careers/admin/type/certix")) == [cliente.ids["certix"]]
        assert ids_de(cliente.http.get("/careers/admin/type/diploma")) == []
