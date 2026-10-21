from typing import Optional
from decimal import Decimal
from sqlmodel import Session, select

from database.services.filter.filters import BaseServiceWithFilters
from v2.models.politica_calificacion import (
    PoliticaCalificacion,
    PoliticaCalificacionCreate,
    PoliticaCalificacionUpdate,
)


class PoliticaCalificacionService(BaseServiceWithFilters[PoliticaCalificacion]):
    def __init__(self):
        super().__init__(PoliticaCalificacion)

    def get_by_id(self, politica_id: int, session: Session) -> Optional[PoliticaCalificacion]:
        return session.exec(
            select(PoliticaCalificacion).where(PoliticaCalificacion.id == politica_id)
        ).first()

    # ── Validacion de umbrales ───────────────────────────────────────────────

    @staticmethod
    def _validar_umbrales(
        nota_maxima: Optional[Decimal],
        umbral_aprobacion: Optional[Decimal],
        umbral_examen: Optional[Decimal],
        umbral_exoneracion: Optional[Decimal],
    ) -> None:
        """
        Valida que los umbrales sean coherentes entre si.

        El motor de calificaciones evalua la exoneracion ANTES que el examen, asi
        que una politica con exoneracion por debajo del umbral de examen hace que
        los alumnos exoneren en vez de ganar derecho a examen, en silencio y sin
        que nadie lo note hasta ver las actas.
        """
        errores = []

        if nota_maxima is None or nota_maxima <= 0:
            errores.append("nota_maxima debe ser mayor a 0")

        umbrales = (
            ("umbral_aprobacion", umbral_aprobacion),
            ("umbral_examen", umbral_examen),
            ("umbral_exoneracion", umbral_exoneracion),
        )
        for nombre, valor in umbrales:
            if valor is None:
                continue
            if valor < 0:
                errores.append(f"{nombre} no puede ser negativo")
            elif nota_maxima is not None and nota_maxima > 0 and valor > nota_maxima:
                errores.append(
                    f"{nombre} ({valor}) supera nota_maxima ({nota_maxima}): "
                    f"es inalcanzable"
                )

        if umbral_aprobacion is not None and umbral_aprobacion <= 0:
            errores.append(
                "umbral_aprobacion debe ser mayor a 0: en 0 cualquier nota aprueba"
            )

        if (
            umbral_examen is not None
            and umbral_exoneracion is not None
            and umbral_exoneracion <= umbral_examen
        ):
            errores.append(
                f"umbral_exoneracion ({umbral_exoneracion}) debe ser mayor que "
                f"umbral_examen ({umbral_examen}): si no, se exonera antes de "
                f"llegar al derecho a examen"
            )

        if errores:
            raise ValueError("Politica de calificacion invalida: " + "; ".join(errores))

    def create(self, data: PoliticaCalificacionCreate, session: Session) -> PoliticaCalificacion:
        self._validar_umbrales(
            data.nota_maxima, data.umbral_aprobacion,
            data.umbral_examen, data.umbral_exoneracion,
        )
        politica = PoliticaCalificacion(**data.model_dump())
        session.add(politica)
        session.commit()
        session.refresh(politica)
        return politica

    def update(
        self, politica_id: int, data: PoliticaCalificacionUpdate, session: Session
    ) -> PoliticaCalificacion:
        politica = self.get_by_id(politica_id, session)
        if not politica:
            raise ValueError(f"Politica de calificacion {politica_id} no encontrada")

        update_data = data.model_dump(exclude_unset=True)

        # Se valida el resultado combinado, no lo que vino en el body: un update
        # parcial de un solo umbral puede dejar incoherente al conjunto. Y se
        # valida ANTES de mutar, para no dejar el objeto sucio en la sesion si
        # los valores nuevos no pasan.
        combinado = {
            campo: update_data.get(campo, getattr(politica, campo))
            for campo in ("nota_maxima", "umbral_aprobacion",
                          "umbral_examen", "umbral_exoneracion")
        }
        self._validar_umbrales(**combinado)

        for key, value in update_data.items():
            setattr(politica, key, value)

        session.add(politica)
        session.commit()
        session.refresh(politica)
        return politica

    def delete(self, politica_id: int, session: Session) -> None:
        politica = self.get_by_id(politica_id, session)
        if not politica:
            raise ValueError(f"Politica de calificacion {politica_id} no encontrada")

        # Verificar que no tenga materias asignadas
        from v2.models.materia import Materia
        materias = session.exec(
            select(Materia).where(Materia.politica_id == politica_id)
        ).first()
        if materias:
            raise ValueError(
                "No se puede eliminar: hay materias usando esta politica de calificacion"
            )

        session.delete(politica)
        session.commit()
