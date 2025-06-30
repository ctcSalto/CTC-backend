from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, TypeVar, Generic, Union
from sqlmodel import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import and_, or_, desc, asc
from sqlalchemy.inspection import inspect
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class LogicalOperator(str, Enum):
    AND = "and"
    OR = "or"

class Condition(BaseModel):
    attribute: str = Field(..., description="Atributo a filtrar (ej: 'name', 'user.email')")
    operator: str = Field(..., description="Operador de comparación")
    value: Any = Field(..., description="Valor a comparar")
    
    @validator('operator')
    def validate_operator(cls, v):
        allowed_operators = {
            'eq', 'ne', 'gt', 'gte', 'lt', 'lte', 
            'contains', 'icontains', 'startswith', 'endswith',
            'in', 'not_in', 'is_null', 'is_not_null'
        }
        if v not in allowed_operators:
            raise ValueError(f"Operador '{v}' no soportado. Operadores válidos: {allowed_operators}")
        return v

class ConditionGroup(BaseModel):
    """Grupo de condiciones con operador lógico"""
    conditions: List[Union[Condition, "ConditionGroup"]] = []
    logical_operator: LogicalOperator = LogicalOperator.AND

class RelationConfig(BaseModel):
    """Configuración para cargar relaciones"""
    relation_name: str
    load_strategy: str = Field(default="select", pattern="^(select|joined|subquery)$")
    nested_relations: Optional[List["RelationConfig"]] = None
    
    class Config:
        use_enum_values = True

class Filter(BaseModel):
    conditions: Optional[List[Union[Condition, ConditionGroup]]] = None
    logical_operator: LogicalOperator = LogicalOperator.AND
    relations: Optional[List[RelationConfig]] = None
    limit: Optional[int] = Field(default=10, ge=1, le=1000)
    offset: Optional[int] = Field(default=0, ge=0)
    order_by: Optional[str] = None
    order_direction: Optional[str] = Field(default="asc", pattern="^(asc|desc)$")
    
    class Config:
        use_enum_values = True

# Fix forward references
ConditionGroup.model_rebuild()
Filter.model_rebuild()

class QueryBuilderError(Exception):
    """Excepción personalizada para errores del QueryBuilder"""
    pass

