"""
Legajo historico: consulta de lo que bedelia llevaba en la planilla de
escolaridades antes del portal. Solo lectura; los datos entran por
v2/scripts/importar_historico.py.

El resumen por plan reproduce lo que calculaba la hoja ESCOLARIDAD (el
certificado que bedelia imprimia), formula por formula, para que el numero que
vea el alumno sea el mismo que le daban antes. Las reglas estan en
`evaluar_fila` y `resumir_plan`, que son funciones puras: se prueban sin base.
"""
import re
import unicodedata
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from sqlmodel import Session, select, func, col

from v2.models.historico import (
    HistoricoAlumno, HistoricoPlan, HistoricoResultado,
    HistoricoAlumnoRead, HistoricoAlumnoResumenRead, HistoricoPlanRead,
    HistoricoResultadoRead, ResumenPlanRead, LegajoHistoricoRead,
    TIPOS_EVALUACION, RESULTADOS, CREDITOS,
)


# ── Reglas del certificado (puras) ───────────────────────────────────────────

NOTA_MINIMA_CREDITO = 70


def evaluar_fila(tipo: str, resultado: Optional[str], puntaje_promedio: Optional[int]) -> dict:
    """
    Las cuatro columnas de control de la hoja ESCOLARIDAD, tal cual:

      Ctrol  (otorga_credito)   examen o taller con >= 70, cursada exonerada, o revalida
      Ctrl2  (cuenta_promedio)  todo salvo revalidas, filas vacias y cursadas aprobadas
                                (la cursada aprobada espera el examen: no cierra nada)
      Ctrol3 (revalidado)       resultado REV
      Ctrol4 (nota_promedio)    la nota si es examen, taller o cursada exonerada; si no 0

    Una fila eliminada cuenta en el promedio con 0. Es duro, pero es la regla
    que bedelia venia aplicando y la que figura en los certificados emitidos.
    """
    tipo = (tipo or "").upper()
    resultado = (resultado or "").upper()
    nota = puntaje_promedio or 0

    examen_o_taller = tipo in ("EXA", "TALLER")
    cursada_exonerada = tipo == "CUR" and resultado == "EXO"

    otorga_credito = (
        (examen_o_taller and nota >= NOTA_MINIMA_CREDITO)
        or cursada_exonerada
        or tipo == "REV"
    )
    cuenta_promedio = not (tipo == "REV" or tipo == "" or (tipo == "CUR" and resultado == "APR"))
    revalidado = resultado == "REV"
    nota_promedio = nota if (examen_o_taller or cursada_exonerada) else 0

    return {
        "otorga_credito": otorga_credito,
        "cuenta_promedio": cuenta_promedio,
        "revalidado": revalidado,
        "nota_promedio": nota_promedio,
    }


def resumir_plan(filas: List[HistoricoResultado], plan: HistoricoPlan) -> ResumenPlanRead:
    """
    Los totales del certificado para un plan: creditos, revalidas y promedio.

    El promedio es la formula F11 de la hoja, tal cual:
    SUM(Ctrol4) / (SUM(Ctrl2) - SUM(Ctrol3)). Se resta toda fila con resultado
    REV, incluso las de tipo REV que Ctrl2 ya no contaba: eso achica el divisor
    en 27 de los 1457 pares alumno-plan de la planilla y en uno lo deja en 0
    (#DIV/0! en la hoja, None aca). Se decidio dejarlo asi el 11/09/2026 para
    que el numero sea el mismo que bedelia tiene en su Excel y en los
    certificados que ya emitio.
    """
    creditos = revalidados = numerador = denominador = 0
    por_resultado: Dict[str, int] = defaultdict(int)
    materias_aprobadas: List[str] = []
    fechas = [f.fecha for f in filas if f.fecha]

    for f in filas:
        e = evaluar_fila(f.tipo_evaluacion, f.resultado, f.puntaje_promedio)
        creditos += e["otorga_credito"]
        revalidados += e["revalidado"]
        denominador += e["cuenta_promedio"]
        numerador += e["nota_promedio"]
        por_resultado[f.resultado or "SIN_RESULTADO"] += 1
        if e["otorga_credito"] and f.materia not in materias_aprobadas:
            materias_aprobadas.append(f.materia)

    divisor = denominador - revalidados
    promedio = redondear_como_excel(numerador / divisor) if divisor > 0 else None

    return ResumenPlanRead(
        plan=plan.codigo,
        carrera=plan.carrera,
        creditos_requeridos=plan.creditos_requeridos,
        creditos_aprobados=creditos,
        creditos_revalidados=revalidados,
        promedio=promedio,
        cantidad_resultados=len(filas),
        por_resultado=dict(por_resultado),
        materias_aprobadas=sorted(materias_aprobadas),
        primera_fecha=min(fechas) if fechas else None,
        ultima_fecha=max(fechas) if fechas else None,
    )


