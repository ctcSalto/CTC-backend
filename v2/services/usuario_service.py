from sqlmodel import Session, select
from typing import Optional, List
from datetime import datetime

from v2.models.usuario import Usuario, UsuarioRead, UsuarioUpdate, get_uruguay_tz
from v2.models.alumno import Alumno
from v2.models.profesor import Profesor
from v2.models.administrativo import Administrativo
from v2.models.enums import RolUsuario
from database.services.filter.filters import BaseServiceWithFilters


class UsuarioService(BaseServiceWithFilters[Usuario]):
    def __init__(self):
        super().__init__(Usuario)

    def get_by_google_id(self, google_id: str, session: Session) -> Optional[Usuario]:
        return session.exec(select(Usuario).where(Usuario.google_id == google_id)).first()

    def get_by_email(self, email: str, session: Session) -> Optional[Usuario]:
        return session.exec(select(Usuario).where(Usuario.email == email)).first()

    def get_by_id(self, usuario_id: int, session: Session) -> Optional[Usuario]:
        return session.exec(select(Usuario).where(Usuario.id == usuario_id)).first()

    def create_from_google(
        self,
        google_id: str,
        email: str,
        nombre: str,
        apellido: str,
        foto_url: Optional[str],
        ou_google: Optional[str],
        rol: RolUsuario,
        moodle_id: Optional[int],
        session: Session,
    ) -> Usuario:
        """Crea un usuario nuevo desde el login de Google OAuth."""
        usuario = Usuario(
            google_id=google_id,
            email=email,
            nombre=nombre,
            apellido=apellido,
            foto_url=foto_url,
            ou_google=ou_google,
            rol=rol,
            moodle_id=moodle_id,
            activo=True,
            google_activo=True,
            moodle_activo=moodle_id is not None,
            fecha_creacion=datetime.now(get_uruguay_tz()),
            ultimo_acceso=datetime.now(get_uruguay_tz()),
        )
        session.add(usuario)
        session.flush()  # Para obtener el ID sin commit (lo hace el middleware)
        session.refresh(usuario)

        # Auto-crear perfil según rol/OU
        self._auto_crear_perfil(usuario, session)

        return usuario

    def _auto_crear_perfil(self, usuario: Usuario, session: Session):
        """Crea automáticamente el perfil correspondiente según el rol del usuario."""
        if usuario.rol == RolUsuario.ESTUDIANTE:
            self.crear_perfil_alumno(usuario.id, session)
        elif usuario.rol == RolUsuario.DOCENTE:
            self.crear_perfil_profesor(usuario.id, session)
        elif usuario.rol == RolUsuario.ADMINISTRATIVO:
            self.crear_perfil_administrativo(usuario.id, session)

    def update_on_login(
        self,
        usuario: Usuario,
        nombre: str,
        apellido: str,
        foto_url: Optional[str],
        ou_google: Optional[str],
        rol: RolUsuario,
        moodle_id: Optional[int],
        session: Session,
    ) -> Usuario:
        """Actualiza datos del usuario en cada login (re-sync)."""
        usuario.nombre = nombre
        usuario.apellido = apellido
        usuario.foto_url = foto_url
        usuario.ou_google = ou_google
        usuario.rol = rol
        usuario.ultimo_acceso = datetime.now(get_uruguay_tz())
        usuario.google_activo = True

        if moodle_id is not None:
            usuario.moodle_id = moodle_id
            usuario.moodle_activo = True

        session.flush()
        session.refresh(usuario)
        return usuario

    def update_usuario(self, usuario_id: int, data: UsuarioUpdate, session: Session) -> Optional[Usuario]:
        usuario = self.get_by_id(usuario_id, session)
        if not usuario:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(usuario, key, value)

        session.flush()
        session.refresh(usuario)
        return usuario

    def get_all(self, session: Session, skip: int = 0, limit: int = 100) -> List[Usuario]:
        return list(session.exec(select(Usuario).offset(skip).limit(limit)).all())

    def to_read(self, usuario: Usuario) -> UsuarioRead:
        return UsuarioRead.model_validate(usuario)

    # ── Perfiles de herencia ─────────────────────────────────────────────

    def crear_perfil_alumno(self, usuario_id: int, session: Session) -> Alumno:
        """Crea perfil de alumno para un usuario existente."""
        existente = session.exec(
            select(Alumno).where(Alumno.usuario_id == usuario_id)
        ).first()
        if existente:
            return existente
        alumno = Alumno(usuario_id=usuario_id)
        session.add(alumno)
        session.flush()
        session.refresh(alumno)
        return alumno

    def crear_perfil_profesor(
        self, usuario_id: int, session: Session,
        cargo=None, dedicacion=None, especialidad=None,
    ) -> Profesor:
        """Crea perfil de profesor para un usuario existente."""
        existente = session.exec(
            select(Profesor).where(Profesor.usuario_id == usuario_id)
        ).first()
        if existente:
            return existente
        profesor = Profesor(
            usuario_id=usuario_id,
            cargo=cargo,
            dedicacion=dedicacion,
            especialidad=especialidad,
        )
        session.add(profesor)
        session.flush()
        session.refresh(profesor)
        return profesor

    def crear_perfil_administrativo(
        self, usuario_id: int, session: Session,
        departamento=None,
    ) -> Administrativo:
        """Crea perfil de administrativo para un usuario existente."""
        existente = session.exec(
            select(Administrativo).where(Administrativo.usuario_id == usuario_id)
        ).first()
        if existente:
            return existente
        admin = Administrativo(
            usuario_id=usuario_id,
            departamento=departamento,
        )
        session.add(admin)
        session.flush()
        session.refresh(admin)
        return admin

    def get_perfiles(self, usuario_id: int, session: Session) -> dict:
        """Retorna los perfiles activos de un usuario."""
        alumno = session.exec(
            select(Alumno).where(Alumno.usuario_id == usuario_id)
        ).first()
        profesor = session.exec(
            select(Profesor).where(Profesor.usuario_id == usuario_id)
        ).first()
        administrativo = session.exec(
            select(Administrativo).where(Administrativo.usuario_id == usuario_id)
        ).first()
        return {
            "alumno": alumno,
            "profesor": profesor,
            "administrativo": administrativo,
        }

    def soft_delete(self, usuario_id: int, session: Session) -> Optional[Usuario]:
        """Eliminación lógica de un usuario."""
        usuario = self.get_by_id(usuario_id, session)
        if not usuario:
            return None
        usuario.eliminado = True
        usuario.fecha_eliminacion = datetime.now(get_uruguay_tz())
        usuario.activo = False
        session.flush()
        session.refresh(usuario)
        return usuario
