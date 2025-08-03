from sqlmodel import Session, select
from ..models.career import Career, CareerCreate, CareerRead, CareerUpdate, CareerInList
from typing import List, Optional
from sqlalchemy.exc import IntegrityError, NoResultFound
from datetime import datetime

from database.services.filter.filters import BaseServiceWithFilters

class CareerService(BaseServiceWithFilters[Career]):
    def __init__(self):
        super().__init__(Career)

    def create_career(self, career: CareerCreate, session: Session) -> CareerRead:
        """Crear una nueva carrera"""
        with session:
            new_career = Career(**career.model_dump())
            session.add(new_career)
            session.commit()
            session.refresh(new_career)
            return CareerRead.model_validate(new_career)

    def get_careers(self, session: Session, offset: int = 0, limit: int = 10) -> List[CareerRead]:
        """Obtener lista de carreras con paginación"""
        with session:
            statement = select(Career).offset(offset).limit(limit)
            careers = session.exec(statement).all()
            if not careers:
                return []
            return [CareerRead.model_validate(career) for career in careers]

    def get_careers_in_list(self, session: Session, offset: int = 0, limit: int = 10) -> List[CareerInList]:
        """Obtener lista simplificada de carreras para listados"""
        with session:
            statement = select(Career).offset(offset).limit(limit)
            careers = session.exec(statement).all()
            if not careers:
                return []
            return [CareerInList.model_validate(career) for career in careers]

    def get_published_careers(self, session: Session, offset: int = 0, limit: int = 10) -> List[CareerRead]:
        """Obtener solo las carreras publicadas"""
        with session:
            statement = select(Career).where(Career.published == True).offset(offset).limit(limit)
            careers = session.exec(statement).all()
            if not careers:
                return []
            return [CareerRead.model_validate(career) for career in careers]

    def get_career_by_id(self, career_id: int, session: Session) -> CareerRead:
        """Obtener una carrera por su ID"""
        with session:
            statement = select(Career).where(Career.careerId == career_id)
            career = session.exec(statement).one()
            if not career:
                return None
            return CareerRead.model_validate(career)

    def get_careers_by_area(self, area: str, session: Session, offset: int = 0, limit: int = 10) -> List[CareerRead]:
        """Obtener carreras por área"""
        with session:
            statement = select(Career).where(Career.area == area).offset(offset).limit(limit)
            careers = session.exec(statement).all()
            if not careers:
                return []
            return [CareerRead.from_orm(career) for career in careers]

    def get_careers_by_type(self, career_type: str, session: Session, offset: int = 0, limit: int = 10) -> List[CareerRead]:
        """Obtener carreras por tipo"""
        with session:
            statement = select(Career).where(Career.careerType == career_type).offset(offset).limit(limit)
            careers = session.exec(statement).all()
            if not careers:
                return []
            return [CareerRead.from_orm(career) for career in careers]

    def get_careers_by_creator(self, creator_id: int, session: Session, offset: int = 0, limit: int = 10) -> List[CareerRead]:
        """Obtener carreras creadas por un usuario específico"""
        with session:
            statement = select(Career).where(Career.creator == creator_id).offset(offset).limit(limit)
            careers = session.exec(statement).all()
            if not careers:
                return []
            return [CareerRead.from_orm(career) for career in careers]

    def update_career(self, career_id: int, career_update: CareerUpdate, session: Session) -> CareerRead:
        """Actualizar una carrera existente"""
        with session:
            statement = select(Career).where(Career.careerId == career_id)
            old_career = session.exec(statement).one()
            
            update_data = career_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(old_career, key, value)
            
            # La fecha de modificación se actualiza automáticamente en CareerUpdate.__init__
            old_career.modificationDate = datetime.now().date()
                
            session.commit()
            session.refresh(old_career)
            return CareerRead.model_validate(old_career)

    def publish_career(self, career_id: int, session: Session) -> CareerRead:
        """Publicar una carrera (marcar como published=True y establecer fecha de publicación)"""
        with session:
            statement = select(Career).where(Career.careerId == career_id)
            career = session.exec(statement).one()
            
            career.published = True
            career.publicationDate = datetime.now().date()
            career.modificationDate = datetime.now().date()
            
            session.commit()
            session.refresh(career)
            return CareerRead.model_validate(career)

    def unpublish_career(self, career_id: int, session: Session) -> CareerRead:
        """Despublicar una carrera"""
        with session:
            statement = select(Career).where(Career.careerId == career_id)
            career = session.exec(statement).one()
            
            career.published = False
            career.modificationDate = datetime.now().date()
            
            session.commit()
            session.refresh(career)
            return CareerRead.model_validate(career)

    def delete_career(self, career_id: int, session: Session) -> bool:
        """Eliminar una carrera"""
        with session:
            statement = select(Career).where(Career.careerId == career_id)
            career = session.exec(statement).one()
            session.delete(career)
            session.commit()
            return True

    def search_careers_by_name(self, search_term: str, session: Session, offset: int = 0, limit: int = 10) -> List[CareerRead]:
        """Buscar carreras por nombre (búsqueda parcial)"""
        with session:
            statement = select(Career).where(
                Career.name.ilike(f"%{search_term}%")
            ).offset(offset).limit(limit)
            careers = session.exec(statement).all()
            if not careers:
                return []
            return [CareerRead.from_orm(career) for career in careers]

    def get_career_count(self, session: Session) -> int:
        """Obtener el conteo total de carreras"""
        with session:
            statement = select(Career)
            careers = session.exec(statement).all()
            return len(careers)

    def get_published_career_count(self, session: Session) -> int:
        """Obtener el conteo de carreras publicadas"""
        with session:
            statement = select(Career).where(Career.published == True)
            careers = session.exec(statement).all()
            return len(careers)