class QueryBuilder:
    def __init__(self, model_class):
        self.model_class = model_class
        self.query = select(model_class)
        self.joins_applied = set()
        self._model_registry = {}  # Cache para modelos relacionados
    
    def apply_conditions(self, conditions: List[Union[Condition, ConditionGroup]], 
                        logical_operator: LogicalOperator = LogicalOperator.AND):
        """Aplica condiciones de filtrado con soporte para grupos lógicos"""
        if not conditions:
            return self
            
        filter_clauses = []
        
        for condition in conditions:
            if isinstance(condition, Condition):
                clause = self._apply_single_condition(condition)
                if clause is not None:
                    filter_clauses.append(clause)
            elif isinstance(condition, ConditionGroup):
                group_clause = self._apply_condition_group(condition)
                if group_clause is not None:
                    filter_clauses.append(group_clause)
        
        if filter_clauses:
            if logical_operator == LogicalOperator.OR:
                combined_clause = or_(*filter_clauses)
            else:
                combined_clause = and_(*filter_clauses)
            
            self.query = self.query.where(combined_clause)
        
        return self
    
    def _apply_condition_group(self, condition_group: ConditionGroup):
        """Aplica un grupo de condiciones"""
        if not condition_group.conditions:
            return None
            
        clauses = []
        for condition in condition_group.conditions:
            if isinstance(condition, Condition):
                clause = self._apply_single_condition(condition)
                if clause is not None:
                    clauses.append(clause)
            elif isinstance(condition, ConditionGroup):
                nested_clause = self._apply_condition_group(condition)
                if nested_clause is not None:
                    clauses.append(nested_clause)
        
        if not clauses:
            return None
            
        if condition_group.logical_operator == LogicalOperator.OR:
            return or_(*clauses)
        else:
            return and_(*clauses)
    
    def _apply_single_condition(self, condition: Condition):
        """Aplica una condición individual"""
        try:
            attribute_path = condition.attribute.split('.')
            
            if len(attribute_path) == 1:
                # Atributo directo del modelo principal
                if not hasattr(self.model_class, attribute_path[0]):
                    logger.warning(f"Atributo '{attribute_path[0]}' no encontrado en {self.model_class.__name__}")
                    return None
                    
                column = getattr(self.model_class, attribute_path[0])
                return self._build_filter_clause(column, condition.operator, condition.value)
            else:
                # Atributo en relación
                return self._apply_relation_condition(attribute_path, condition)
                
        except Exception as e:
            logger.error(f"Error aplicando condición {condition.attribute}: {str(e)}")
            raise QueryBuilderError(f"Error en condición '{condition.attribute}': {str(e)}")
    
    def _apply_relation_condition(self, attribute_path: List[str], condition: Condition):
        """Aplica condición en relación con mejor manejo de errores"""
        current_model = self.model_class
        
        try:
            # Navegar por las relaciones
            for i, relation_name in enumerate(attribute_path[:-1]):
                if not hasattr(current_model, relation_name):
                    logger.warning(f"Relación '{relation_name}' no encontrada en {current_model.__name__}")
                    return None
                
                related_model = self._get_related_model(current_model, relation_name)
                if related_model is None:
                    logger.warning(f"No se pudo determinar el modelo para la relación '{relation_name}'")
                    return None
                
                # Aplicar JOIN si no se ha aplicado ya
                join_key = f"{current_model.__name__}.{relation_name}"
                if join_key not in self.joins_applied:
                    relation_attr = getattr(current_model, relation_name)
                    self.query = self.query.join(relation_attr)
                    self.joins_applied.add(join_key)
                
                current_model = related_model
            
            # Aplicar filtro en el último atributo
            final_attribute = attribute_path[-1]
            if not hasattr(current_model, final_attribute):
                logger.warning(f"Atributo '{final_attribute}' no encontrado en {current_model.__name__}")
                return None
                
            column = getattr(current_model, final_attribute)
            return self._build_filter_clause(column, condition.operator, condition.value)
            
        except Exception as e:
            logger.error(f"Error en relación {'.'.join(attribute_path)}: {str(e)}")
            return None
    
    def _get_related_model(self, model, relation_name):
        """Obtiene el modelo relacionado con cache"""
        cache_key = f"{model.__name__}.{relation_name}"
        
        if cache_key in self._model_registry:
            return self._model_registry[cache_key]
        
        try:
            relation_attr = getattr(model, relation_name)
            
            # Intentar obtener el modelo de diferentes formas
            related_model = None
            
            if hasattr(relation_attr.property, 'mapper'):
                related_model = relation_attr.property.mapper.class_
            elif hasattr(relation_attr.property, 'entity'):
                related_model = relation_attr.property.entity.class_
            elif hasattr(relation_attr, 'type_'):
                related_model = relation_attr.type_
            
            # Guardar en cache
            if related_model:
                self._model_registry[cache_key] = related_model
            
            return related_model
            
        except Exception as e:
            logger.error(f"Error obteniendo modelo relacionado para {cache_key}: {str(e)}")
            return None
    
    def _build_filter_clause(self, column, operator: str, value: Any):
        """Construye la cláusula de filtro según el operador"""
        try:
            operators = {
                'eq': lambda col, val: col == val,
                'ne': lambda col, val: col != val,
                'gt': lambda col, val: col > val,
                'gte': lambda col, val: col >= val,
                'lt': lambda col, val: col < val,
                'lte': lambda col, val: col <= val,
                'contains': lambda col, val: col.contains(str(val)),
                'icontains': lambda col, val: col.ilike(f'%{val}%'),
                'startswith': lambda col, val: col.startswith(str(val)),
                'endswith': lambda col, val: col.endswith(str(val)),
                'in': lambda col, val: col.in_(val if isinstance(val, list) else [val]),
                'not_in': lambda col, val: ~col.in_(val if isinstance(val, list) else [val]),
                'is_null': lambda col, val: col.is_(None),
                'is_not_null': lambda col, val: col.is_not(None),
            }
            
            if operator not in operators:
                raise ValueError(f"Operador '{operator}' no soportado")
            
            return operators[operator](column, value)
            
        except Exception as e:
            logger.error(f"Error construyendo cláusula para operador '{operator}': {str(e)}")
            raise QueryBuilderError(f"Error en operador '{operator}': {str(e)}")
    
    def apply_relations(self, relations: List[RelationConfig]):
        """Aplica carga de relaciones con mejor manejo de errores"""
        for relation_config in relations:
            try:
                self._apply_relation_loading(relation_config)
            except Exception as e:
                logger.error(f"Error cargando relación '{relation_config.relation_name}': {str(e)}")
                # Continuar con otras relaciones en lugar de fallar completamente
                continue
        return self
    
    def _apply_relation_loading(self, relation_config: RelationConfig):
        """Aplica carga de una relación específica"""
        if not hasattr(self.model_class, relation_config.relation_name):
            logger.warning(f"Relación '{relation_config.relation_name}' no encontrada en {self.model_class.__name__}")
            return
            
        relation_attr = getattr(self.model_class, relation_config.relation_name)
        
        # Configurar estrategia de carga
        if relation_config.load_strategy == "joined":
            loader = joinedload(relation_attr)
        elif relation_config.load_strategy == "subquery":
            from sqlalchemy.orm import subqueryload
            loader = subqueryload(relation_attr)
        else:  # select (default)
            loader = selectinload(relation_attr)
        
        # Aplicar relaciones anidadas
        if relation_config.nested_relations:
            for nested_relation in relation_config.nested_relations:
                try:
                    related_model = self._get_related_model(self.model_class, relation_config.relation_name)
                    if related_model and hasattr(related_model, nested_relation.relation_name):
                        nested_attr = getattr(related_model, nested_relation.relation_name)
                        
                        if nested_relation.load_strategy == "joined":
                            loader = loader.joinedload(nested_attr)
                        elif nested_relation.load_strategy == "subquery":
                            loader = loader.subqueryload(nested_attr)
                        else:
                            loader = loader.selectinload(nested_attr)
                except Exception as e:
                    logger.error(f"Error en relación anidada '{nested_relation.relation_name}': {str(e)}")
                    continue
        
        self.query = self.query.options(loader)
    
    def apply_pagination(self, limit: Optional[int], offset: Optional[int]):
        """Aplica paginación"""
        if limit is not None:
            self.query = self.query.limit(limit)
        if offset is not None:
            self.query = self.query.offset(offset)
        return self
    
    def apply_ordering(self, order_by: Optional[str], direction: str = "asc"):
        """Aplica ordenamiento con mejor manejo de relaciones"""
        if not order_by:
            return self
            
        try:
            attribute_path = order_by.split('.')
            
            if len(attribute_path) == 1:
                if not hasattr(self.model_class, attribute_path[0]):
                    logger.warning(f"Atributo de ordenamiento '{attribute_path[0]}' no encontrado")
                    return self
                column = getattr(self.model_class, attribute_path[0])
            else:
                # Manejar ordenamiento por relaciones
                current_model = self.model_class
                for relation_name in attribute_path[:-1]:
                    if not hasattr(current_model, relation_name):
                        logger.warning(f"Relación de ordenamiento '{relation_name}' no encontrada")
                        return self
                        
                    related_model = self._get_related_model(current_model, relation_name)
                    if related_model is None:
                        logger.warning(f"No se pudo determinar modelo para ordenamiento en '{relation_name}'")
                        return self
                        
                    join_key = f"{current_model.__name__}.{relation_name}"
                    if join_key not in self.joins_applied:
                        relation_attr = getattr(current_model, relation_name)
                        self.query = self.query.join(relation_attr)
                        self.joins_applied.add(join_key)
                    current_model = related_model
                
                final_attribute = attribute_path[-1]
                if not hasattr(current_model, final_attribute):
                    logger.warning(f"Atributo de ordenamiento '{final_attribute}' no encontrado")
                    return self
                column = getattr(current_model, final_attribute)
            
            if direction.lower() == "desc":
                self.query = self.query.order_by(desc(column))
            else:
                self.query = self.query.order_by(asc(column))
                
        except Exception as e:
            logger.error(f"Error aplicando ordenamiento: {str(e)}")
            # No fallar por errores de ordenamiento
            
        return self
    
    def build(self):
        """Retorna la query construida"""
        return self.query

