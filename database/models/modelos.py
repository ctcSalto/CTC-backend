from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from enum import Enum
import json

# Enums
class RamaEnum(str, Enum):
    INGENIERIA = "ingenieria"
    CIENCIAS = "ciencias"
    HUMANIDADES = "humanidades"
    MEDICINA = "medicina"
    DERECHO = "derecho"
    ECONOMIA = "economia"

class TipoAprobacionEnum(str, Enum):
    CURSO = "curso"
    EXAMEN = "examen"
    EQUIVALENCIA = "equivalencia"
    REVALIDACION = "revalidacion"

class EstadoExamenEnum(str, Enum):
    PROGRAMADO = "programado"
    EN_CURSO = "en_curso"
    FINALIZADO = "finalizado"
    CANCELADO = "cancelado"

class EstadoInscripcionEnum(str, Enum):
    ACTIVO = "activo"
    RETIRADO = "retirado"
    FINALIZADO = "finalizado"
    SUSPENDIDO = "suspendido"

class RolEnum(str, Enum):
    ESTUDIANTE = "estudiante"
    DOCENTE = "docente"
    ADMINISTRADOR = "administrador"
    COORDINADOR = "coordinador"

class TipoPagoEnum(str, Enum):
    INSCRIPCION = "inscripcion"
    CURSO = "curso"
    EXAMEN = "examen"
    CERTIFICADO = "certificado"
    OTRO = "otro"

class MetodoPagoEnum(str, Enum):
    TARJETA = "tarjeta"
    TRANSFERENCIA = "transferencia"
    EFECTIVO = "efectivo"
    PAYPAL = "paypal"
    MERCADOPAGO = "mercadopago"

class EstadoPagoEnum(str, Enum):
    PENDIENTE = "pendiente"
    PROCESANDO = "procesando"
    COMPLETADO = "completado"
    FALLIDO = "fallido"
    CANCELADO = "cancelado"
    REEMBOLSADO = "reembolsado"

# --- USUARIO ---

# --> Colocarle imagen de perfil?
class UsuarioBase(SQLModel):
    moodle_user_id: Optional[int] = None
    email: str = Field(unique=True, index=True)
    username: str = Field(unique=True, index=True)
    nombre: str
    apellido: str
    telefono: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    documento: Optional[str] = Field(default=None, unique=True)
    direccion: Optional[str] = None
    rol: RolEnum
    activo: bool = True
    ultimo_acceso: Optional[datetime] = None
    embedding: Optional[str] = None  # Cambia a vector si usas pgvector

class Usuario(UsuarioBase, table=True):
    __tablename__ = "usuarios"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_creacion: datetime = Field(default_factory=datetime.now)
    fecha_actualizacion: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    cursos_dictados: List["Curso"] = Relationship(back_populates="docente")
    inscripciones_cursos: List["InscripcionCurso"] = Relationship(back_populates="estudiante")
    inscripciones_examenes: List["InscripcionExamen"] = Relationship(back_populates="estudiante")
    calificaciones_cursos: List["CalificacionCurso"] = Relationship(back_populates="estudiante")
    pagos: List["Pago"] = Relationship(back_populates="usuario")
    noticias: List["Noticia"] = Relationship(back_populates="autor")

class UsuarioCreate(UsuarioBase):
    pass

class UsuarioRead(UsuarioBase):
    id: int
    fecha_creacion: datetime
    fecha_actualizacion: datetime

class UsuarioUpdate(SQLModel):
    email: Optional[str] = None
    username: Optional[str] = None
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    telefono: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    documento: Optional[str] = None
    direccion: Optional[str] = None
    rol: Optional[RolEnum] = None
    activo: Optional[bool] = None

# --- CARRERAS ---
class CarreraBase(SQLModel):
    nombre: str
    descripcion: Optional[str] = None
    rama: RamaEnum
    duracion_semestres: int = Field(default=8, gt=0)
    creditos_totales: int = Field(default=240, gt=0)
    codigo: str = Field(unique=True)
    activa: bool = True
    embedding: Optional[str] = None

class Carrera(CarreraBase, table=True):
    __tablename__ = "carreras"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_creacion: datetime = Field(default_factory=datetime.now)
    fecha_actualizacion: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    materias: List["Materia"] = Relationship(back_populates="carrera")

class CarreraCreate(CarreraBase):
    pass

class CarreraRead(CarreraBase):
    id: int
    fecha_creacion: datetime
    fecha_actualizacion: datetime

# --- MATERIAS ---
class MateriaBase(SQLModel):
    nombre: str
    descripcion: Optional[str] = None
    codigo: str = Field(unique=True)
    creditos: int = Field(default=6, gt=0)
    semestre: int = Field(ge=1, le=12)
    carrera_id: int = Field(foreign_key="carreras.id")
    moodle_course_id: Optional[int] = Field(default=None, unique=True)
    activa: bool = True
    embedding: Optional[str] = None

