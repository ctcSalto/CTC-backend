from v2.services.usuario_service import UsuarioService
from v2.services.politica_calificacion_service import PoliticaCalificacionService
from v2.services.politica_examen_service import PoliticaExamenService
from v2.services.programa_service import ProgramaService
from v2.services.materia_service import MateriaService
from v2.services.previatura_service import PreviaturaService
from v2.services.instancia_evaluacion_service import InstanciaEvaluacionService
from v2.services.docente_materia_service import DocenteMateriaService
from v2.services.periodo_inscripcion_service import PeriodoInscripcionService
from v2.services.inscripcion_service import InscripcionMateriaService
from v2.services.calificacion_service import CalificacionService
from v2.services.equipo_service import EquipoService
from v2.services.inscripcion_examen_service import InscripcionExamenService
from v2.services.inscripcion_programa_service import InscripcionProgramaService
from v2.services.instancia_cursado_service import InstanciaCursadoService
from v2.services.instancia_examen_service import InstanciaExamenService
from v2.services.egreso_service import EgresoService
from v2.services.local_file_service import LocalFileService
from v2.services.email_service import EmailService
from v2.services.notification_service import NotificationService
from v2.services.proximos_eventos_service import ProximosEventosService


class V2Services:
    def __init__(self):
        self.usuarioService = UsuarioService()
        self.politicaCalificacionService = PoliticaCalificacionService()
        self.politicaExamenService = PoliticaExamenService()
        self.programaService = ProgramaService()
        self.materiaService = MateriaService()
        self.previaturaService = PreviaturaService()
        self.instanciaEvaluacionService = InstanciaEvaluacionService()
        self.docenteMateriaService = DocenteMateriaService()
        self.periodoInscripcionService = PeriodoInscripcionService()
        self.inscripcionService = InscripcionMateriaService()
        self.calificacionService = CalificacionService()
        self.equipoService = EquipoService()
        self.instanciaExamenService = InstanciaExamenService()
        self.inscripcionExamenService = InscripcionExamenService()
        self.inscripcionProgramaService = InscripcionProgramaService()
        self.instanciaCursadoService = InstanciaCursadoService()
        self.egresoService = EgresoService()
        self.localFileService = LocalFileService()
        self.emailService = EmailService()
        self.notificationService = NotificationService()
        self.proximosEventosService = ProximosEventosService()


_v2_services: V2Services | None = None


def get_v2_services() -> V2Services:
    global _v2_services
    if _v2_services is None:
        _v2_services = V2Services()
    return _v2_services
