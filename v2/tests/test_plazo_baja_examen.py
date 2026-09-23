"""
Plazo para darse de baja de un examen: 24 horas antes (regla de bedelia,
23/09/2026; antes el default era 72).

Quien no se da de baja a tiempo y no se presenta queda AUSENTE (el NSP de
bedelia): cuenta como actividad rendida, con 0 en el promedio de la
escolaridad, y gasta una oportunidad de examen.
"""
import os
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from v2.models.enums import (
    EstadoInscripcionExamen as EE, EstadoInscripcionMateria as EM, EstadoInstanciaCursado,
)
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.services.inscripcion_examen_service import InscripcionExamenService
from v2.services import promedio_escolaridad as pe

SERVICIO = InscripcionExamenService()


def ahora_naive():
    return datetime.now(ZoneInfo(os.environ.get("TIME_ZONE", "America/Montevideo"))).replace(tzinfo=None)


@pytest.fixture(name="inscripto_a")
def fixture_inscripto_a(session, alumno, materias_con_previaturas):
    """Devuelve una funcion: inscripto a un examen que es dentro de N horas."""
    p1 = materias_con_previaturas["prog1"]

    def armar(horas_hasta_el_examen: float) -> InscripcionExamen:
        ic = InstanciaCursado(materia_id=p1.id, anio_lectivo=2026, estado=EstadoInstanciaCursado.FINALIZADA)
        session.add(ic)
        session.flush()
        insc = InscripcionMateria(alumno_id=alumno.id, instancia_cursado_id=ic.id, estado=EM.A_EXAMEN)
        session.add(insc)
        session.flush()
        fecha = ahora_naive() + timedelta(hours=horas_hasta_el_examen)
        inst = InstanciaExamen(materia_id=p1.id, nombre="Examen", fecha_inicio_inscripcion=fecha - timedelta(days=10),
                               fecha_fin_inscripcion=fecha - timedelta(days=2), fecha_examen=fecha, habilitado=True)
        session.add(inst)
        session.flush()
        ie = InscripcionExamen(inscripcion_materia_id=insc.id, instancia_examen_id=inst.id, estado=EE.INSCRIPTO)
        session.add(ie)
        session.commit()
        session.refresh(ie)
        return ie
    return armar


class TestPlazoDeBaja:
    def test_se_puede_hasta_24_horas_antes(self, session, inscripto_a, monkeypatch):
        monkeypatch.delenv("PLAZO_BAJA_EXAMEN_HORAS", raising=False)
        ie = inscripto_a(25)
        SERVICIO.desinscribir_examen(ie.id, session)
        session.refresh(ie)
        assert ie.estado == EE.BAJA and ie.fecha_baja is not None

    def test_con_menos_de_24_horas_no(self, session, inscripto_a, monkeypatch):
        monkeypatch.delenv("PLAZO_BAJA_EXAMEN_HORAS", raising=False)
        ie = inscripto_a(23)
        with pytest.raises(ValueError, match="24 horas"):
            SERVICIO.desinscribir_examen(ie.id, session)
        session.refresh(ie)
        assert ie.estado == EE.INSCRIPTO

    def test_ya_no_son_72(self, session, inscripto_a, monkeypatch):
        """Con el default viejo, a 48 horas se rechazaba."""
        monkeypatch.delenv("PLAZO_BAJA_EXAMEN_HORAS", raising=False)
        ie = inscripto_a(48)
        SERVICIO.desinscribir_examen(ie.id, session)
        session.refresh(ie)
        assert ie.estado == EE.BAJA

    def test_se_puede_configurar(self, session, inscripto_a, monkeypatch):
        monkeypatch.setenv("PLAZO_BAJA_EXAMEN_HORAS", "72")
        ie = inscripto_a(48)
        with pytest.raises(ValueError, match="72 horas"):
            SERVICIO.desinscribir_examen(ie.id, session)