class Materia(MateriaBase, table=True):
    __tablename__ = "materias"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_creacion: datetime = Field(default_factory=datetime.now)
    fecha_actualizacion: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    carrera: Carrera = Relationship(back_populates="materias")
    cursos: List["Curso"] = Relationship(back_populates="materia")
    examenes: List["Examen"] = Relationship(back_populates="materia")
    cursos_comprados: List["CursoComprado"] = Relationship(back_populates="materia")
    previaturas: List["Previatura"] = Relationship(
        back_populates="materia", 
        sa_relationship_kwargs={"foreign_keys": "Previatura.materia_id"}
    )
    previaturas_requeridas: List["Previatura"] = Relationship(
        back_populates="materia_previa",
        sa_relationship_kwargs={"foreign_keys": "Previatura.materia_previa_id"}
    )

class MateriaCreate(MateriaBase):
    pass

class MateriaRead(MateriaBase):
    id: int
    fecha_creacion: datetime
    fecha_actualizacion: datetime

# --- CURSOS ---
class CursoBase(SQLModel):
    materia_id: int = Field(foreign_key="materias.id")
    docente_id: int = Field(foreign_key="usuarios.id")
    nombre: str
    año: int = Field(ge=2020)
    semestre: int = Field(ge=1, le=2)
    fecha_inicio: date
    fecha_fin: date
    cupos_maximos: int = Field(default=30, gt=0)
    moodle_course_instance_id: Optional[int] = None
    activo: bool = True

class Curso(CursoBase, table=True):
    __tablename__ = "cursos"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_creacion: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    materia: Materia = Relationship(back_populates="cursos")
    docente: Usuario = Relationship(back_populates="cursos_dictados")
    inscripciones: List["InscripcionCurso"] = Relationship(back_populates="curso")
    calificaciones: List["CalificacionCurso"] = Relationship(back_populates="curso")
    cursos_comprados: List["CursoComprado"] = Relationship(back_populates="curso")

class CursoCreate(CursoBase):
    pass

class CursoRead(CursoBase):
    id: int
    fecha_creacion: datetime

# --- EXAMENES ---
class ExamenBase(SQLModel):
    materia_id: int = Field(foreign_key="materias.id")
    nombre: str
    descripcion: Optional[str] = None
    fecha_examen: datetime
    duracion_minutos: int = Field(default=120, gt=0)
    calificacion_minima: Decimal = Field(default=Decimal("70.00"), ge=0, le=100)
    lugar: Optional[str] = None
    estado: EstadoExamenEnum = EstadoExamenEnum.PROGRAMADO

class Examen(ExamenBase, table=True):
    __tablename__ = "examenes"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_creacion: datetime = Field(default_factory=datetime.now)
    fecha_actualizacion: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    materia: Materia = Relationship(back_populates="examenes")
    inscripciones: List["InscripcionExamen"] = Relationship(back_populates="examen")
    calificaciones: List["CalificacionCurso"] = Relationship(back_populates="examen")

class ExamenCreate(ExamenBase):
    pass

class ExamenRead(ExamenBase):
    id: int
    fecha_creacion: datetime
    fecha_actualizacion: datetime

# --- INSCRIPCIONES CURSOS ---
class InscripcionCursoBase(SQLModel):
    curso_id: int = Field(foreign_key="cursos.id")
    estudiante_id: int = Field(foreign_key="usuarios.id")
    estado: EstadoInscripcionEnum = EstadoInscripcionEnum.ACTIVO
    calificacion_final: Optional[Decimal] = Field(default=None, ge=0, le=100)
    fecha_calificacion: Optional[datetime] = None
    observaciones: Optional[str] = None

class InscripcionCurso(InscripcionCursoBase, table=True):
    __tablename__ = "inscripciones_cursos"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_inscripcion: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    curso: Curso = Relationship(back_populates="inscripciones")
    estudiante: Usuario = Relationship(back_populates="inscripciones_cursos")

class InscripcionCursoCreate(InscripcionCursoBase):
    pass

class InscripcionCursoRead(InscripcionCursoBase):
    id: int
    fecha_inscripcion: datetime

# --- INSCRIPCIONES EXAMENES ---
class InscripcionExamenBase(SQLModel):
    examen_id: int = Field(foreign_key="examenes.id")
    estudiante_id: int = Field(foreign_key="usuarios.id")
    calificacion: Optional[Decimal] = Field(default=None, ge=0, le=100)
    fecha_calificacion: Optional[datetime] = None
    observaciones: Optional[str] = None
    presente: Optional[bool] = None

class InscripcionExamen(InscripcionExamenBase, table=True):
    __tablename__ = "inscripciones_examenes"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_inscripcion: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    examen: Examen = Relationship(back_populates="inscripciones")
    estudiante: Usuario = Relationship(back_populates="inscripciones_examenes")