T = TypeVar('T')

class BaseServiceWithFilters(Generic[T]):
    def __init__(self, model_class: T):
        self.model_class = model_class
    
    def get_with_filters(self, session, filters: Filter):
        """Obtiene registros aplicando filtros con manejo robusto de errores"""
        try:
            builder = QueryBuilder(self.model_class)
            
            if filters.conditions:
                builder.apply_conditions(filters.conditions, filters.logical_operator)
            if filters.relations:
                builder.apply_relations(filters.relations)
            if filters.order_by:
                builder.apply_ordering(filters.order_by, filters.order_direction)
            
            builder.apply_pagination(filters.limit, filters.offset)
            
            query = builder.build()
            return session.exec(query).all()
            
        except QueryBuilderError:
            # Re-raise QueryBuilder errors
            raise
        except Exception as e:
            logger.error(f"Error ejecutando query con filtros: {str(e)}")
            raise QueryBuilderError(f"Error ejecutando consulta: {str(e)}")
    
    def count_with_filters(self, session, filters: Filter) -> int:
        """Cuenta registros que coinciden con los filtros"""
        try:
            builder = QueryBuilder(self.model_class)
            
            if filters.conditions:
                builder.apply_conditions(filters.conditions, filters.logical_operator)
            
            # Para contar, no necesitamos relaciones, paginación ni ordenamiento
            query = builder.build()
            count_query = select([func.count()]).select_from(query.subquery())
            
            return session.exec(count_query).scalar()
            
        except Exception as e:
            logger.error(f"Error contando registros: {str(e)}")
            return 0