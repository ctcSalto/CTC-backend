from sqlmodel import Session, select, func, and_, or_
from ..models.career import Career, CareerCreate, CareerRead, CareerSimple, CareerUpdate, CareerInList, CareerReadOptimized, UserSimple, TestimonyForCareer, Area
from typing import List, Optional
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import selectinload
from datetime import datetime
import random

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
            statement = select(Career).where(Career.published == True).offset(offset).limit(limit)
            careers = session.exec(statement).all()
            if not careers:
                return []
            return [CareerInList.model_validate(career) for career in careers]

    def get_careers_in_list_admin(self, session: Session, offset: int = 0, limit: int = 10) -> List[CareerInList]:
        """Obtener lista simplificada de carreras para listados"""
        with session:
            statement = select(Career).offset(offset).limit(limit)
            careers = session.exec(statement).all()
            if not careers:
                return []
            return [CareerInList.model_validate(career) for career in careers]
        
# Versión alternativa más concisa usando model_validate con transformaciones
    def get_careers_optimized(self, session: Session, offset: int = 0, limit: int = 10) -> List[CareerReadOptimized]:
        """Versión alternativa más concisa"""
        with session:
            statement = (
                select(Career)
                .options(
                    selectinload(Career.creator_user),
                    selectinload(Career.modifier_user),
                    selectinload(Career.testimonies)
                )
                .offset(offset)
                .limit(limit)
            )
            
            careers = session.exec(statement).all()
            
            if not careers:
                return []
            
            result = []
            for career in careers:
                # Convertir a dict y transformar las relaciones
                career_dict = career.model_dump()
                
                # Transformar creator_user
                if career.creator_user:
                    career_dict["creator_user"] = {
                        "userId": career.creator_user.userId,
                        "name": career.creator_user.name,
                        "lastname": career.creator_user.lastname
                    }
                
                # Transformar modifier_user
                if career.modifier_user:
                    career_dict["modifier_user"] = {
                        "userId": career.modifier_user.userId,
                        "name": career.modifier_user.name,
                        "lastname": career.modifier_user.lastname
                    }
                
                # Transformar testimonies
                career_dict["testimonies"] = [
                    {
                        "testimonyId": t.testimonyId,
                        "text": t.text,
                        "name": t.name,
                        "lastname": t.lastname,
                        "creationDate": t.creationDate
                    }
                    for t in career.testimonies
                ]
                
                # Crear el objeto usando el dict transformado
                career_optimized = CareerReadOptimized.model_validate(career_dict)
                result.append(career_optimized)
            
            return result