class InscripcionExamenCreate(InscripcionExamenBase):
    pass

class InscripcionExamenRead(InscripcionExamenBase):
    id: int
    fecha_inscripcion: datetime

# --- CALIFICACIONES CURSOS ---
class CalificacionCursoBase(SQLModel):
    curso_id: int = Field(foreign_key="cursos.id")
    estudiante_id: int = Field(foreign_key="usuarios.id")
    calificacion_curso: Decimal = Field(ge=0, le=100)
    tipo_aprobacion: TipoAprobacionEnum
    examen_id: Optional[int] = Field(default=None, foreign_key="examenes.id")
    observaciones: Optional[str] = None

class CalificacionCurso(CalificacionCursoBase, table=True):
    __tablename__ = "calificaciones_cursos"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_aprobacion: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    curso: Curso = Relationship(back_populates="calificaciones")
    estudiante: Usuario = Relationship(back_populates="calificaciones_cursos")
    examen: Optional[Examen] = Relationship(back_populates="calificaciones")

class CalificacionCursoCreate(CalificacionCursoBase):
    pass

class CalificacionCursoRead(CalificacionCursoBase):
    id: int
    fecha_aprobacion: datetime

# --- PAGOS ---
class PagoBase(SQLModel):
    usuario_id: int = Field(foreign_key="usuarios.id")
    tipo_pago: TipoPagoEnum
    monto: Decimal = Field(gt=0)
    moneda: str = "USD"
    metodo_pago: MetodoPagoEnum
    estado: EstadoPagoEnum = EstadoPagoEnum.PENDIENTE
    fecha_vencimiento: Optional[datetime] = None
    transaction_id: Optional[str] = None
    descripcion: Optional[str] = None
    datos_pago: Optional[dict] = None

class Pago(PagoBase, table=True):
    __tablename__ = "pagos"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_pago: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    usuario: Usuario = Relationship(back_populates="pagos")
    cursos_comprados: List["CursoComprado"] = Relationship(back_populates="pago")

class PagoCreate(PagoBase):
    pass

class PagoRead(PagoBase):
    id: int
    fecha_pago: datetime

# --- CURSOS COMPRADOS ---
class CursoCompradoBase(SQLModel):
    pago_id: int = Field(foreign_key="pagos.id")
    curso_id: Optional[int] = Field(default=None, foreign_key="cursos.id")
    materia_id: Optional[int] = Field(default=None, foreign_key="materias.id")
    fecha_expiracion: Optional[datetime] = None
    activo: bool = True

class CursoComprado(CursoCompradoBase, table=True):
    __tablename__ = "cursos_comprados"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_compra: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    pago: Pago = Relationship(back_populates="cursos_comprados")
    curso: Optional[Curso] = Relationship(back_populates="cursos_comprados")
    materia: Optional[Materia] = Relationship(back_populates="cursos_comprados")

class CursoCompradoCreate(CursoCompradoBase):
    pass

class CursoCompradoRead(CursoCompradoBase):
    id: int
    fecha_compra: datetime

# --- PREVIATURAS ---
class PreviaturaBase(SQLModel):
    materia_id: int = Field(foreign_key="materias.id")
    materia_previa_id: int = Field(foreign_key="materias.id")
    obligatoria: bool = True

class Previatura(PreviaturaBase, table=True):
    __tablename__ = "previaturas"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_creacion: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    materia: Materia = Relationship(
        back_populates="previaturas",
        sa_relationship_kwargs={"foreign_keys": "Previatura.materia_id"}
    )
    materia_previa: Materia = Relationship(
        back_populates="previaturas_requeridas",
        sa_relationship_kwargs={"foreign_keys": "Previatura.materia_previa_id"}
    )

class PreviaturaCreate(PreviaturaBase):
    pass

class PreviaturaRead(PreviaturaBase):
    id: int
    fecha_creacion: datetime

# --- NOTICIAS ---

# --> Carrusel de imagenes y videos?
class NoticiaBase(SQLModel):
    titulo: str
    resumen: Optional[str] = None
    contenido: str
    autor_id: int = Field(foreign_key="usuarios.id")
    activa: bool = True
    destacada: bool = False
    imagen_url: Optional[str] = None
    slug: Optional[str] = Field(default=None, unique=True)
    tags: Optional[List[str]] = None
    vistas: int = 0
    embedding: Optional[str] = None

class Noticia(NoticiaBase, table=True):
    __tablename__ = "noticias"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    fecha_publicacion: datetime = Field(default_factory=datetime.now)
    fecha_actualizacion: datetime = Field(default_factory=datetime.now)
    
    # Relationships
    autor: Usuario = Relationship(back_populates="noticias")

class NoticiaCreate(NoticiaBase):
    pass

class NoticiaRead(NoticiaBase):
    id: int
    fecha_publicacion: datetime
    fecha_actualizacion: datetime