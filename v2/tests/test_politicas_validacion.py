"""
Validacion de coherencia de las politicas.

El motor evalua la exoneracion antes que el examen, asi que una politica con los
umbrales cruzados hace exonerar a quien deberia ir a examen, sin ningun error
visible. Estos tests fijan las reglas que impiden cargar esas politicas.
"""
import pytest
from decimal import Decimal

from v2.models.politica_calificacion import (
    PoliticaCalificacionCreate, PoliticaCalificacionUpdate,
)
from v2.models.politica_examen import PoliticaExamenCreate, PoliticaExamenUpdate
from v2.services.politica_calificacion_service import PoliticaCalificacionService
from v2.services.politica_examen_service import PoliticaExamenService


def politica_ctc(**overrides):
    """La politica real de CTC: <70 reprueba, 70-85 examen, 86+ exonera."""
    base = dict(
        nombre="Base 100 - Carrera AP",
        nota_maxima=Decimal("100"),
        umbral_aprobacion=Decimal("70"),
        umbral_examen=Decimal("70"),
        umbral_exoneracion=Decimal("86"),
    )
    base.update(overrides)
    return PoliticaCalificacionCreate(**base)


class TestPoliticasRealesSiguenSiendoValidas:
    """Las politicas cargadas hoy en develop no deben quedar fuera de norma."""

    def test_politica_carrera_ap(self, session):
        pol = PoliticaCalificacionService().create(politica_ctc(), session)
        assert pol.id is not None

    def test_politica_curso_corto(self, session):
        """Sin umbral_examen ni exoneracion: aprobacion directa."""
        pol = PoliticaCalificacionService().create(
            PoliticaCalificacionCreate(
                nombre="Base 100 - Curso Corto",
                nota_maxima=Decimal("100"),
                umbral_aprobacion=Decimal("70"),
            ),
            session,
        )
        assert pol.umbral_examen is None

    def test_politica_examen_estandar(self, session):
        pol = PoliticaExamenService().create(
            PoliticaExamenCreate(
                nombre="Examen estandar base 100",
                nota_maxima=Decimal("100"),
                umbral_aprobacion=Decimal("70"),
                max_oportunidades=5,
            ),
            session,
        )
        assert pol.max_oportunidades == 5


class TestUmbralesIncoherentes:

    def test_exoneracion_por_debajo_del_examen(self, session):
        """El caso que motiva la validacion: se exonera antes de ir a examen."""
        with pytest.raises(ValueError, match="umbral_exoneracion"):
            PoliticaCalificacionService().create(
                politica_ctc(umbral_examen=Decimal("86"),
                             umbral_exoneracion=Decimal("70")),
                session,
            )

    def test_exoneracion_igual_al_examen(self, session):
        """Iguales tampoco: nadie llegaria nunca a A_EXAMEN."""
        with pytest.raises(ValueError, match="umbral_exoneracion"):
            PoliticaCalificacionService().create(
                politica_ctc(umbral_examen=Decimal("80"),
                             umbral_exoneracion=Decimal("80")),
                session,
            )

    @pytest.mark.parametrize("campo", [
        "umbral_aprobacion", "umbral_examen", "umbral_exoneracion",
    ])
    def test_umbral_mayor_a_nota_maxima(self, session, campo):
        with pytest.raises(ValueError, match="inalcanzable"):
            PoliticaCalificacionService().create(
                politica_ctc(**{campo: Decimal("150")}), session
            )

    def test_umbral_aprobacion_en_cero(self, session):
        """En 0 cualquier nota aprueba, incluido un 0."""
        with pytest.raises(ValueError, match="umbral_aprobacion"):
            PoliticaCalificacionService().create(
                politica_ctc(umbral_aprobacion=Decimal("0"),
                             umbral_examen=None, umbral_exoneracion=None),
                session,
            )

    def test_nota_maxima_en_cero(self, session):
        with pytest.raises(ValueError, match="nota_maxima"):
            PoliticaCalificacionService().create(
                politica_ctc(nota_maxima=Decimal("0")), session
            )

    def test_umbral_negativo(self, session):
        with pytest.raises(ValueError, match="negativo"):
            PoliticaCalificacionService().create(
                politica_ctc(umbral_examen=Decimal("-10")), session
            )


class TestUpdateValidaElCombinado:
    """Un update parcial puede romper la coherencia sin mandar todos los campos."""

    def test_update_de_un_solo_umbral_es_rechazado(self, session):
        service = PoliticaCalificacionService()
        pol = service.create(politica_ctc(), session)

        # Solo se manda umbral_examen=90, pero la exoneracion guardada es 86
        with pytest.raises(ValueError, match="umbral_exoneracion"):
            service.update(
                pol.id,
                PoliticaCalificacionUpdate(umbral_examen=Decimal("90")),
                session,
            )

    def test_la_politica_no_queda_modificada_tras_el_rechazo(self, session):
        """Si la validacion falla, el objeto no debe quedar sucio en la sesion."""
        service = PoliticaCalificacionService()
        pol = service.create(politica_ctc(), session)

        with pytest.raises(ValueError):
            service.update(
                pol.id,
                PoliticaCalificacionUpdate(umbral_examen=Decimal("90")),
                session,
            )

        session.rollback()
        recargada = service.get_by_id(pol.id, session)
        assert recargada.umbral_examen == Decimal("70")

    def test_update_coherente_pasa(self, session):
        service = PoliticaCalificacionService()
        pol = service.create(politica_ctc(), session)

        actualizada = service.update(
            pol.id,
            PoliticaCalificacionUpdate(umbral_exoneracion=Decimal("90")),
            session,
        )
        assert actualizada.umbral_exoneracion == Decimal("90")


class TestPoliticaExamen:

    def test_umbral_mayor_a_nota_maxima(self, session):
        with pytest.raises(ValueError, match="inaprobable"):
            PoliticaExamenService().create(
                PoliticaExamenCreate(
                    nombre="Rota", nota_maxima=Decimal("100"),
                    umbral_aprobacion=Decimal("120"), max_oportunidades=5,
                ),
                session,
            )

    def test_sin_oportunidades(self, session):
        with pytest.raises(ValueError, match="max_oportunidades"):
            PoliticaExamenService().create(
                PoliticaExamenCreate(
                    nombre="Rota", nota_maxima=Decimal("100"),
                    umbral_aprobacion=Decimal("70"), max_oportunidades=0,
                ),
                session,
            )

    def test_update_valida_el_combinado(self, session):
        service = PoliticaExamenService()
        pol = service.create(
            PoliticaExamenCreate(
                nombre="Examen", nota_maxima=Decimal("100"),
                umbral_aprobacion=Decimal("70"), max_oportunidades=5,
            ),
            session,
        )
        # Bajar la nota maxima por debajo del umbral guardado
        with pytest.raises(ValueError, match="inaprobable"):
            service.update(
                pol.id, PoliticaExamenUpdate(nota_maxima=Decimal("50")), session
            )