class TestNSP:
    def test_el_ausente_cuenta_cero_y_gasta_una_oportunidad(self, session, inscripto_a):
        """No se dio de baja y no se presento: NSP."""
        ie = inscripto_a(-2)          # el examen fue hace dos horas
        SERVICIO.marcar_ausente(ie.id, session)
        session.refresh(ie)
        assert ie.estado == EE.AUSENTE

        act = pe.actividad_de_examen(ie, "PROGRAMACION 1", None)
        assert (act.resultado, act.nota_promedio, act.peso) == ("NSP", 0.0, 1)
        assert SERVICIO._contar_rendiciones_previas(ie.inscripcion_materia_id, session) == 1

    def test_la_baja_a_tiempo_no_es_actividad(self, session, inscripto_a):
        ie = inscripto_a(30)
        SERVICIO.desinscribir_examen(ie.id, session)
        session.refresh(ie)
        assert pe.actividad_de_examen(ie, "PROGRAMACION 1", None) is None
        assert SERVICIO._contar_rendiciones_previas(ie.inscripcion_materia_id, session) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Cierre de acta: el NSP se marca solo, al cerrar
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(name="examen_pasado")
def fixture_examen_pasado(session, alumno, materias_con_previaturas):
    """
    Un examen de ayer con tres inscriptos del mismo alumno en tres cursadas
    distintas (para no tener que crear alumnos): uno aprobado, uno que se dio
    de baja y uno que no hizo nada.
    """
    p1 = materias_con_previaturas["prog1"]
    fecha = ahora_naive() - timedelta(days=1)
    inst = InstanciaExamen(materia_id=p1.id, nombre="Examen de ayer", fecha_inicio_inscripcion=fecha - timedelta(days=10),
                           fecha_fin_inscripcion=fecha - timedelta(days=2), fecha_examen=fecha, habilitado=True)
    session.add(inst)
    session.flush()

    def inscripcion(estado, max_oportunidades=5):
        ic = InstanciaCursado(materia_id=p1.id, anio_lectivo=2026, estado=EstadoInstanciaCursado.FINALIZADA)
        session.add(ic)
        session.flush()
        im = InscripcionMateria(alumno_id=alumno.id, instancia_cursado_id=ic.id, estado=EM.A_EXAMEN)
        session.add(im)
        session.flush()
        ie = InscripcionExamen(inscripcion_materia_id=im.id, instancia_examen_id=inst.id, estado=estado,
                               snapshot_politica_examen={"max_oportunidades": max_oportunidades})
        session.add(ie)
        session.flush()
        return ie

    armado = {
        "instancia": inst,
        "aprobado": inscripcion(EE.APROBADO),
        "baja": inscripcion(EE.BAJA),
        "sin_nota": inscripcion(EE.INSCRIPTO),
        "inscripcion": inscripcion,
        "materia": p1,
    }
    session.commit()
    return armado


