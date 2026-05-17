# Importar todos los modelos para que SQLModel.metadata los registre
# Necesario para alembic autogenerate

from v2.models.enums import (
    RolUsuario, TipoPrograma, TipoNota,
    EstadoInscripcionMateria, EstadoInscripcionExamen,
    TipoPreviatura, RolDocente,
    AreaPrograma, EstadoInstanciaCursado, EstadoInscripcionPrograma,
    ModalidadExamen, TipoExamen, EstadoInstanciaExamen,
    CargoDocente, DedicacionDocente,
    TipoDocumento,
)

from v2.models.usuario import Usuario
from v2.models.alumno import Alumno
from v2.models.profesor import Profesor
from v2.models.administrativo import Administrativo
from v2.models.politica_calificacion import PoliticaCalificacion
from v2.models.politica_examen import PoliticaExamen
from v2.models.programa import Programa
from v2.models.materia import Materia
from v2.models.instancia_cursado import InstanciaCursado
from v2.models.materia_instancia_evaluacion import MateriaInstanciaEvaluacion
from v2.models.previatura import Previatura
from v2.models.docente_materia import DocenteMateria
from v2.models.inscripcion_materia import InscripcionMateria
from v2.models.calificacion import Calificacion
from v2.models.equipo import Equipo, EquipoMiembro
from v2.models.periodo_inscripcion_materia import PeriodoInscripcionMateria
from v2.models.instancia_examen import InstanciaExamen
from v2.models.docente_instancia_examen import DocenteInstanciaExamen
from v2.models.inscripcion_programa import InscripcionPrograma
from v2.models.inscripcion_examen import InscripcionExamen
from v2.models.documento_usuario import DocumentoUsuario
