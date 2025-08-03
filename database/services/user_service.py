from sqlmodel import Session, select
from ..models.user import User, UserCreate, UserRead, UserUpdate
from typing import List, Optional
from sqlalchemy.exc import IntegrityError, NoResultFound
from database.services.auth.security import get_password_hash, verify_password
from datetime import date
from database.services.filter.filters import BaseServiceWithFilters

from utils.logger import show

class UserService(BaseServiceWithFilters[User]):
    def __init__(self):
        super().__init__(User)
    
    def create_user(self, user: UserCreate, session: Session) -> UserRead:
        """Crea un nuevo usuario"""
        try:
            user_dict = user.model_dump(exclude={'password'})
            user_dict['password'] = get_password_hash(user.password)  # Cambiado de password_hash a password
            db_user = User(**user_dict)
            session.add(db_user)
            session.commit()
            session.refresh(db_user)
            return UserRead.model_validate(db_user)
        except IntegrityError as e:
            session.rollback()
            raise ValueError("Email o documento ya existe") from e

    def authenticate_user(self, email: str, password: str, session: Session) -> Optional[UserRead]:
        """Autentica un usuario por email y contraseña"""
        user = session.exec(select(User).where(User.email == email)).first()
        
        if not user:
            return None
        if not verify_password(password, user.password):
            return None
        
        # Actualizar último acceso
        user.lastAccess = date.today()
        session.commit()
        session.refresh(user)
        
        return UserRead.model_validate(user)

    def get_user_by_email(self, email: str, session: Session) -> Optional[UserRead]:
        """Obtiene un usuario por email"""
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            return None
        return UserRead.model_validate(user)

    def get_user_by_document(self, document: str, session: Session) -> Optional[UserRead]:
        """Obtiene un usuario por documento"""
        user = session.exec(select(User).where(User.document == document)).first()
        if not user:
            return None
        return UserRead.model_validate(user)

    def get_user_by_id(self, userId: int, session: Session) -> Optional[UserRead]:
        """Obtiene un usuario por ID"""
        user = session.exec(select(User).where(User.userId == userId)).first()
        if not user:
            return None
        return UserRead.model_validate(user)

    def get_all_users(self, session: Session, skip: int = 0, limit: int = 100) -> List[UserRead]:
        """Obtiene todos los usuarios con paginación"""
        users = session.exec(select(User).offset(skip).limit(limit)).all()
        return [UserRead.model_validate(user) for user in users]

    def get_active_users(self, session: Session, skip: int = 0, limit: int = 100) -> List[UserRead]:
        """Obtiene solo usuarios activos"""
        users = session.exec(
            select(User).where(User.active == True).offset(skip).limit(limit)
        ).all()
        return [UserRead.model_validate(user) for user in users]

    def update_user(self, userId: int, user_update: UserUpdate, session: Session) -> Optional[UserRead]:
        """Actualiza un usuario"""
        try:
            user = session.exec(select(User).where(User.userId == userId)).first()
            if not user:
                return None
            
            update_data = user_update.model_dump(exclude_unset=True, exclude={'password'})
            
            # Actualizar campos básicos
            for key, value in update_data.items():
                setattr(user, key, value)
            
            # Manejar contraseña por separado si se proporciona
            if user_update.password is not None:
                user.password = get_password_hash(user_update.password)
            
            # Actualizar fecha de modificación
            user.modificationDate = date.today()
            
            session.commit()
            session.refresh(user)
            return UserRead.model_validate(user)
            
        except IntegrityError as e:
            session.rollback()
            raise ValueError("Email o documento ya existe") from e
        except Exception as e:
            session.rollback()
            raise ValueError("Error al actualizar el usuario") from e

    def deactivate_user(self, userId: int, session: Session) -> Optional[UserRead]:
        """Desactiva un usuario (soft delete)"""
        user = session.exec(select(User).where(User.userId == userId)).first()
        if not user:
            return None
        
        user.active = False
        user.modificationDate = date.today()
        session.commit()
        session.refresh(user)
        return UserRead.model_validate(user)

    def activate_user(self, userId: int, session: Session) -> Optional[UserRead]:
        """Activa un usuario"""
        user = session.exec(select(User).where(User.userId == userId)).first()
        show(user)
        if not user:
            return None
        
        user.active = True
        user.modificationDate = date.today()
        session.commit()
        session.refresh(user)
        return UserRead.model_validate(user)

    def confirm_user(self, userId: int, session: Session) -> Optional[UserRead]:
        """Confirma un usuario"""
        try:
            user = session.exec(select(User).where(User.userId == userId)).first()
            show(user)
            if not user:
                return None
            
            user.confirmed = True
            user.modificationDate = date.today()
            session.commit()
            session.refresh(user)
            return UserRead.model_validate(user)
        except IntegrityError as e:
            session.rollback()
            raise ValueError("Error al confirmar el usuario") from e

    def delete_user(self, userId: int, session: Session) -> Optional[UserRead]:
        """Elimina un usuario permanentemente y retorna el usuario eliminado"""
        try:
            user = session.exec(select(User).where(User.userId == userId)).first()
            if not user:
                return None
            
            user.active = False  # Soft delete
            user.modificationDate = date.today()
            session.commit()
            
            return user
        except Exception as e:
            session.rollback()
            raise ValueError(f"Error al eliminar el usuario: {str(e)}") from e

    def user_exists_by_email(self, email: str, session: Session) -> bool:
        """Verifica si existe un usuario con el email dado"""
        user = session.exec(select(User).where(User.email == email)).first()
        return user is not None

    def user_exists_by_document(self, document: str, session: Session) -> bool:
        """Verifica si existe un usuario con el documento dado"""
        user = session.exec(select(User).where(User.document == document)).first()
        return user is not None