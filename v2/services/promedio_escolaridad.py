"""
Promedio de la escolaridad del portal, con la regla de bedelia.

LA REGLA (acordada con bedelia el 22/09/2026)
---------------------------------------------
"La escolaridad es la historia academica del estudiante": el promedio cuenta
TODAS las actividades rendidas, no solo el resultado final de cada materia.

  - Cada cursada cuenta. Una exonerada suma su nota; una perdida (recursa,
    inasistencia) suma 0 y cuenta 1 en el divisor. Recursar baja el promedio,
    y es a proposito.
  - Cada rendicion de examen cuenta. Aprobado suma su nota; eliminado o
    ausente suma 0 y cuenta 1.
  - La cursada aprobada que espera examen (A_EXAMEN) NO cuenta: todavia no
    cerro nada. Cuenta el examen cuando se rinde.
  - La reválida da creditos pero no entra al promedio.
  - Se promedia por carrera, con todos sus planes juntos: si el alumno cambio
    de plan dentro de la misma carrera se suma. Carreras distintas, promedios
    distintos (en el portal, uno por programa).

Es la misma regla que la hoja ESCOLARIDAD del Excel de bedelia, que
reproduce historico_service.evaluar_fila. Las dos partes se suman en un
solo cociente.

DE DONDE SALE CADA ACTIVIDAD
----------------------------
Hasta la FECHA DE CORTE, del legajo historico (el Excel de Escolaridades
importado). Despues, del portal: cada InscripcionMateria es una cursada y
cada InscripcionExamen una rendicion.

Una cursada del portal cuenta solo si EL PORTAL LA CERRO despues del corte
(fecha_cierre, o fecha_baja en un abandono). Todos los caminos de cierre la
graban: calificacion, examen aprobado, agotar examenes, inasistencia,
revalida. Una rendicion cuenta si fecha_examen es posterior al corte.

Asi no se cuenta dos veces lo que trae la planilla de carga inicial: crea
una inscripcion por materia con el estado de HOY, y esa ultima instancia ya
esta en el historico. Esas filas no las cerro el portal (fecha_cierre en
NULL) y no entran. Las que la planilla trae como CURSANDO si entran, cuando
el portal las cierre, que es justo lo que corresponde. EL IMPORTADOR DE LA
PLANILLA NO TIENE QUE PONER fecha_cierre.

Probado el caso que lo motivo: con fechas por semestre, una exoneracion de
2026-1 traida por la planilla caia el 31/07, despues de la ultima acta del
Excel (20/07), y se contaba doble.

Por defecto el corte es la fecha del acta mas reciente del historico. Se puede
fijar con ESCOLARIDAD_FECHA_CORTE=AAAA-MM-DD (el dia que arranca el portal).

EL CASO QUE MAS FACIL SE CUENTA DOBLE
-------------------------------------
Al aprobar un examen, el portal pasa la cursada a APROBADO con nota_final =
nota del examen, Y guarda la rendicion. Si se contaran las dos, un aprobado
sumaria doble. Cuenta la rendicion; la cursada queda como "cursada aprobada"
(no cuenta), igual que en el Excel. Solo si la cursada esta APROBADO y no hay
ninguna rendicion aprobada registrada (una carga manual) cuenta la cursada.

Lo mismo al reves: si el alumno agota los examenes, el portal pasa la cursada
a REPROBADO, pero esa cursada se habia aprobado. Los ceros son de los
examenes; la cursada no suma otro.
"""
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from sqlmodel import Session, select, func, col

from v2.models.alumno import Alumno
from v2.models.enums import EstadoInscripcionMateria as EM, EstadoInscripcionExamen as EE
from v2.models.historico import HistoricoAlumno, HistoricoPlan, HistoricoResultado
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.inscripcion_materia import (
    InscripcionMateria, ActividadEscolaridadRead, PromedioEscolaridadRead,
)
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.instancia_examen import InstanciaExamen
from v2.models.materia import Materia
from v2.models.programa import Programa
from v2.models.usuario import Usuario
from v2.services.historico_service import evaluar_fila, redondear_como_excel, solo_digitos, texto_busqueda