class TestCerrarActa:
    def test_el_que_no_hizo_nada_queda_ausente(self, session, examen_pasado):
        r = SERVICIO.cerrar_acta(examen_pasado["instancia"].id, session)

        for clave in ("aprobado", "baja", "sin_nota"):
            session.refresh(examen_pasado[clave])
        assert examen_pasado["sin_nota"].estado == EE.AUSENTE
        assert examen_pasado["aprobado"].estado == EE.APROBADO       # no se toca
        assert examen_pasado["baja"].estado == EE.BAJA               # se bajo a tiempo: no es NSP
        assert [a["inscripcion_examen_id"] for a in r["marcados_ausentes"]] == [examen_pasado["sin_nota"].id]
        assert (r["aprobados"], r["ausentes"], r["bajas"]) == (1, 1, 1)

    def test_el_examen_queda_finalizado(self, session, examen_pasado):
        from v2.models.enums import EstadoInstanciaExamen
        r = SERVICIO.cerrar_acta(examen_pasado["instancia"].id, session)
        session.refresh(examen_pasado["instancia"])
        assert examen_pasado["instancia"].estado == EstadoInstanciaExamen.FINALIZADO
        assert r["estado"] == "finalizado"

    def test_cerrarla_dos_veces_no_cambia_nada(self, session, examen_pasado):
        SERVICIO.cerrar_acta(examen_pasado["instancia"].id, session)
        r = SERVICIO.cerrar_acta(examen_pasado["instancia"].id, session)
        assert r["marcados_ausentes"] == [] and r["ausentes"] == 1

    def test_no_se_cierra_antes_del_examen(self, session, inscripto_a):
        ie = inscripto_a(48)
        with pytest.raises(ValueError, match="todavia no se tomo"):
            SERVICIO.cerrar_acta(ie.instancia_examen_id, session)
        session.refresh(ie)
        assert ie.estado == EE.INSCRIPTO

    def test_no_se_cierra_un_examen_cancelado(self, session, examen_pasado):
        from v2.models.enums import EstadoInstanciaExamen
        examen_pasado["instancia"].estado = EstadoInstanciaExamen.CANCELADO
        session.add(examen_pasado["instancia"])
        session.commit()
        with pytest.raises(ValueError, match="cancelado"):
            SERVICIO.cerrar_acta(examen_pasado["instancia"].id, session)

    def test_el_docente_solo_cierra_examenes_de_su_materia(self, session, examen_pasado, materias_con_previaturas):
        otra = materias_con_previaturas["prog2"]
        with pytest.raises(ValueError, match="no es de esta materia"):
            SERVICIO.cerrar_acta(examen_pasado["instancia"].id, session, materia_id=otra.id)
        r = SERVICIO.cerrar_acta(examen_pasado["instancia"].id, session, materia_id=examen_pasado["materia"].id)
        assert len(r["marcados_ausentes"]) == 1

    def test_el_nsp_entra_al_promedio(self, session, examen_pasado):
        SERVICIO.cerrar_acta(examen_pasado["instancia"].id, session)
        session.refresh(examen_pasado["sin_nota"])
        act = pe.actividad_de_examen(examen_pasado["sin_nota"], "PROGRAMACION 1", None)
        assert (act.resultado, act.nota_promedio, act.peso) == ("NSP", 0.0, 1)


class TestAusenteGastaOportunidad:
    """
    Antes solo reprobar revisaba si se agotaron las oportunidades. Un ausente
    tambien gasta una (regla de bedelia), asi que tambien puede obligar a
    recursar.
    """

    def test_agotar_con_ausentes_obliga_a_recursar(self, session, examen_pasado):
        ie = examen_pasado["inscripcion"](EE.INSCRIPTO, max_oportunidades=1)
        session.commit()
        r = SERVICIO.cerrar_acta(examen_pasado["instancia"].id, session)

        im = session.get(InscripcionMateria, ie.inscripcion_materia_id)
        assert im.estado == EM.REPROBADO
        assert "Agotadas" in im.motivo_cierre
        agotados = {a["inscripcion_examen_id"]: a["agoto_oportunidades"] for a in r["marcados_ausentes"]}
        assert agotados[ie.id] is True
        assert agotados[examen_pasado["sin_nota"].id] is False   # le quedan

    def test_marcar_ausente_a_mano_tambien_lo_revisa(self, session, examen_pasado):
        ie = examen_pasado["inscripcion"](EE.INSCRIPTO, max_oportunidades=1)
        session.commit()
        SERVICIO.marcar_ausente(ie.id, session)
        im = session.get(InscripcionMateria, ie.inscripcion_materia_id)
        assert im.estado == EM.REPROBADO

    def test_con_oportunidades_la_materia_sigue_a_examen(self, session, examen_pasado):
        SERVICIO.marcar_ausente(examen_pasado["sin_nota"].id, session)
        im = session.get(InscripcionMateria, examen_pasado["sin_nota"].inscripcion_materia_id)
        assert im.estado == EM.A_EXAMEN