# Si también quieres una función para obtener una sola carrera
    def get_career_optimized_by_id(self, session: Session, career_id: int) -> Optional[CareerReadOptimized]:
        """Obtener una carrera específica con información optimizada"""
        with session:
            statement = (
                select(Career)
                .options(
                    selectinload(Career.creator_user),
                    selectinload(Career.modifier_user),
                    selectinload(Career.testimonies)
                )
                .where(Career.careerId == career_id)
            )
            
            career = session.exec(statement).first()
            
            if not career:
                return None
            
            # Usar la misma lógica de transformación que en get_careers_optimized
            creator_user = None
            if career.creator_user:
                creator_user = UserSimple(
                    userId=career.creator_user.userId,
                    name=career.creator_user.name,
                    lastname=career.creator_user.lastname
                )
            
            modifier_user = None
            if career.modifier_user:
                modifier_user = UserSimple(
                    userId=career.modifier_user.userId,
                    name=career.modifier_user.name,
                    lastname=career.modifier_user.lastname
                )
            
            testimonies = [
                TestimonyForCareer(
                    testimonyId=t.testimonyId,
                    text=t.text,
                    name=t.name,
                    lastname=t.lastname,
                    creationDate=t.creationDate
                )
                for t in career.testimonies
            ]
            
            return CareerReadOptimized(
                careerId=career.careerId,
                careerType=career.careerType,
                area=career.area,
                name=career.name,
                subtitle=career.subtitle,
                aboutCourse1=career.aboutCourse1,
                aboutCourse2=career.aboutCourse2,
                graduateProfile=career.graduateProfile,
                studyPlan=career.studyPlan,
                imageLink=career.imageLink,
                creationDate=career.creationDate,
                modificationDate=career.modificationDate,
                publicationDate=career.publicationDate,
                published=career.published,
                creator=career.creator,
                modifier=career.modifier,
                creator_user=creator_user,
                modifier_user=modifier_user,
                testimonies=testimonies
            )

    def get_published_careers(self, session: Session, offset: int = 0, limit: int = 10) -> List[CareerRead]:
        """Obtener solo las carreras publicadas"""
        with session:
            statement = select(Career).where(Career.published == True).offset(offset).limit(limit)
            careers = session.exec(statement).all()
            if not careers:
                return []
            return [CareerRead.model_validate(career) for career in careers]

    def get_career_by_id_admin(self, career_id: int, session: Session) -> CareerRead:
        """Obtener una carrera por su ID"""
        with session:
            statement = select(Career).where(Career.careerId == career_id)
            career = session.exec(statement).one()
            if not career:
                return None
            return CareerRead.model_validate(career)

    def get_career_by_id(self, career_id: int, session: Session) -> CareerRead:
        """Obtener una carrera por su ID"""
        with session:
            statement = select(Career).where(and_(Career.published == True, Career.careerId == career_id))
            career = session.exec(statement).one()
            if not career:
                return None
            return CareerRead.model_validate(career)
        
    def career_exists(self, career_id: int, session: Session) -> bool:
        with session:
            statement = select(Career).where(Career.careerId == career_id)
            career = session.exec(statement).one_or_none()
            return True if career is not None else False
 
    def get_random_careers_by_area(self, session: Session, count: int = 4) -> List[CareerSimple]:
        """
        Obtener carreras aleatorias asegurando diversidad de áreas
        - Si count <= número de áreas: una carrera por área
        - Si count > número de áreas: repite áreas de forma equitativa
        - NO repite la misma carrera
        - Solo carreras publicadas
        """
        try:
            with session:
                areas = [area.value for area in Area]
                selected_careers = []
                used_career_ids = set()  # Para evitar repeticiones
                
                # Obtener carreras disponibles por área (SOLO PUBLICADAS)
                careers_by_area = {}
                for area in areas:
                    stmt = select(Career).where(and_(
                        Career.area == area, 
                        Career.published == True
                    ))
                    area_careers = session.exec(stmt).all()
                    if area_careers:  # Solo incluir áreas que tienen carreras
                        careers_by_area[area] = area_careers
                
                if not careers_by_area:
                    return []
                
                available_areas = list(careers_by_area.keys())
                
                # Distribuir el count entre las áreas disponibles
                for i in range(count):
                    # Rotar entre las áreas disponibles
                    area = available_areas[i % len(available_areas)]
                    
                    # Filtrar carreras no usadas de esta área
                    available_careers_in_area = [
                        career for career in careers_by_area[area] 
                        if career.careerId not in used_career_ids
                    ]
                    
                    # Si no hay carreras disponibles en esta área, pasar a la siguiente
                    if not available_careers_in_area:
                        continue
                    
                    # Seleccionar una carrera aleatoria de esta área
                    career = random.choice(available_careers_in_area)
                    selected_careers.append(career)
                    used_career_ids.add(career.careerId)
                
                return [CareerSimple.model_validate(career) for career in selected_careers]
                
        except Exception as e:
            print(f"Error en servicio de carreras aleatorias: {e}")
            raise ValueError(f"Error al obtener carreras aleatorias: {str(e)}")

    def get_careers_of_interest(
        self, 
        session: Session, 
        count: int = 4,
        areas: Optional[List[str]] = None,
        include_career_id: Optional[int] = None,
        exclude_career_id: Optional[int] = None
    ) -> List[CareerSimple]:
        """
        Obtener carreras de interés con filtros flexibles
        - Este método único cubre TODOS los casos de uso que mencionaste
        - NO repite carreras
        - Solo carreras publicadas
        """
        try:
            with session:
                selected_careers = []
                used_career_ids = set()
                
                # Paso 1: Incluir carrera específica si se solicita
                if include_career_id:
                    career_stmt = select(Career).where(and_(
                        Career.careerId == include_career_id, 
                        Career.published == True
                    ))
                    specific_career = session.exec(career_stmt).first()
                    
                    if specific_career:
                        selected_careers.append(specific_career)
                        used_career_ids.add(specific_career.careerId)
                    else:
                        raise ValueError(f"No se encontró la carrera con ID {include_career_id} o no está publicada")
                
                # Paso 2: Agregar carrera a excluir al conjunto de usados
                if exclude_career_id:
                    used_career_ids.add(exclude_career_id)
                
                # Paso 3: Construir query para carreras adicionales
                remaining_count = count - len(selected_careers)
                
                if remaining_count > 0:
                    # Construir filtros (SIEMPRE incluir published == True)
                    filters = [Career.published == True]
                    
                    # Filtro por áreas si se especifican
                    if areas:
                        area_filters = [Career.area == area for area in areas]
                        filters.append(or_(*area_filters))
                    
                    # Excluir carreras ya usadas
                    if used_career_ids:
                        filters.append(~Career.careerId.in_(used_career_ids))
                    
                    # Construir statement
                    stmt = select(Career).where(and_(*filters)).order_by(func.random())
                    
                    # Obtener carreras disponibles
                    available_careers = session.exec(stmt).all()
                    
                    # Seleccionar las que necesitamos (sin repetir)
                    if available_careers:
                        careers_to_add = min(len(available_careers), remaining_count)
                        random_careers = random.sample(list(available_careers), careers_to_add)
                        selected_careers.extend(random_careers)
                
                return [CareerSimple.model_validate(career) for career in selected_careers]
                
        except Exception as e:
            print(f"Error en servicio de carreras de interés: {e}")
            raise ValueError(f"Error al obtener carreras de interés: {str(e)}")

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
            old_career = session.exec(statement).first()  # Usar first() en lugar de one()
            
            if not old_career:
                return None
            
            # Obtener solo los campos que no son None
            update_data = career_update.model_dump(exclude_unset=True, exclude_none=True)
            
            # Actualizar los campos
            for key, value in update_data.items():
                setattr(old_career, key, value)
            
            # Actualizar fecha de modificación automáticamente
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
            career = session.exec(statement).first()
            for testimony in career.testimonies:
                session.delete(testimony)
            session.delete(career)
            session.commit()
            return True

    def search_careers_by_name(self, search_term: str, session: Session, offset: int = 0, limit: int = 10) -> List[CareerRead]:
        """Buscar carreras por nombre (búsqueda parcial)"""
        with session:
            statement = select(Career).where(
                and_(
                Career.published == True,
                Career.name.ilike(f"%{search_term}%")
                )
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