def redondear_como_excel(valor: float, decimales: int = 2) -> float:
    """
    35,125 -> 35,13. round() de Python redondea al par (35,12) y el Excel de
    bedelia redondea hacia arriba: el promedio tiene que dar el mismo numero.
    """
    paso = Decimal(1).scaleb(-decimales)
    return float(Decimal(str(valor)).quantize(paso, rounding=ROUND_HALF_UP))


def solo_digitos(valor: Optional[str]) -> str:
    """'4.257.024-3' -> '42570243'. Para comparar cedulas venga como venga."""
    return re.sub(r"\D", "", str(valor or ""))


def texto_busqueda(valor: Optional[str]) -> str:
    """'Núñez  Ávila' -> 'NUNEZ AVILA'. Lo que se guarda en nombre_busqueda y lo que se busca."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", str(valor or ""))
        if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", sin_acentos).strip().upper()


# ── Servicio ─────────────────────────────────────────────────────────────────

class HistoricoService:

    # ── Alumnos ──────────────────────────────────────────────────────────────

    def buscar_alumnos(
        self, session: Session, q: Optional[str] = None, plan: Optional[str] = None,
        solo_con_resultados: bool = False, limit: int = 50, offset: int = 0,
    ) -> dict:
        """
        Busqueda para el listado. `q` con digitos busca por cedula (prefijo);
        con letras busca en el nombre. `plan` filtra a quienes tienen algun
        resultado en ese plan.
        """
        consulta = select(HistoricoAlumno)
        if q:
            q = q.strip()
            if solo_digitos(q) == q.replace(".", "").replace("-", ""):
                consulta = consulta.where(col(HistoricoAlumno.cedula).startswith(solo_digitos(q)))
            else:
                consulta = consulta.where(col(HistoricoAlumno.nombre_busqueda).like(f"%{texto_busqueda(q)}%"))
        if plan or solo_con_resultados:
            con_resultados = select(HistoricoResultado.alumno_id)
            if plan:
                con_resultados = con_resultados.join(HistoricoPlan).where(HistoricoPlan.codigo == plan.strip().upper())
            consulta = consulta.where(col(HistoricoAlumno.id).in_(con_resultados))

        total = session.exec(select(func.count()).select_from(consulta.subquery())).one()
        alumnos = session.exec(
            consulta.order_by(HistoricoAlumno.nombre).offset(offset).limit(limit)
        ).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": self._resumenes(session, alumnos),
        }

    def _resumenes(self, session: Session, alumnos: List[HistoricoAlumno]) -> List[HistoricoAlumnoResumenRead]:
        """Una consulta agregada para toda la pagina, no una por alumno."""
        if not alumnos:
            return []
        ids = [a.id for a in alumnos]
        agregados = session.exec(
            select(
                HistoricoResultado.alumno_id, HistoricoPlan.codigo,
                func.count(HistoricoResultado.id),
                func.min(HistoricoResultado.fecha), func.max(HistoricoResultado.fecha),
            )
            .join(HistoricoPlan, HistoricoPlan.id == HistoricoResultado.plan_id)
            .where(col(HistoricoResultado.alumno_id).in_(ids))
            .group_by(HistoricoResultado.alumno_id, HistoricoPlan.codigo)
            .order_by(HistoricoPlan.codigo)
        ).all()

        por_alumno: Dict[int, dict] = defaultdict(lambda: {"planes": [], "n": 0, "fechas": []})
        for alumno_id, codigo, n, desde, hasta in agregados:
            r = por_alumno[alumno_id]
            r["planes"].append(codigo)
            r["n"] += n
            r["fechas"].extend(f for f in (desde, hasta) if f)

        salida = []
        for a in alumnos:
            r = por_alumno[a.id]
            salida.append(HistoricoAlumnoResumenRead(
                id=a.id, cedula=a.cedula, nombre=a.nombre, plan_declarado=a.plan_declarado,
                planes=r["planes"], cantidad_resultados=r["n"],
                primera_fecha=min(r["fechas"]) if r["fechas"] else None,
                ultima_fecha=max(r["fechas"]) if r["fechas"] else None,
            ))
        return salida

    def alumno_por_cedula(self, session: Session, cedula: str) -> Optional[HistoricoAlumno]:
        return session.exec(
            select(HistoricoAlumno).where(HistoricoAlumno.cedula == solo_digitos(cedula))
        ).first()

    # ── Legajo ───────────────────────────────────────────────────────────────

    def legajo(self, session: Session, cedula: str) -> Optional[LegajoHistoricoRead]:
        """El legajo completo: datos de la persona, resumen por plan y todas las filas."""
        alumno = self.alumno_por_cedula(session, cedula)
        if not alumno:
            return None

        filas = session.exec(
            select(HistoricoResultado, HistoricoPlan)
            .join(HistoricoPlan, HistoricoPlan.id == HistoricoResultado.plan_id)
            .where(HistoricoResultado.alumno_id == alumno.id)
            .order_by(
                col(HistoricoResultado.fecha).asc().nulls_last(),
                HistoricoResultado.fila_origen,
            )
        ).all()

        por_plan: Dict[int, List[HistoricoResultado]] = defaultdict(list)
        planes: Dict[int, HistoricoPlan] = {}
        for fila, plan in filas:
            por_plan[plan.id].append(fila)
            planes[plan.id] = plan

        resumenes = [resumir_plan(por_plan[pid], planes[pid]) for pid in por_plan]
        resumenes.sort(key=lambda r: (r.primera_fecha or date.min, r.plan))

        return LegajoHistoricoRead(
            alumno=HistoricoAlumnoRead.model_validate(alumno),
            general=self._resumen_general([f for f, _ in filas], resumenes, planes),
            planes=resumenes,
            resultados=[self._fila_read(f, p) for f, p in filas],
            codigos={
                "tipo_evaluacion": TIPOS_EVALUACION,
                "resultado": RESULTADOS,
                "credito": CREDITOS,
            },
        )

    @staticmethod
    def _resumen_general(
        filas: List[HistoricoResultado], resumenes: List[ResumenPlanRead],
        planes: Dict[int, HistoricoPlan],
    ) -> Optional[ResumenPlanRead]:
        """
        Todas las actas juntas, sin importar el plan. Es el numero por defecto
        del certificado de bedelia: la hoja ESCOLARIDAD filtra por documento
        con CARRERA = (Todas), asi que un alumno que paso de AP 2020 a AP 2022
        promedia las dos. El 22% de los alumnos del historico tiene actas en
        mas de un plan, asi que no es un detalle.

        Los creditos requeridos en el certificado salen del PLAN que bedelia
        elige a mano; aca se toman del plan del acta mas reciente. La carrera
        va solo si todos los planes son de la misma.
        """
        if not filas:
            return None
        ultimo = max(resumenes, key=lambda r: (r.ultima_fecha or date.min, r.plan))
        carreras = {p.carrera for p in planes.values()}
        seudo_plan = HistoricoPlan(
            codigo="(Todas)",
            carrera=carreras.pop() if len(carreras) == 1 else None,
            creditos_requeridos=ultimo.creditos_requeridos,
        )
        return resumir_plan(filas, seudo_plan)

    def legajo_por_documento(self, session: Session, documento: Optional[str]) -> Optional[LegajoHistoricoRead]:
        """Para el portal del estudiante: por el documento del usuario logueado."""
        if not solo_digitos(documento):
            return None
        return self.legajo(session, documento)

    @staticmethod
    def _fila_read(f: HistoricoResultado, plan: HistoricoPlan) -> HistoricoResultadoRead:
        e = evaluar_fila(f.tipo_evaluacion, f.resultado, f.puntaje_promedio)
        return HistoricoResultadoRead(
            id=f.id, plan=plan.codigo, carrera=plan.carrera,
            materia=f.materia, docente=f.docente,
            fecha=f.fecha, fecha_texto=f.fecha_texto,
            tipo_evaluacion=f.tipo_evaluacion,
            tipo_evaluacion_descripcion=TIPOS_EVALUACION.get(f.tipo_evaluacion),
            resultado=f.resultado,
            resultado_descripcion=RESULTADOS.get(f.resultado or ""),
            puntaje=f.puntaje, puntaje_promedio=f.puntaje_promedio,
            credito=f.credito, acta=f.acta, proyecto=f.proyecto,
            observaciones=f.observaciones,
            otorga_credito=e["otorga_credito"],
        )

    # ── Catalogos ────────────────────────────────────────────────────────────

    def listar_planes(self, session: Session) -> List[dict]:
        """Los planes con cuantos alumnos y filas tiene cada uno."""
        filas = session.exec(
            select(
                HistoricoPlan,
                func.count(func.distinct(HistoricoResultado.alumno_id)),
                func.count(HistoricoResultado.id),
                func.min(HistoricoResultado.fecha), func.max(HistoricoResultado.fecha),
            )
            .outerjoin(HistoricoResultado, HistoricoResultado.plan_id == HistoricoPlan.id)
            .group_by(HistoricoPlan.id)
            .order_by(HistoricoPlan.codigo)
        ).all()
        return [
            {
                **HistoricoPlanRead.model_validate(plan).model_dump(),
                "cantidad_alumnos": alumnos,
                "cantidad_resultados": resultados,
                "primera_fecha": desde,
                "ultima_fecha": hasta,
            }
            for plan, alumnos, resultados, desde, hasta in filas
        ]

    def listar_materias(self, session: Session, plan: Optional[str] = None) -> List[dict]:
        """Nombres de materia distintos, para armar filtros. Con cuantas filas tiene cada uno."""
        consulta = (
            select(HistoricoResultado.materia, func.count(HistoricoResultado.id))
            .group_by(HistoricoResultado.materia)
            .order_by(HistoricoResultado.materia)
        )
        if plan:
            consulta = consulta.join(HistoricoPlan).where(HistoricoPlan.codigo == plan.strip().upper())
        return [{"materia": m, "cantidad": n} for m, n in session.exec(consulta).all()]

    # ── Filas sueltas ────────────────────────────────────────────────────────

    def buscar_resultados(
        self, session: Session, cedula: Optional[str] = None, plan: Optional[str] = None,
        materia: Optional[str] = None, tipo_evaluacion: Optional[str] = None,
        resultado: Optional[str] = None, acta: Optional[str] = None,
        desde: Optional[date] = None, hasta: Optional[date] = None,
        limit: int = 100, offset: int = 0,
    ) -> dict:
        """
        Busqueda por acta, materia o fecha, sin pasar por el alumno. Es lo que
        bedelia necesita para responder "quienes rindieron X en tal fecha".
        """
        consulta = (
            select(HistoricoResultado, HistoricoPlan, HistoricoAlumno)
            .join(HistoricoPlan, HistoricoPlan.id == HistoricoResultado.plan_id)
            .join(HistoricoAlumno, HistoricoAlumno.id == HistoricoResultado.alumno_id)
        )
        if cedula:
            consulta = consulta.where(HistoricoAlumno.cedula == solo_digitos(cedula))
        if plan:
            consulta = consulta.where(HistoricoPlan.codigo == plan.strip().upper())
        if materia:
            consulta = consulta.where(col(HistoricoResultado.materia).ilike(f"%{materia.strip().upper()}%"))
        if tipo_evaluacion:
            consulta = consulta.where(HistoricoResultado.tipo_evaluacion == tipo_evaluacion.strip().upper())
        if resultado:
            consulta = consulta.where(HistoricoResultado.resultado == resultado.strip().upper())
        if acta:
            consulta = consulta.where(HistoricoResultado.acta == acta.strip())
        if desde:
            consulta = consulta.where(HistoricoResultado.fecha >= desde)
        if hasta:
            consulta = consulta.where(HistoricoResultado.fecha <= hasta)

        total = session.exec(select(func.count()).select_from(consulta.subquery())).one()
        filas = session.exec(
            consulta.order_by(
                col(HistoricoResultado.fecha).desc().nulls_last(),
                HistoricoAlumno.nombre,
            ).offset(offset).limit(limit)
        ).all()

        items = []
        for f, p, a in filas:
            item = self._fila_read(f, p).model_dump()
            item["alumno"] = {"id": a.id, "cedula": a.cedula, "nombre": a.nombre}
            items.append(item)

        return {"total": total, "limit": limit, "offset": offset, "items": items}
