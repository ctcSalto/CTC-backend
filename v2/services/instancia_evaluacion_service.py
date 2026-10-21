from typing import Optional, List
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.materia_instancia_evaluacion import (
    MateriaInstanciaEvaluacion,
    InstanciaEvaluacionCreate,
    InstanciaEvaluacionUpdate,
)


class InstanciaEvaluacionService(BaseServiceWithFilters[MateriaInstanciaEvaluacion]):
    def __init__(self):
        super().__init__(MateriaInstanciaEvaluacion)

    def get_by_id(
        self, instancia_id: int, session: Session
    ) -> Optional[MateriaInstanciaEvaluacion]:
        return session.exec(
            select(MateriaInstanciaEvaluacion).where(
                MateriaInstanciaEvaluacion.id == instancia_id
            )
        ).first()

    def get_by_instancia_cursado(
        self, instancia_cursado_id: int, session: Session
    ) -> List[MateriaInstanciaEvaluacion]:
        """Obtiene instancias de evaluación de una instancia de cursado."""
        return list(session.exec(
            select(MateriaInstanciaEvaluacion)
            .where(
                MateriaInstanciaEvaluacion.instancia_cursado_id == instancia_cursado_id,
            )
            .order_by(MateriaInstanciaEvaluacion.orden)
        ).all())

    def _validar_suma_pesos(
        self,
        instancia_cursado_id: int,
        peso_nuevo,
        session: Session,
        excluir_id: Optional[int] = None,
    ) -> None:
        """
        Los pesos de las evaluaciones no pueden pasarse de la nota máxima de la
        política de la materia.

        Si se pasan, un alumno puede acumular más de la nota máxima y exonerar
        con menos de lo que la política pide. Si quedan cortos, el techo alcanzable
        puede caer por debajo del umbral de aprobación y se reprueba el curso
        entero de forma automática, sin que nadie lo note hasta ver las actas.

        excluir_id: al actualizar, la evaluación que se está editando no cuenta
        con su peso viejo.
        """
        from decimal import Decimal
        from v2.models.instancia_cursado import InstanciaCursado
        from v2.models.materia import Materia
        from v2.models.politica_calificacion import PoliticaCalificacion

        instancia_cursado = session.get(InstanciaCursado, instancia_cursado_id)
        if not instancia_cursado:
            return
        materia = session.get(Materia, instancia_cursado.materia_id)
        if not materia or not materia.politica_id:
            return  # sin política no hay techo contra el cual comparar
        politica = session.get(PoliticaCalificacion, materia.politica_id)
        if not politica or politica.nota_maxima is None:
            return

        stmt = select(MateriaInstanciaEvaluacion).where(
            MateriaInstanciaEvaluacion.instancia_cursado_id == instancia_cursado_id,
            MateriaInstanciaEvaluacion.activo == True,
        )
        if excluir_id is not None:
            stmt = stmt.where(MateriaInstanciaEvaluacion.id != excluir_id)

        suma_actual = sum(
            (ev.peso_maximo or Decimal("0")) for ev in session.exec(stmt).all()
        )
        total = suma_actual + (peso_nuevo or Decimal("0"))

        if total > politica.nota_maxima:
            raise ValueError(
                f"Los pesos de las evaluaciones sumarian {total}, y la politica "
                f"'{politica.nombre}' tiene nota_maxima {politica.nota_maxima}. "
                f"Ya hay {suma_actual} asignados en esta cursada."
            )

    def create(
        self, data: InstanciaEvaluacionCreate, session: Session
    ) -> MateriaInstanciaEvaluacion:
        # Validar que la instancia de cursado exista
        from v2.models.instancia_cursado import InstanciaCursado
        instancia_cursado = session.get(InstanciaCursado, data.instancia_cursado_id)
        if not instancia_cursado:
            raise ValueError(f"Instancia de cursado {data.instancia_cursado_id} no encontrada")

        self._validar_suma_pesos(
            data.instancia_cursado_id, data.peso_maximo, session
        )

        instancia = MateriaInstanciaEvaluacion(**data.model_dump())
        session.add(instancia)
        session.commit()
        session.refresh(instancia)
        return instancia

    def update(
        self,
        instancia_id: int,
        data: InstanciaEvaluacionUpdate,
        session: Session,
    ) -> MateriaInstanciaEvaluacion:
        instancia = self.get_by_id(instancia_id, session)
        if not instancia:
            raise ValueError(f"Instancia de evaluacion {instancia_id} no encontrada")

        update_data = data.model_dump(exclude_unset=True)

        # Si cambia el peso, se revalida el total sin contar el peso viejo de esta
        peso_nuevo = update_data.get("peso_maximo", instancia.peso_maximo)
        if "peso_maximo" in update_data or "activo" in update_data:
            if update_data.get("activo", instancia.activo):
                self._validar_suma_pesos(
                    instancia.instancia_cursado_id, peso_nuevo, session,
                    excluir_id=instancia.id,
                )

        for key, value in update_data.items():
            setattr(instancia, key, value)

        session.add(instancia)
        session.commit()
        session.refresh(instancia)
        return instancia

    def delete(self, instancia_id: int, session: Session) -> None:
        instancia = self.get_by_id(instancia_id, session)
        if not instancia:
            raise ValueError(f"Instancia de evaluacion {instancia_id} no encontrada")

        # Verificar que no tenga calificaciones
        from v2.models.calificacion import Calificacion
        calificacion = session.exec(
            select(Calificacion).where(
                Calificacion.instancia_evaluacion_id == instancia_id
            )
        ).first()
        if calificacion:
            raise ValueError(
                "No se puede eliminar: la instancia tiene calificaciones registradas"
            )

        session.delete(instancia)
        session.commit()