ORIGEN_HISTORICO = "historico"
ORIGEN_PORTAL = "portal"

# Una baja voluntaria (ABANDONO) no es una actividad rendida, asi que por
# defecto no entra. A CONFIRMAR con bedelia: si ellos la cargaban como ELI,
# poner True y pasa a contar como 0.
CONTAR_ABANDONO = False

# Programa del portal -> carrera del historico, cuando el nombre no coincide.
# Las claves y valores van normalizados (texto_busqueda). Hoy no hace falta:
# "Analista Programador" coincide exacto.
ALIAS_CARRERA_HISTORICA: Dict[str, str] = {}


@dataclass
class Actividad:
    """Una fila del certificado. `peso` es lo que suma al divisor."""
    fecha: Optional[date]
    materia: str
    tipo: str               # CUR, EXA, TALLER, REV
    resultado: str          # APR, EXO, ELI, NSP, REV
    nota: Optional[float]   # la nota original, para mostrar
    nota_promedio: float    # lo que suma al numerador
    peso: int               # lo que suma al divisor
    origen: str
    detalle: Optional[str] = None

    @property
    def cuenta(self) -> bool:
        return self.peso > 0

    def read(self) -> ActividadEscolaridadRead:
        return ActividadEscolaridadRead(
            fecha=self.fecha, materia=self.materia, tipo=self.tipo,
            resultado=self.resultado, nota=self.nota, nota_promedio=self.nota_promedio,
            cuenta_en_promedio=self.cuenta, origen=self.origen, detalle=self.detalle,
        )


# ── Reglas puras ─────────────────────────────────────────────────────────────

def _num(valor) -> Optional[float]:
    return float(valor) if valor is not None else None


def _es_taller(materia: str) -> bool:
    return texto_busqueda(materia).startswith("TALLER")


def actividades_de_cursada(
    insc: InscripcionMateria, materia: str, fecha: Optional[date],
    examenes: List[InscripcionExamen],
) -> List[Actividad]:
    """
    La cursada como actividad (o nada, si todavia no cerro). Las rendiciones
    de examen van aparte, en actividad_de_examen.
    """
    tipo = "TALLER" if _es_taller(materia) else "CUR"
    nota_curso = _num(insc.nota_curso)
    nota_final = _num(insc.nota_final) if insc.nota_final is not None else nota_curso
    tuvo_examenes = any(e.estado in (EE.APROBADO, EE.REPROBADO, EE.AUSENTE) for e in examenes)
    aprobo_examen = any(e.estado == EE.APROBADO for e in examenes)

    def act(resultado, nota, nota_promedio, peso, detalle=None, tipo_=tipo):
        return [Actividad(fecha, materia, tipo_, resultado, nota, nota_promedio, peso,
                          ORIGEN_PORTAL, detalle)]

    estado = insc.estado
    if estado == EM.CURSANDO:
        return []
    if estado == EM.EXONERADO:
        return act("EXO", nota_final, nota_final or 0.0, 1)
    if estado == EM.A_EXAMEN:
        return act("APR", nota_curso, 0.0, 0, "cursada aprobada, espera examen")
    if estado == EM.APROBADO:
        if aprobo_examen:
            return act("APR", nota_curso, 0.0, 0, "cursada aprobada; cuenta el examen")
        # Aprobada sin rendicion registrada (carga manual, o taller cerrado a
        # mano): si no se cuenta aca, esa materia no aparece en el promedio.
        return act("APR", nota_final, nota_final or 0.0, 1, "aprobada sin examen registrado en el portal",
                   tipo_=tipo if tipo == "TALLER" else "EXA")
    if estado == EM.REPROBADO:
        if tuvo_examenes:
            return act("APR", nota_curso, 0.0, 0,
                       "cursada aprobada; agoto los examenes (los ceros son de los examenes)")
        return act("ELI", nota_curso, 0.0, 1, "no aprobo el curso")
    if estado == EM.PERDIDO_INASISTENCIA:
        return act("ELI", nota_curso, 0.0, 1, "perdida por inasistencia")
    if estado == EM.ABANDONO:
        if CONTAR_ABANDONO:
            return act("ELI", nota_curso, 0.0, 1, "abandono")
        return act("ELI", nota_curso, 0.0, 0, "abandono: no entra al promedio")
    if estado == EM.REVALIDADA:
        return act("REV", None, 0.0, 0, insc.motivo_revalida or "revalida", tipo_="REV")
    return []