# ══════════════════════════════════════════════════════════════════════════════
# Cursos independientes: 2 oportunidades, sin fecha de caducidad
# ══════════════════════════════════════════════════════════════════════════════

class TestCursosIndependientes:
    """
    Decision de negocio (23/09/2026): los cursos independientes (anuales o
    cortos, fuera de una carrera) tienen 2 oportunidades de examen y el
    derecho NO VENCE. Hay alumnos que vuelven a los cinco años a usarlo, y si
    no se les da no vuelven. Las carreras tienen 5.

    No es codigo especial: es la politica de examen de la materia con
    max_oportunidades = 2. Este test fija que la antigüedad de la cursada no
    se mira nunca; si alguien agrega un vencimiento, se entera aca.
    """

    @pytest.fixture(name="curso_independiente")
    def fixture_curso_independiente(self, session, programa, politica_base100, alumno):
        from v2.models.materia import Materia
        from v2.models.politica_examen import PoliticaExamen
        politica = PoliticaExamen(nombre="Cursos independientes", nota_maxima=100,
                                  umbral_aprobacion=70, max_oportunidades=2)
        session.add(politica)
        session.flush()
        materia = Materia(programa_id=programa.id, nombre="Soporte Tecnico IT", codigo="STIT",
                          semestre=1, creditos=10, politica_id=politica_base100.id,
                          politica_examen_id=politica.id, activo=True)
        session.add(materia)
        session.flush()
        # Aprobo el curso hace cinco años y nunca rindio
        ic = InstanciaCursado(materia_id=materia.id, anio_lectivo=2021, semestre=2,
                              estado=EstadoInstanciaCursado.FINALIZADA)
        session.add(ic)
        session.flush()
        im = InscripcionMateria(alumno_id=alumno.id, instancia_cursado_id=ic.id, estado=EM.A_EXAMEN)
        session.add(im)
        session.commit()
        return {"materia": materia, "inscripcion": im}

    def _mesa(self, session, materia, dias):
        """Un examen con la inscripcion abierta hoy, dentro de `dias` dias."""
        ahora = ahora_naive()
        inst = InstanciaExamen(materia_id=materia.id, nombre=f"Examen +{dias}d",
                               fecha_inicio_inscripcion=ahora - timedelta(days=1),
                               fecha_fin_inscripcion=ahora + timedelta(days=1),
                               fecha_examen=ahora + timedelta(days=dias), habilitado=True)
        session.add(inst)
        session.commit()
        return inst

    def test_cinco_años_despues_puede_rendir(self, session, curso_independiente):
        inst = self._mesa(session, curso_independiente["materia"], 10)
        ie = SERVICIO.inscribir_examen(curso_independiente["inscripcion"].id, inst.id, session)
        assert ie.estado == EE.INSCRIPTO and ie.numero_rendicion == 1

    def test_tiene_dos_oportunidades_y_despues_recursa(self, session, curso_independiente):
        from decimal import Decimal
        im = curso_independiente["inscripcion"]

        primera = SERVICIO.inscribir_examen(im.id, self._mesa(session, curso_independiente["materia"], 10).id, session)
        SERVICIO.calificar_examen(primera.id, Decimal("40"), session)
        session.refresh(im)
        assert im.estado == EM.A_EXAMEN          # le queda una

        segunda = SERVICIO.inscribir_examen(im.id, self._mesa(session, curso_independiente["materia"], 20).id, session)
        assert segunda.numero_rendicion == 2
        SERVICIO.calificar_examen(segunda.id, Decimal("50"), session)
        session.refresh(im)
        assert im.estado == EM.REPROBADO         # agoto las dos: recursa

        with pytest.raises(ValueError):
            SERVICIO.inscribir_examen(im.id, self._mesa(session, curso_independiente["materia"], 30).id, session)
