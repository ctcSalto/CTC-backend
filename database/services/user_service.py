from sqlmodel import Session, select
from ..models.user import User, UserCreate, UserRead, UserUpdate
from typing import List
from sqlalchemy.exc import IntegrityError, NoResultFound
from database.services.auth.security import get_password_hash, verify_password

class UserService:
    
    def create_user(self, user: UserCreate, session: Session) -> UserRead:
        with session:
            user_dict = user.model_dump(exclude={'password'})
            user_dict['password_hash'] = get_password_hash(user.password)
            db_user = User(**user_dict)
            session.add(db_user)
            session.commit()
            session.refresh(db_user)
            return db_user

    def authenticate_user(self, username: str, password: str, session: Session) -> UserRead:
        with session:
            user = session.exec(select(User).where(User.username == username)).first()
            if not verify_password(password, user.password_hash) or not user:
                return None
            return user

    def get_user_by_username(self, username: str, session: Session) -> UserRead:
        with session:
            user = session.exec(select(User).where(User.username == username)).first()
            if not user:
                return None
            return user

    def get_user_by_email(self, email: str, session: Session) -> UserRead:
        with session:
            user = session.exec(select(User).where(User.email == email)).first()
            if not user:
                return None
            return user
        

    def get_user_by_id(self, id: int, session: Session) -> UserRead:
        with session:
            user = session.exec(select(User).where(User.id == id)).first()
            if not user:
                return None
            return user

    def update_user(self, id: int, user_update: UserUpdate, session: Session) -> UserRead:
        with session:
            user = session.exec(select(User).where(User.id == id)).first()
            update_data = user_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(user, key, value)
            user.password_hash = get_password_hash(user.password)
            session.commit()
            session.refresh(user)
            return user

    def delete_user(self, id: int, session: Session) -> bool:
        with session:
            user = session.exec(select(User).where(User.id == id)).first()
            session.delete(user)
            session.commit()
            return True