def actividad_de_examen(ie: InscripcionExamen, materia: str, fecha: Optional[date]) -> Optional[Actividad]:
    """Una rendicion. Eliminado y ausente suman 0 y cuentan 1, como en el Excel."""
    nota = _num(ie.nota_examen)
    if ie.estado == EE.APROBADO:
        return Actividad(fecha, materia, "EXA", "APR", nota, nota or 0.0, 1, ORIGEN_PORTAL)
    if ie.estado == EE.REPROBADO:
        return Actividad(fecha, materia, "EXA", "ELI", nota, 0.0, 1, ORIGEN_PORTAL)
    if ie.estado == EE.AUSENTE:
        return Actividad(fecha, materia, "EXA", "NSP", None, 0.0, 1, ORIGEN_PORTAL)
    return None   # INSCRIPTO todavia no rindio; BAJA se bajo antes


def actividad_historica(r: HistoricoResultado) -> Actividad:
    """
    Una fila del legajo con las cuentas del Excel. El peso puede ser 0 o -1:
    la hoja resta del divisor toda fila con resultado REV, incluso las que no
    habia contado (ver historico_service.resumir_plan). Se respeta tal cual.
    """
    e = evaluar_fila(r.tipo_evaluacion, r.resultado, r.puntaje_promedio)
    return Actividad(
        fecha=r.fecha, materia=r.materia, tipo=r.tipo_evaluacion, resultado=r.resultado or "",
        nota=_num(r.puntaje), nota_promedio=float(e["nota_promedio"]),
        peso=int(e["cuenta_promedio"]) - int(e["revalidado"]),
        origen=ORIGEN_HISTORICO,
    )


def promediar(actividades: List[Actividad]) -> Tuple[Optional[float], float, int]:
    """(promedio, suma de notas, divisor). Sin divisor positivo, no hay promedio."""
    suma = sum(a.nota_promedio for a in actividades)
    divisor = sum(a.peso for a in actividades)
    promedio = redondear_como_excel(suma / divisor) if divisor > 0 else None
    return promedio, suma, divisor


def _como_fecha(valor) -> Optional[date]:
    if valor is None:
        return None
    return valor.date() if isinstance(valor, datetime) else valor


def fecha_de_cierre_en_portal(insc: InscripcionMateria) -> Optional[date]:
    """Cuando la cerro el portal. None si nunca la cerro (por ejemplo, vino de la planilla)."""
    return _como_fecha(insc.fecha_cierre) or _como_fecha(insc.fecha_baja)


def fecha_de_cursada(instancia: InstanciaCursado, insc: InscripcionMateria) -> Optional[date]:
    """
    Cuando termino la cursada, para mostrar cuando no hay historico. Si no hay
    fecha, la del fin del semestre.
    """
    for valor in (instancia.fecha_fin, insc.fecha_cierre):
        if valor is not None:
            return valor.date() if isinstance(valor, datetime) else valor
    if instancia.anio_lectivo:
        return date(instancia.anio_lectivo, 7, 31) if instancia.semestre == 1 else date(instancia.anio_lectivo, 12, 31)
    return None


def carrera_historica_de(programa: str, carreras: List[str]) -> Optional[str]:
    """La carrera del historico que corresponde a un programa del portal, por nombre."""
    objetivo = texto_busqueda(programa)
    objetivo = ALIAS_CARRERA_HISTORICA.get(objetivo, objetivo)
    for carrera in carreras:
        if carrera and texto_busqueda(carrera) == objetivo:
            return carrera
    return None


# ── Con base ─────────────────────────────────────────────────────────────────

