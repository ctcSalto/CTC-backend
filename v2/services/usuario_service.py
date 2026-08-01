from sqlmodel import Session, select, func, or_
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

    def get_by_email(self, email: Optional[str], session: Session) -> Optional[Usuario]:
        # Guard: `email` es nullable (oyentes sin cuenta). Sin esto, un None generaría
        # `WHERE email = NULL` y devolvería siempre None de forma silenciosa; peor,
        # cualquier lookup accidental con None quedaría enmascarado como "no existe".
        if not email:
            return None
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

    def create_manual(
        self,
        nombre: str,
        apellido: str,
        rol: RolUsuario,
        session: Session,
        email: Optional[str] = None,
        documento: Optional[str] = None,
        telefono: Optional[str] = None,
        email_personal: Optional[str] = None,
        perfil: Optional[dict] = None,
    ) -> Usuario:
        """
        Crea un usuario manualmente (admin), sin requerir login de Google.
        Util para ponentes que dan una charla puntual o asistentes a charlas
        que deben quedar registrados pero nunca inician sesion en el portal.

        `email` es opcional: un oyente de una charla puede no tener cuenta
        institucional ni email que queramos almacenar. Si se provee y la persona
        luego inicia sesion con Google usando ese mismo email, el callback de
        OAuth la encuentra y vincula la cuenta (ver v2/routes/auth_google.py).

        Se crea con `activo=False` porque no tiene acceso al portal. Si mas
        adelante inicia sesion con Google, el callback lo reactiva.
        """
        if email and self.get_by_email(email, session):
            raise ValueError(f"Ya existe un usuario con el email {email}")

        usuario = Usuario(
            email=email,
            nombre=nombre,
            apellido=apellido,
            documento=documento,
            telefono=telefono,
            email_personal=email_personal,
            rol=rol,
            activo=False,
            google_activo=False,
            moodle_activo=False,
            fecha_creacion=datetime.now(get_uruguay_tz()),
        )
        session.add(usuario)
        session.flush()
        session.refresh(usuario)

        self._auto_crear_perfil(usuario, session, perfil)

        return usuario

    def _auto_crear_perfil(self, usuario: Usuario, session: Session, perfil: Optional[dict] = None):
        """
        Crea automáticamente el perfil correspondiente según el rol del usuario.
        `perfil` permite pasar los campos propios del perfil en el alta manual.
        """
        datos = perfil or {}
        if usuario.rol == RolUsuario.ESTUDIANTE:
            self.crear_perfil_alumno(
                usuario.id, session,
                fecha_ingreso=datos.get("fecha_ingreso"),
            )
        elif usuario.rol == RolUsuario.DOCENTE:
            self.crear_perfil_profesor(
                usuario.id, session,
                cargo=datos.get("cargo"),
                dedicacion=datos.get("dedicacion"),
                especialidad=datos.get("especialidad"),
                carga_horaria_semanal=datos.get("carga_horaria_semanal"),
            )
        elif usuario.rol == RolUsuario.ADMINISTRATIVO:
            self.crear_perfil_administrativo(
                usuario.id, session,
                departamento=datos.get("departamento"),
            )

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
        google_id: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Usuario:
        """
        Actualiza datos del usuario en cada login (re-sync).

        Si el usuario habia sido creado manualmente (sin google_id) y ahora
        inicia sesion con Google, se vincula la cuenta: se guarda el google_id,
        se completa el email si faltaba y se lo activa. Sin esto, el vinculo
        nunca se persistia y la persona quedaba bloqueada por activo=False.

        Un usuario que YA tenia google_id y esta inactivo fue desactivado a
        proposito por un administrador: no se reactiva.
        """
        primer_vinculo_google = usuario.google_id is None

        usuario.nombre = nombre
        usuario.apellido = apellido
        usuario.foto_url = foto_url
        usuario.ou_google = ou_google
        usuario.rol = rol
        usuario.ultimo_acceso = datetime.now(get_uruguay_tz())
        usuario.google_activo = True

        if primer_vinculo_google and google_id is not None:
            usuario.google_id = google_id
            if not usuario.email and email:
                usuario.email = email
            usuario.activo = True

        if moodle_id is not None:
            usuario.moodle_id = moodle_id
            usuario.moodle_activo = True

        session.flush()

        # El rol se re-sincroniza desde la OU en cada login. Si cambio (o si el
        # perfil nunca se creo), hay que garantizar que exista: las inscripciones
        # y asignaciones docentes referencian alumno.id / profesor.id, no usuario.id.
        # Es idempotente: si el perfil ya existe, no hace nada.
        self._auto_crear_perfil(usuario, session)

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

    def crear_perfil_alumno(
        self, usuario_id: int, session: Session,
        fecha_ingreso=None,
    ) -> Alumno:
        """Crea perfil de alumno para un usuario existente. Idempotente."""
        existente = session.exec(
            select(Alumno).where(Alumno.usuario_id == usuario_id)
        ).first()
        if existente:
            return existente
        kwargs = {"usuario_id": usuario_id}
        if fecha_ingreso is not None:
            kwargs["fecha_ingreso"] = fecha_ingreso
        alumno = Alumno(**kwargs)
        session.add(alumno)
        session.flush()
        session.refresh(alumno)
        return alumno

    def crear_perfil_profesor(
        self, usuario_id: int, session: Session,
        cargo=None, dedicacion=None, especialidad=None,
        carga_horaria_semanal=None,
    ) -> Profesor:
        """Crea perfil de profesor para un usuario existente. Idempotente."""
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
            carga_horaria_semanal=carga_horaria_semanal,
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

    # ── Dashboards de admin ──────────────────────────────────────────────

    def get_alumnos_dashboard(
        self,
        session: Session,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None,
        activo: Optional[bool] = None,
    ) -> dict:
        """
        Lista paginada de alumnos para el dashboard de admin, con datos de
        usuario embebidos. Incluye tanto alumnos con cuenta de Google como
        los creados manualmente (ej: asistentes a charlas) via tiene_login.
        """
        base_filters = [Usuario.eliminado == False]
        if activo is not None:
            base_filters.append(Usuario.activo == activo)
        if search:
            like = f"%{search}%"
            base_filters.append(
                or_(Usuario.nombre.ilike(like), Usuario.apellido.ilike(like), Usuario.email.ilike(like))
            )

        count_stmt = (
            select(func.count())
            .select_from(Alumno)
            .join(Usuario, Alumno.usuario_id == Usuario.id)
            .where(*base_filters)
        )
        total = session.exec(count_stmt).one()

        stmt = (
            select(Alumno, Usuario)
            .join(Usuario, Alumno.usuario_id == Usuario.id)
            .where(*base_filters)
            .order_by(Usuario.apellido, Usuario.nombre)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        rows = session.exec(stmt).all()

        items = [
            {
                "id": alumno.id,
                "usuario_id": usuario.id,
                "nombre": usuario.nombre,
                "apellido": usuario.apellido,
                "email": usuario.email,
                "documento": usuario.documento,
                "telefono": usuario.telefono,
                "activo": usuario.activo,
                "tiene_login": usuario.google_id is not None,
                "fecha_ingreso": alumno.fecha_ingreso,
            }
            for alumno, usuario in rows
        ]

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if total > 0 else 0,
        }

    def get_docentes_dashboard(
        self,
        session: Session,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None,
        activo: Optional[bool] = None,
        activo_docente: Optional[bool] = None,
    ) -> dict:
        """
        Lista paginada de docentes para el dashboard de admin, con datos de
        usuario embebidos. Incluye tanto docentes con cuenta de Google como
        los creados manualmente (ej: ponentes de una charla puntual).

        activo: filtra por acceso al sistema (usuario.activo)
        activo_docente: filtra por si dicta actualmente (profesor.activo)
        """
        base_filters = [Usuario.eliminado == False]
        if activo is not None:
            base_filters.append(Usuario.activo == activo)
        if activo_docente is not None:
            base_filters.append(Profesor.activo == activo_docente)
        if search:
            like = f"%{search}%"
            base_filters.append(
                or_(Usuario.nombre.ilike(like), Usuario.apellido.ilike(like), Usuario.email.ilike(like))
            )

        count_stmt = (
            select(func.count())
            .select_from(Profesor)
            .join(Usuario, Profesor.usuario_id == Usuario.id)
            .where(*base_filters)
        )
        total = session.exec(count_stmt).one()

        stmt = (
            select(Profesor, Usuario)
            .join(Usuario, Profesor.usuario_id == Usuario.id)
            .where(*base_filters)
            .order_by(Usuario.apellido, Usuario.nombre)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        rows = session.exec(stmt).all()

        items = [
            {
                "id": profesor.id,
                "usuario_id": usuario.id,
                "nombre": usuario.nombre,
                "apellido": usuario.apellido,
                "email": usuario.email,
                "documento": usuario.documento,
                "telefono": usuario.telefono,
                "activo": usuario.activo,
                "activo_docente": profesor.activo,
                "tiene_login": usuario.google_id is not None,
                "cargo": profesor.cargo,
                "dedicacion": profesor.dedicacion,
                "especialidad": profesor.especialidad,
                "carga_horaria_semanal": profesor.carga_horaria_semanal,
            }
            for profesor, usuario in rows
        ]

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if total > 0 else 0,
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
