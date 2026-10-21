"""
Avance de un alumno en una carrera (pedido de frontend, 27/09/2026).

Reparte las materias activas del plan en cuatro listas, sin repetir:

    aprobadas   APROBADO, EXONERADO o REVALIDADA
    cursando    una inscripcion CURSANDO
    a_examen    curso aprobado, examen pendiente (con las oportunidades usadas)
    pendientes  el resto: nunca cursada, reprobada, abandonada o perdida por
                faltas, con si hoy cumple las previaturas para cursarla

Si una materia tiene varias inscripciones (recursadas), manda la mas fuerte en
ese orden: una aprobacion vieja gana sobre una recursada en curso, y una
cursada en curso gana sobre un A_EXAMEN viejo. Dentro del mismo tipo, la del
año lectivo mas reciente.

Mismos criterios que el resto del portal, sin reescribirlos: lo cumplido y los
creditos como el egreso (EgresoService), las previaturas con la regla de
cumplimiento pleno y las excepciones del año (InscripcionMateriaService), y las
rendiciones como el servicio de examenes.

Cada plan es un programa aparte, asi que lo aprobado en otro plan de la misma
carrera va en `aprobadas_otros_planes` y no descuenta pendientes: las
equivalencias entre planes no estan definidas.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlmodel import Session, col, select

from v2.models.avance import AvanceCarreraRead, AvanceMateriaItem, AvanceResumen
from v2.models.enums import EstadoInscripcionMateria as EM
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.materia import Materia
from v2.models.politica_examen import PoliticaExamen
from v2.models.programa import Programa
from v2.services.egreso_service import EgresoService
from v2.services.historico_service import carrera_canonica
from v2.services.inscripcion_examen_service import InscripcionExamenService
from v2.services.inscripcion_service import InscripcionMateriaService, get_uruguay_tz
from v2.services.planes import carrera_de

CUMPLIDA = set(EgresoService.ESTADOS_CUMPLIDA)


def _elegir(inscripciones: List[Tuple[InscripcionMateria, int]]) -> Tuple[str, Tuple[InscripcionMateria, int]]:
    """La inscripcion que define la situacion de la materia, y en que lista va."""
    def mas_reciente(filas):
        return max(filas, key=lambda f: (f[1], f[0].id or 0))

    for lista, estados in (("aprobadas", CUMPLIDA), ("cursando", {EM.CURSANDO}), ("a_examen", {EM.A_EXAMEN})):
        filas = [f for f in inscripciones if f[0].estado in estados]
        if filas:
            return lista, mas_reciente(filas)
    return "pendientes", mas_reciente(inscripciones)


class AvanceService:

    def __init__(self):
        self._inscripciones = InscripcionMateriaService()

    def _item(self, materia: Materia, fila: Optional[Tuple[InscripcionMateria, int]] = None, **extra) -> AvanceMateriaItem:
        insc, anio = fila if fila else (None, None)
        return AvanceMateriaItem(
            materia_id=materia.id, nombre=materia.nombre, codigo=materia.codigo,
            semestre=materia.semestre, creditos=materia.creditos,
            inscripcion_id=insc.id if insc else None,
            estado=insc.estado.value if insc else None,
            anio_lectivo=anio,
            nota_curso=insc.nota_curso if insc else None,
            nota_final=insc.nota_final if insc else None,
            **extra,
        )

    @staticmethod
    def _inscripciones_por_materia(
        alumno_id: int, materia_ids: List[int], session: Session
    ) -> Dict[int, List[Tuple[InscripcionMateria, int]]]:
        if not materia_ids:
            return {}
        filas = session.exec(
            select(InscripcionMateria, InstanciaCursado.materia_id, InstanciaCursado.anio_lectivo)
            .join(InstanciaCursado, InscripcionMateria.instancia_cursado_id == InstanciaCursado.id)
            .where(InscripcionMateria.alumno_id == alumno_id,
                   col(InstanciaCursado.materia_id).in_(materia_ids))
        ).all()
        por_materia: Dict[int, List[Tuple[InscripcionMateria, int]]] = {}
        for insc, materia_id, anio in filas:
            por_materia.setdefault(materia_id, []).append((insc, anio))
        return por_materia

    def avance(self, alumno_id: int, programa_id: int, session: Session) -> AvanceCarreraRead:
        programa = session.get(Programa, programa_id)
        if programa is None:
            raise ValueError(f"Programa {programa_id} no encontrado")

        materias = list(session.exec(
            select(Materia).where(Materia.programa_id == programa_id, Materia.activo == True)  # noqa: E712
            .order_by(Materia.semestre, Materia.nombre)
        ).all())
        por_materia = self._inscripciones_por_materia(alumno_id, [m.id for m in materias], session)

        listas: Dict[str, List[Tuple[Materia, Tuple[InscripcionMateria, int]]]] = {
            "aprobadas": [], "cursando": [], "a_examen": [], "pendientes": []}
        for materia in materias:
            inscripciones = por_materia.get(materia.id)
            if not inscripciones:
                listas["pendientes"].append((materia, None))
                continue
            lista, fila = _elegir(inscripciones)
            listas[lista].append((materia, fila))

        salida = AvanceCarreraRead(
            alumno_id=alumno_id, programa_id=programa_id, programa_nombre=programa.nombre,
            resumen=AvanceResumen(materias_totales=0, aprobadas=0, cursando=0, a_examen=0, pendientes=0,
                                  creditos_obtenidos=0, creditos_requeridos=0, porcentaje_avance=0),
        )
        salida.aprobadas = [self._item(m, f) for m, f in listas["aprobadas"]]
        salida.cursando = [self._item(m, f, faltas=f[0].faltas) for m, f in listas["cursando"]]
        salida.a_examen = self._a_examen(listas["a_examen"], session)
        salida.pendientes = self._pendientes(alumno_id, programa_id, listas["pendientes"], session)
        salida.aprobadas_otros_planes = self._otros_planes(alumno_id, programa, session)

        creditos_obtenidos = sum(m.creditos for m, _ in listas["aprobadas"])
        creditos_requeridos = programa.creditos_requeridos or sum(m.creditos for m in materias)
        salida.resumen = AvanceResumen(
            materias_totales=len(materias),
            aprobadas=len(salida.aprobadas), cursando=len(salida.cursando),
            a_examen=len(salida.a_examen), pendientes=len(salida.pendientes),
            creditos_obtenidos=creditos_obtenidos, creditos_requeridos=creditos_requeridos,
            porcentaje_avance=round(creditos_obtenidos / creditos_requeridos * 100, 2) if creditos_requeridos else 0,
        )
        return salida

    def _a_examen(self, filas, session: Session) -> List[AvanceMateriaItem]:
        usadas = InscripcionExamenService._contar_rendiciones_en_lote([f[0].id for _, f in filas], session)
        politicas = {p.id: p for p in session.exec(select(PoliticaExamen)).all()} if filas else {}
        return [
            self._item(m, f, rendiciones_usadas=usadas.get(f[0].id, 0),
                       max_oportunidades=politicas[m.politica_examen_id].max_oportunidades
                       if m.politica_examen_id in politicas else None)
            for m, f in filas
        ]

    def _pendientes(self, alumno_id: int, programa_id: int, filas, session: Session) -> List[AvanceMateriaItem]:
        if not filas:
            return []
        # La misma regla que la inscripcion: cadena completa y excepciones de
        # este año lectivo, en lote para no consultar materia por materia.
        servicio = self._inscripciones
        grafo = servicio._grafo_previaturas(programa_id, session)
        nombres = {mid: nombre for mid, nombre in session.exec(
            select(Materia.id, Materia.nombre).where(Materia.programa_id == programa_id)).all()}
        estados = servicio._estados_del_alumno(alumno_id, list(nombres), session)
        anio = datetime.now(get_uruguay_tz()).year
        excepciones = servicio._excepciones_vigentes(alumno_id, anio, session)

        items = []
        for materia, fila in filas:
            cumple, faltantes = servicio._evaluar_previaturas(
                grafo.get(materia.id, []), estados, nombres, grafo, excepciones)
            items.append(self._item(materia, fila, cumple_previaturas=cumple, previaturas_faltantes=faltantes))
        return items

    def _otros_planes(self, alumno_id: int, programa: Programa, session: Session) -> List[AvanceMateriaItem]:
        carrera = carrera_canonica(carrera_de(programa.nombre))
        otros = {p.id: p for p in session.exec(select(Programa)).all()
                 if p.id != programa.id and carrera_canonica(carrera_de(p.nombre)) == carrera}
        if not otros:
            return []
        materias = {m.id: m for m in session.exec(
            select(Materia).where(col(Materia.programa_id).in_(list(otros)))).all()}
        items = []
        for materia_id, inscripciones in self._inscripciones_por_materia(alumno_id, list(materias), session).items():
            lista, fila = _elegir(inscripciones)
            if lista == "aprobadas":
                materia = materias[materia_id]
                items.append(self._item(materia, fila, programa=otros[materia.programa_id].nombre))
        return sorted(items, key=lambda i: (i.programa or "", i.semestre, i.nombre))
