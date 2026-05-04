from enum import Enum


class RolUsuario(str, Enum):
    ESTUDIANTE = "estudiante"
    DOCENTE = "docente"
    ADMINISTRATIVO = "administrativo"


class TipoPrograma(str, Enum):
    CARRERA = "carrera"
    CURSO_CORTO = "curso_corto"
    TALLER = "taller"
    DIPLOMA = "diploma"


class TipoNota(str, Enum):
    NUMERICA = "numerica"
    LETRA = "letra"
    ESCALA_CUSTOM = "escala_custom"


class EstadoInscripcionMateria(str, Enum):
    CURSANDO = "cursando"
    EXONERADO = "exonerado"
    A_EXAMEN = "a_examen"
    APROBADO = "aprobado"
    REPROBADO = "reprobado"
    PERDIDO_INASISTENCIA = "perdido_inasistencia"
    ABANDONO = "abandono"


class EstadoInscripcionExamen(str, Enum):
    INSCRIPTO = "inscripto"
    APROBADO = "aprobado"
    REPROBADO = "reprobado"
    AUSENTE = "ausente"


class TipoPreviatura(str, Enum):
    APROBADA = "aprobada"       # Requiere APROBADO o EXONERADO
    EXONERADA = "exonerada"     # Requiere solo EXONERADO


class RolDocente(str, Enum):
    TITULAR = "titular"
    ADJUNTO = "adjunto"
    ASISTENTE = "asistente"


class AreaPrograma(str, Enum):
    ADMINISTRACION = "administracion"
    COMUNICACION = "comunicacion"
    CULTURA = "cultura"
    GENERAL = "general"
    INFORMATICA = "informatica"


class EstadoInstanciaCursado(str, Enum):
    PLANIFICADA = "planificada"
    EN_CURSO = "en_curso"
    FINALIZADA = "finalizada"
    CANCELADA = "cancelada"


class EstadoInscripcionPrograma(str, Enum):
    ACTIVA = "activa"
    SUSPENDIDA = "suspendida"
    COMPLETADA = "completada"
    BAJA = "baja"


class ModalidadExamen(str, Enum):
    PRESENCIAL = "presencial"
    VIRTUAL = "virtual"
    HIBRIDO = "hibrido"


class TipoExamen(str, Enum):
    ORDINARIO = "ordinario"
    EXTRAORDINARIO = "extraordinario"


class EstadoInstanciaExamen(str, Enum):
    PROGRAMADO = "programado"
    EN_CURSO = "en_curso"
    FINALIZADO = "finalizado"
    CANCELADO = "cancelado"


class CargoDocente(str, Enum):
    TITULAR = "titular"
    INTERINO = "interino"
    CONTRATO = "contrato"


class DedicacionDocente(str, Enum):
    TIEMPO_COMPLETO = "tiempo_completo"
    MEDIO_TIEMPO = "medio_tiempo"
    HORAS = "horas"
