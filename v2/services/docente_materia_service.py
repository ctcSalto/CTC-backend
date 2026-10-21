from typing import Optional, List
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.docente_materia import (
    DocenteMateria,
    DocenteMateriaCreate,
    DocenteMateriaUpdate,
)
from v2.models.profesor import Profesor


class DocenteMateriaService(BaseServiceWithFilters[DocenteMateria]):
    def __init__(self):
        super().__init__(DocenteMateria)

    def get_by_id(
        self, asignacion_id: int, session: Session
    ) -> Optional[DocenteMateria]:
        return session.exec(
            select(DocenteMateria).where(DocenteMateria.id == asignacion_id)
        ).first()

    def get_by_instancia_cursado(
        self, instancia_cursado_id: int, session: Session
    ) -> List[DocenteMateria]:
        return list(session.exec(
            select(DocenteMateria).where(
                DocenteMateria.instancia_cursado_id == instancia_cursado_id,
            )
        ).all())

    @staticmethod
    def docente_asignado_a_cursada(
        usuario_id: int, instancia_cursado_id: int, session: Session
    ) -> bool:
        """
        Si el usuario (persona, la del JWT) dicta esa instancia de cursado.

        Recibe usuario_id y no profesor_id porque el token identifica a la
        persona, mientras que la asignacion referencia el perfil docente.
        """
        from v2.models.profesor import Profesor
        from v2.models.instancia_cursado import InstanciaCursado  # noqa: F401

        asignacion = session.exec(
            select(DocenteMateria)
            .join(Profesor, DocenteMateria.profesor_id == Profesor.id)
            .where(
                Profesor.usuario_id == usuario_id,
                DocenteMateria.instancia_cursado_id == instancia_cursado_id,
            )
        ).first()
        return asignacion is not None

    # ── Historico ────────────────────────────────────────────────────────────

    def get_historico_materias(
        self,
        profesor_id: int,
        session: Session,
        anio_lectivo: Optional[int] = None,
    ) -> List[dict]:
        """
        Historico completo de instancias de cursado dictadas por el profesor,
        de la mas reciente a la mas antigua. Sin anio_lectivo devuelve todos
        los anios.
        """
        from v2.models.instancia_cursado import InstanciaCursado
        from v2.models.materia import Materia
        from v2.models.inscripcion_materia import InscripcionMateria
        from v2.models.programa import Programa
        from sqlalchemy import func

        stmt = (
            select(DocenteMateria, InstanciaCursado, Materia, Programa)
            .join(InstanciaCursado, DocenteMateria.instancia_cursado_id == InstanciaCursado.id)
            .join(Materia, InstanciaCursado.materia_id == Materia.id)
            .join(Programa, Materia.programa_id == Programa.id)
            .where(DocenteMateria.profesor_id == profesor_id)
            .order_by(
                InstanciaCursado.anio_lectivo.desc(),
                InstanciaCursado.semestre.desc(),
                Materia.nombre,
            )
        )
        if anio_lectivo is not None:
            stmt = stmt.where(InstanciaCursado.anio_lectivo == anio_lectivo)

        filas = session.exec(stmt).all()

        # Cantidad de inscriptos por instancia, en una sola consulta
        instancia_ids = [ic.id for _, ic, _, _ in filas]
        inscriptos_por_instancia: dict[int, int] = {}
        if instancia_ids:
            conteos = session.exec(
                select(
                    InscripcionMateria.instancia_cursado_id,
                    func.count(InscripcionMateria.id),
                )
                .where(InscripcionMateria.instancia_cursado_id.in_(instancia_ids))
                .group_by(InscripcionMateria.instancia_cursado_id)
            ).all()
            inscriptos_por_instancia = {ic_id: total for ic_id, total in conteos}

        return [
            {
                "asignacion_id": asignacion.id,
                "instancia_cursado_id": ic.id,
                "materia_id": materia.id,
                "materia_nombre": materia.nombre,
                "materia_codigo": materia.codigo,
                "programa_id": programa.id,
                "programa_nombre": programa.nombre,
                "semestre_plan": materia.semestre,
                "anio_lectivo": ic.anio_lectivo,
                "semestre": ic.semestre,
                "salon": ic.salon,
                "horario": ic.horario,
                "estado_instancia": ic.estado.value,
                "rol_docente": asignacion.rol_docente.value,
                "total_inscriptos": inscriptos_por_instancia.get(ic.id, 0),
            }
            for asignacion, ic, materia, programa in filas
        ]

    def get_historico_examenes(
        self,
        profesor_id: int,
        session: Session,
        anio: Optional[int] = None,
    ) -> List[dict]:
        """
        Historico de instancias de examen en las que el profesor estuvo asignado
        como tribunal, de la mas reciente a la mas antigua. `anio` filtra por
        anio de la fecha del examen.
        """
        from v2.models.docente_instancia_examen import DocenteInstanciaExamen
        from v2.models.instancia_examen import InstanciaExamen
        from v2.models.inscripcion_examen import InscripcionExamen
        from v2.models.materia import Materia
        from v2.models.programa import Programa
        from sqlalchemy import func, extract

        stmt = (
            select(DocenteInstanciaExamen, InstanciaExamen, Materia, Programa)
            .join(InstanciaExamen, DocenteInstanciaExamen.instancia_examen_id == InstanciaExamen.id)
            .join(Materia, InstanciaExamen.materia_id == Materia.id)
            .join(Programa, Materia.programa_id == Programa.id)
            .where(DocenteInstanciaExamen.profesor_id == profesor_id)
            .order_by(InstanciaExamen.fecha_examen.desc())
        )
        if anio is not None:
            stmt = stmt.where(extract('year', InstanciaExamen.fecha_examen) == anio)

        filas = session.exec(stmt).all()

        instancia_ids = [inst.id for _, inst, _, _ in filas]
        inscriptos_por_instancia: dict[int, int] = {}
        if instancia_ids:
            conteos = session.exec(
                select(
                    InscripcionExamen.instancia_examen_id,
                    func.count(InscripcionExamen.id),
                )
                .where(InscripcionExamen.instancia_examen_id.in_(instancia_ids))
                .group_by(InscripcionExamen.instancia_examen_id)
            ).all()
            inscriptos_por_instancia = {inst_id: total for inst_id, total in conteos}

        return [
            {
                "asignacion_id": asignacion.id,
                "instancia_examen_id": inst.id,
                "materia_id": materia.id,
                "materia_nombre": materia.nombre,
                "materia_codigo": materia.codigo,
                "programa_id": programa.id,
                "programa_nombre": programa.nombre,
                "nombre_examen": inst.nombre,
                "fecha_examen": inst.fecha_examen.isoformat() if inst.fecha_examen else None,
                "hora": inst.hora,
                "salon": inst.salon,
                "modalidad": inst.modalidad.value if inst.modalidad else None,
                "tipo": inst.tipo.value if inst.tipo else None,
                "estado_instancia": inst.estado.value,
                "total_inscriptos": inscriptos_por_instancia.get(inst.id, 0),
            }
            for asignacion, inst, materia, programa in filas
        ]

    def assign(self, data: DocenteMateriaCreate, session: Session) -> DocenteMateria:
        # Validar que el perfil de profesor exista. Ya no hace falta chequear el rol
        # del usuario por separado: tener fila en `profesor` ES la afirmacion de que
        # esa persona es docente, y la FK lo garantiza a nivel de base de datos.
        profesor = session.get(Profesor, data.profesor_id)
        if not profesor:
            raise ValueError(f"Profesor {data.profesor_id} no encontrado")

        # Validar que la instancia de cursado exista
        from v2.models.instancia_cursado import InstanciaCursado
        instancia = session.get(InstanciaCursado, data.instancia_cursado_id)
        if not instancia:
            raise ValueError(f"Instancia de cursado {data.instancia_cursado_id} no encontrada")

        # Validar que no exista la misma asignacion
        existente = session.exec(
            select(DocenteMateria).where(
                DocenteMateria.profesor_id == data.profesor_id,
                DocenteMateria.instancia_cursado_id == data.instancia_cursado_id,
            )
        ).first()
        if existente:
            raise ValueError(
                "Este docente ya esta asignado a esta instancia de cursado"
            )

        asignacion = DocenteMateria(**data.model_dump())
        session.add(asignacion)
        session.commit()
        session.refresh(asignacion)
        return asignacion

    def update(
        self,
        asignacion_id: int,
        data: DocenteMateriaUpdate,
        session: Session,
    ) -> DocenteMateria:
        asignacion = self.get_by_id(asignacion_id, session)
        if not asignacion:
            raise ValueError(f"Asignacion {asignacion_id} no encontrada")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(asignacion, key, value)

        session.add(asignacion)
        session.commit()
        session.refresh(asignacion)
        return asignacion

    def delete(self, asignacion_id: int, session: Session) -> None:
        asignacion = self.get_by_id(asignacion_id, session)
        if not asignacion:
            raise ValueError(f"Asignacion {asignacion_id} no encontrada")

        session.delete(asignacion)
        session.commit()
