from sqlmodel import Session, select
from ..models.testimony import Testimony, TestimonyCreate, TestimonyRead, TestimonyUpdate, TestimonyInList, TestimonyPublic
from typing import List, Optional
from sqlalchemy.exc import IntegrityError, NoResultFound
from datetime import datetime

from database.services.filter.filters import BaseServiceWithFilters

class TestimonyService(BaseServiceWithFilters[Testimony]):
    def __init__(self):
        super().__init__(Testimony)

    def create_testimony(self, testimony: TestimonyCreate, session: Session) -> TestimonyRead:
        """Crear un nuevo testimonio"""
        with session:
            new_testimony = Testimony(**testimony.model_dump())
            session.add(new_testimony)
            session.commit()
            session.refresh(new_testimony)
            return TestimonyRead.model_validate(new_testimony)

    def get_testimonies(self, session: Session, offset: int = 0, limit: int = 10) -> List[TestimonyRead]:
        """Obtener lista de testimonios con paginación"""
        with session:
            statement = select(Testimony).offset(offset).limit(limit)
            testimonies = session.exec(statement).all()
            if not testimonies:
                return []
            return [TestimonyRead.model_validate(testimony) for testimony in testimonies]

    def get_testimonies_in_list(self, session: Session, offset: int = 0, limit: int = 10) -> List[TestimonyInList]:
        """Obtener lista simplificada de testimonios para listados"""
        with session:
            statement = select(Testimony).offset(offset).limit(limit)
            testimonies = session.exec(statement).all()
            if not testimonies:
                return []
            return [TestimonyInList.model_validate(testimony) for testimony in testimonies]

    def get_testimonies_public(self, session: Session, offset: int = 0, limit: int = 10) -> List[TestimonyPublic]:
        """Obtener testimonios públicos (sin información sensible)"""
        with session:
            statement = select(Testimony).offset(offset).limit(limit)
            testimonies = session.exec(statement).all()
            if not testimonies:
                return []
            return [TestimonyPublic.model_validate(testimony) for testimony in testimonies]

    def get_testimony_by_id(self, testimony_id: int, session: Session) -> TestimonyRead:
        """Obtener un testimonio por su ID"""
        with session:
            statement = select(Testimony).where(Testimony.testimonyId == testimony_id)
            testimony = session.exec(statement).one()
            if not testimony:
                return None
            return TestimonyRead.model_validate(testimony)

    def get_testimonies_by_career(self, career_id: int, session: Session, offset: int = 0, limit: int = 10) -> List[TestimonyRead]:
        """Obtener testimonios por carrera"""
        with session:
            statement = select(Testimony).where(Testimony.career == career_id).offset(offset).limit(limit)
            testimonies = session.exec(statement).all()
            if not testimonies:
                return []
            return [TestimonyRead.model_validate(testimony) for testimony in testimonies]

    def get_testimonies_by_career_public(self, career_id: int, session: Session, offset: int = 0, limit: int = 10) -> List[TestimonyPublic]:
        """Obtener testimonios públicos por carrera"""
        with session:
            statement = select(Testimony).where(Testimony.career == career_id).offset(offset).limit(limit)
            testimonies = session.exec(statement).all()
            if not testimonies:
                return []
            return [TestimonyPublic.model_validate(testimony) for testimony in testimonies]

    def get_testimonies_by_creator(self, creator_id: int, session: Session, offset: int = 0, limit: int = 10) -> List[TestimonyRead]:
        """Obtener testimonios creados por un usuario específico"""
        with session:
            statement = select(Testimony).where(Testimony.creator == creator_id).offset(offset).limit(limit)
            testimonies = session.exec(statement).all()
            if not testimonies:
                return []
            return [TestimonyRead.model_validate(testimony) for testimony in testimonies]

    def get_testimonies_by_person(self, name: str, lastname: str, session: Session, offset: int = 0, limit: int = 10) -> List[TestimonyRead]:
        """Obtener testimonios por nombre y apellido de la persona"""
        with session:
            statement = select(Testimony).where(
                Testimony.name == name,
                Testimony.lastname == lastname
            ).offset(offset).limit(limit)
            testimonies = session.exec(statement).all()
            if not testimonies:
                return []
            return [TestimonyRead.model_validate(testimony) for testimony in testimonies]

    def search_testimonies_by_text(self, search_term: str, session: Session, offset: int = 0, limit: int = 10) -> List[TestimonyRead]:
        """Buscar testimonios por contenido de texto (búsqueda parcial)"""
        with session:
            statement = select(Testimony).where(
                Testimony.text.ilike(f"%{search_term}%")
            ).offset(offset).limit(limit)
            testimonies = session.exec(statement).all()
            if not testimonies:
                return []
            return [TestimonyRead.model_validate(testimony) for testimony in testimonies]

    def search_testimonies_by_name(self, search_term: str, session: Session, offset: int = 0, limit: int = 10) -> List[TestimonyRead]:
        """Buscar testimonios por nombre o apellido (búsqueda parcial)"""
        with session:
            statement = select(Testimony).where(
                Testimony.name.ilike(f"%{search_term}%") |
                Testimony.lastname.ilike(f"%{search_term}%")
            ).offset(offset).limit(limit)
            testimonies = session.exec(statement).all()
            if not testimonies:
                return []
            return [TestimonyRead.model_validate(testimony) for testimony in testimonies]

    def get_recent_testimonies(self, session: Session, days: int = 30, offset: int = 0, limit: int = 10) -> List[TestimonyRead]:
        """Obtener testimonios recientes (últimos N días)"""
        from datetime import timedelta
        
        with session:
            cutoff_date = datetime.now().date() - timedelta(days=days)
            statement = select(Testimony).where(
                Testimony.creationDate >= cutoff_date
            ).order_by(Testimony.creationDate.desc()).offset(offset).limit(limit)
            testimonies = session.exec(statement).all()
            if not testimonies:
                return []
            return [TestimonyRead.model_validate(testimony) for testimony in testimonies]

    def get_latest_testimonies(self, session: Session, limit: int = 5) -> List[TestimonyPublic]:
        """Obtener los testimonios más recientes (para mostrar en homepage)"""
        with session:
            statement = select(Testimony).order_by(
                Testimony.creationDate.desc()
            ).limit(limit)
            testimonies = session.exec(statement).all()
            if not testimonies:
                return []
            return [TestimonyPublic.model_validate(testimony) for testimony in testimonies]

    def update_testimony(self, testimony_id: int, testimony_update: TestimonyUpdate, session: Session) -> TestimonyRead:
        """Actualizar un testimonio existente"""
        with session:
            statement = select(Testimony).where(Testimony.testimonyId == testimony_id)
            old_testimony = session.exec(statement).one()
            
            update_data = testimony_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(old_testimony, key, value)
            
            # La fecha de modificación se actualiza automáticamente en TestimonyUpdate.__init__
            old_testimony.modificationDate = datetime.now().date()
                
            session.commit()
            session.refresh(old_testimony)
            return TestimonyRead.model_validate(old_testimony)

    def delete_testimony(self, testimony_id: int, session: Session) -> bool:
        """Eliminar un testimonio"""
        with session:
            statement = select(Testimony).where(Testimony.testimonyId == testimony_id)
            testimony = session.exec(statement).one()
            session.delete(testimony)
            session.commit()
            return True

    def get_testimony_count(self, session: Session) -> int:
        """Obtener el conteo total de testimonios"""
        with session:
            statement = select(Testimony)
            testimonies = session.exec(statement).all()
            return len(testimonies)

    def get_testimony_count_by_career(self, career_id: int, session: Session) -> int:
        """Obtener el conteo de testimonios por carrera"""
        with session:
            statement = select(Testimony).where(Testimony.career == career_id)
            testimonies = session.exec(statement).all()
            return len(testimonies)

    def get_testimonies_stats(self, session: Session) -> dict:
        """Obtener estadísticas de testimonios"""
        with session:
            total_count = self.get_testimony_count(session)
            recent_count = len(self.get_recent_testimonies(7, session, limit=1000))  # Últimos 7 días
            
            # Obtener testimonios por carrera
            statement = select(Testimony)
            all_testimonies = session.exec(statement).all()
            
            career_stats = {}
            for testimony in all_testimonies:
                career_id = testimony.career
                if career_id in career_stats:
                    career_stats[career_id] += 1
                else:
                    career_stats[career_id] = 1
            
            return {
                "total_testimonies": total_count,
                "recent_testimonies": recent_count,
                "testimonies_by_career": career_stats
            }

    def bulk_delete_by_career(self, career_id: int, session: Session) -> int:
        """Eliminar todos los testimonios de una carrera específica"""
        with session:
            statement = select(Testimony).where(Testimony.career == career_id)
            testimonies = session.exec(statement).all()
            count = len(testimonies)
            
            for testimony in testimonies:
                session.delete(testimony)
            
            session.commit()
            return count