"""
Guard de configuracion critica al arrancar.

Existe por un patron que ya nos costo caro: un default silencioso tapando una
mala configuracion. Si SECRET_KEY falta, el codigo cae a un literal publicado en
el repositorio y la app arranca normal firmando los JWT con esa clave.
"""
import pytest

from utils.config_guard import (
    PLACEHOLDER_SECRET_KEY,
    es_produccion,
    revisar_configuracion_critica,
    exigir_configuracion_critica,
)


class TestFueraDeProduccion:
    """En desarrollo los defaults son comodos y no hay nada que proteger."""

    @pytest.mark.parametrize("entorno", ["development", "staging", "", "DEVELOPMENT"])
    def test_no_se_queja_de_nada(self, monkeypatch, entorno):
        monkeypatch.setenv("ENVIRONMENT", entorno)
        monkeypatch.delenv("SECRET_KEY", raising=False)

        assert revisar_configuracion_critica() == []
        exigir_configuracion_critica()  # no levanta

    def test_sin_variable_environment(self, monkeypatch):
        """Sin ENVIRONMENT seteada se asume desarrollo."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("SECRET_KEY", raising=False)

        assert es_produccion() is False
        assert revisar_configuracion_critica() == []


class TestEnProduccion:

    def test_secret_key_ausente(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("SECRET_KEY", raising=False)

        problemas = revisar_configuracion_critica()
        assert len(problemas) == 1
        assert "SECRET_KEY no esta definida" in problemas[0]

        with pytest.raises(RuntimeError, match="no arranca"):
            exigir_configuracion_critica()

    def test_secret_key_vacia(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("SECRET_KEY", "")

        with pytest.raises(RuntimeError):
            exigir_configuracion_critica()

    def test_secret_key_con_el_placeholder_del_repo(self, monkeypatch):
        """El caso que motiva el guard: el literal esta publicado."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("SECRET_KEY", PLACEHOLDER_SECRET_KEY)

        problemas = revisar_configuracion_critica()
        assert len(problemas) == 1
        assert "placeholder" in problemas[0]

        with pytest.raises(RuntimeError, match="placeholder"):
            exigir_configuracion_critica()

    def test_secret_key_real_pasa(self, monkeypatch):
        """Una clave propia arranca sin ruido, sea del largo que sea."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("SECRET_KEY", "una-clave-propia-del-despliegue")

        assert revisar_configuracion_critica() == []
        exigir_configuracion_critica()  # no levanta

    def test_environment_no_distingue_mayusculas(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "PRODUCTION")
        monkeypatch.delenv("SECRET_KEY", raising=False)

        assert es_produccion() is True
        with pytest.raises(RuntimeError):
            exigir_configuracion_critica()

    def test_el_mensaje_dice_que_hacer(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("SECRET_KEY", raising=False)

        with pytest.raises(RuntimeError) as exc:
            exigir_configuracion_critica()

        mensaje = str(exc.value)
        assert "variables de entorno" in mensaje
        assert "SECRET_KEY" in mensaje