def fecha_corte(session: Session) -> Optional[date]:
    """ESCOLARIDAD_FECHA_CORTE si esta; si no, el acta mas reciente del historico."""
    fijada = os.getenv("ESCOLARIDAD_FECHA_CORTE", "").strip()
    if fijada:
        return date.fromisoformat(fijada)
    return session.exec(select(func.max(HistoricoResultado.fecha))).one()


def promedio_escolaridad(alumno_id: int, programa_id: int, session: Session) -> PromedioEscolaridadRead:
    corte = fecha_corte(session)
    programa = session.get(Programa, programa_id)

    # ── Historico: por documento del usuario, en la carrera del programa ──────
    historicas: List[Actividad] = []
    carrera = None
    if programa is not None:
        carreras = [c for c in session.exec(select(HistoricoPlan.carrera).distinct()).all() if c]
        carrera = carrera_historica_de(programa.nombre, carreras)

    documento = session.exec(
        select(Usuario.documento).join(Alumno, Alumno.usuario_id == Usuario.id).where(Alumno.id == alumno_id)
    ).first()
    if carrera and solo_digitos(documento):
        filas = session.exec(
            select(HistoricoResultado)
            .join(HistoricoAlumno, HistoricoAlumno.id == HistoricoResultado.alumno_id)
            .join(HistoricoPlan, HistoricoPlan.id == HistoricoResultado.plan_id)
            .where(
                HistoricoAlumno.cedula == solo_digitos(documento),
                HistoricoPlan.carrera == carrera,
            )
            .order_by(col(HistoricoResultado.fecha).asc().nulls_last(), HistoricoResultado.fila_origen)
        ).all()
        historicas = [
            actividad_historica(r) for r in filas
            if corte is None or r.fecha is None or r.fecha <= corte
        ]

    # ── Portal: cursadas y rendiciones del programa, despues del corte ────────
    cursadas = session.exec(
        select(InscripcionMateria, InstanciaCursado, Materia)
        .join(InstanciaCursado, InstanciaCursado.id == InscripcionMateria.instancia_cursado_id)
        .join(Materia, Materia.id == InstanciaCursado.materia_id)
        .where(InscripcionMateria.alumno_id == alumno_id, Materia.programa_id == programa_id)
    ).all()

    ids = [insc.id for insc, _, _ in cursadas]
    examenes_de: Dict[int, List[Tuple[InscripcionExamen, InstanciaExamen]]] = {i: [] for i in ids}
    if ids:
        for ie, inst in session.exec(
            select(InscripcionExamen, InstanciaExamen)
            .join(InstanciaExamen, InstanciaExamen.id == InscripcionExamen.instancia_examen_id)
            .where(col(InscripcionExamen.inscripcion_materia_id).in_(ids))
        ).all():
            examenes_de[ie.inscripcion_materia_id].append((ie, inst))

    del_portal: List[Actividad] = []
    for insc, instancia, materia in cursadas:
        examenes = examenes_de.get(insc.id, [])
        cierre = fecha_de_cierre_en_portal(insc)
        if corte is None:
            # Sin historico no hay nada que duplicar: cuenta todo lo del portal
            cuenta_cursada, fecha = True, cierre or fecha_de_cursada(instancia, insc)
        else:
            cuenta_cursada, fecha = (cierre is not None and cierre > corte), cierre
        if cuenta_cursada:
            del_portal += actividades_de_cursada(insc, materia.nombre, fecha, [e for e, _ in examenes])
        for ie, inst in examenes:
            fecha_ex = _como_fecha(inst.fecha_examen)
            if corte is None or fecha_ex is None or fecha_ex > corte:
                a = actividad_de_examen(ie, materia.nombre, fecha_ex)
                if a:
                    del_portal.append(a)

    todas = sorted(historicas + del_portal, key=lambda a: (a.fecha or date.max, a.origen, a.materia))
    promedio, suma, divisor = promediar(todas)

    return PromedioEscolaridadRead(
        promedio=promedio,
        suma_notas=round(suma, 2),
        divisor=divisor,
        actividades_que_cuentan=sum(1 for a in todas if a.cuenta),
        del_historico=len(historicas),
        del_portal=len(del_portal),
        carrera_historica=carrera,
        fecha_corte=corte,
        actividades=[a.read() for a in todas],
    )
