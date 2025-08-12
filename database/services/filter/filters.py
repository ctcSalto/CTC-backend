from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, TypeVar, Generic, Union
from sqlmodel import select, SQLModel
from sqlalchemy.orm import selectinload, joinedload, load_only
from sqlalchemy import and_, or_, desc, asc, func
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
    """Configuración para cargar relaciones con selección de campos"""
    relation_name: str
    load_strategy: str = Field(default="select", pattern="^(select|joined|subquery)$")
    nested_relations: Optional[List["RelationConfig"]] = None
    fields: Optional[List[str]] = Field(
        default=None, 
        description="Campos específicos a cargar de esta relación. Si es None, carga todos los campos."
    )
    
    class Config:
        use_enum_values = True

class FieldFilter:
    """
    Clase para filtrar campos de respuestas basándose en los campos solicitados
    Con soporte recursivo para relaciones anidadas de múltiples niveles
    """
    
    @staticmethod
    def filter_response_fields(
        data: Union[List[Dict[str, Any]], Dict[str, Any]], 
        requested_fields: Optional[List[str]] = None,
        requested_relations: Optional[List[Dict[str, Any]]] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Filtra los campos de la respuesta basándose en los campos solicitados
        """
        if not data:
            return data
            
        # Si no se especifican campos, retornar todo
        if not requested_fields and not requested_relations:
            return data
            
        # Procesar lista de objetos
        if isinstance(data, list):
            return [
                FieldFilter._filter_single_object(item, requested_fields, requested_relations)
                for item in data
            ]
        
        # Procesar objeto único
        return FieldFilter._filter_single_object(data, requested_fields, requested_relations)
    
    @staticmethod
    def _filter_single_object(
        obj: Dict[str, Any], 
        requested_fields: Optional[List[str]] = None,
        requested_relations: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Filtra un objeto único de forma recursiva"""
        if not isinstance(obj, dict):
            return obj
            
        filtered_obj = {}
        
        # Obtener nombres de relaciones para excluirlos de campos principales
        relation_names = set()
        if requested_relations:
            relation_names = {rel.get('relation_name', '') for rel in requested_relations}
        
        # Filtrar campos principales (no relacionales)
        if requested_fields:
            for field in requested_fields:
                if field in obj and field not in relation_names:
                    filtered_obj[field] = obj[field]
        else:
            # Si no se especifican campos principales, incluir todos excepto relaciones
            for key, value in obj.items():
                if key not in relation_names:
                    filtered_obj[key] = value
        
        # Procesar relaciones de forma recursiva
        if requested_relations:
            for relation in requested_relations:
                relation_name = relation.get('relation_name')
                relation_fields = relation.get('fields', [])
                nested_relations = relation.get('relations', [])
                
                if relation_name and relation_name in obj:
                    relation_data = obj[relation_name]
                    
                    if relation_data is not None:
                        # DEBUG: Información de la relación antes del filtrado
                        logger.info(f"DEBUG - Filtrando relación '{relation_name}'")
                        logger.info(f"DEBUG - Tipo de datos: {type(relation_data)}")
                        logger.info(f"DEBUG - Campos solicitados para '{relation_name}': {relation_fields}")
                        
                        # IMPORTANTE: No convertir objetos únicos en listas vacías
                        if isinstance(relation_data, list) and len(relation_data) == 0:
                            logger.info(f"DEBUG - Relación '{relation_name}' es lista vacía, manteniéndola como lista vacía")
                            filtered_obj[relation_name] = []
                        else:
                            filtered_relation = FieldFilter._filter_relation_recursive(
                                relation_data, 
                                relation_fields, 
                                nested_relations
                            )
                            filtered_obj[relation_name] = filtered_relation
                            logger.info(f"DEBUG - Relación '{relation_name}' filtrada exitosamente")
                            logger.info(f"DEBUG - Resultado filtrado: {filtered_relation}")
                    else:
                        logger.info(f"DEBUG - Relación '{relation_name}' es None")
                        filtered_obj[relation_name] = None
        
        return filtered_obj
    
    @staticmethod
    def _filter_relation_recursive(
        relation_data: Union[List[Dict[str, Any]], Dict[str, Any]], 
        requested_fields: List[str],
        nested_relations: Optional[List[Dict[str, Any]]] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Filtra los campos de una relación de forma recursiva"""
        if not relation_data:
            return relation_data
        
        logger.info(f"DEBUG - _filter_relation_recursive llamado con tipo: {type(relation_data)}")
        logger.info(f"DEBUG - requested_fields: {requested_fields}")
        
        # Procesar lista de objetos relacionados
        if isinstance(relation_data, list):
            logger.info(f"DEBUG - Procesando lista con {len(relation_data)} elementos")
            filtered_list = []
            for item in relation_data:
                filtered_item = FieldFilter._filter_single_relation_object(item, requested_fields, nested_relations)
                filtered_list.append(filtered_item)
                logger.info(f"DEBUG - Item filtrado: {filtered_item}")
            return filtered_list
        
        # Procesar objeto relacionado único
        elif isinstance(relation_data, dict):
            logger.info(f"DEBUG - Procesando objeto único con claves: {list(relation_data.keys())}")
            filtered_obj = FieldFilter._filter_single_relation_object(relation_data, requested_fields, nested_relations)
            logger.info(f"DEBUG - Objeto filtrado: {filtered_obj}")
            return filtered_obj
        
        # Si no es ni lista ni diccionario, devolver tal como está
        else:
            logger.info(f"DEBUG - Datos de tipo no procesable: {type(relation_data)}, devolviendo tal como está")
            return relation_data
    
    @staticmethod
    def _filter_single_relation_object(
        obj: Dict[str, Any],
        requested_fields: List[str],
        nested_relations: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Filtra un objeto de relación individual con soporte para relaciones anidadas"""
        if not isinstance(obj, dict):
            return obj
        
        filtered_obj = {}
        
        # Obtener nombres de relaciones anidadas
        nested_relation_names = set()
        if nested_relations:
            nested_relation_names = {rel.get('relation_name', '') for rel in nested_relations}
        
        # CORREGIDO: Filtrar campos solicitados (excluyendo relaciones anidadas)
        if requested_fields:
            for field in requested_fields:
                if field in obj and field not in nested_relation_names:
                    filtered_obj[field] = obj[field]
        else:
            # Si no se especifican campos, incluir todos excepto relaciones anidadas
            for key, value in obj.items():
                if key not in nested_relation_names:
                    filtered_obj[key] = value
        
        # Procesar relaciones anidadas recursivamente
        if nested_relations:
            for nested_relation in nested_relations:
                nested_relation_name = nested_relation.get('relation_name')
                nested_fields = nested_relation.get('fields', [])
                deeper_relations = nested_relation.get('relations', [])
                
                if nested_relation_name and nested_relation_name in obj:
                    nested_data = obj[nested_relation_name]
                    
                    if nested_data is not None:
                        filtered_nested = FieldFilter._filter_relation_recursive(
                            nested_data,
                            nested_fields,
                            deeper_relations
                        )
                        filtered_obj[nested_relation_name] = filtered_nested
        
        return filtered_obj

class EnhancedFieldFilter(FieldFilter):
    """Versión mejorada que maneja modelos SQLModel/Pydantic y objetos personalizados"""
    
    @staticmethod
    def filter_model_response(
        data: Union[List[SQLModel], SQLModel, List[Dict], Dict],
        requested_fields: Optional[List[str]] = None,
        requested_relations: Optional[List[Dict[str, Any]]] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Filtra respuestas que pueden ser modelos SQLModel, objetos personalizados o diccionarios"""
        # Convertir modelos a diccionarios si es necesario
        if isinstance(data, list):
            dict_data = []
            for item in data:
                converted_item = EnhancedFieldFilter._convert_to_dict_with_relations(item)
                dict_data.append(converted_item)
        else:
            dict_data = EnhancedFieldFilter._convert_to_dict_with_relations(data)
        
        return FieldFilter.filter_response_fields(dict_data, requested_fields, requested_relations)
    
    @staticmethod
    def _convert_to_dict_with_relations(item):
        """
        Convierte un objeto a diccionario, FORZANDO la inclusión de relaciones SQLAlchemy
        MEJORADO para debugging y manejo de relaciones únicas
        """
        # Caso 1: Ya es un diccionario
        if isinstance(item, dict):
            return item
        
        # Caso 2: Modelo SQLModel/Pydantic
        if hasattr(item, 'model_dump') or hasattr(item, 'dict'):
            # Obtener el diccionario base
            if hasattr(item, 'model_dump'):
                base_dict = item.model_dump()
            else:
                base_dict = item.dict()
            
            logger.info(f"DEBUG - Objeto {type(item).__name__}: model_dump/dict keys: {list(base_dict.keys())}")
            
            # CRÍTICO: Forzar la inclusión de relaciones SQLAlchemy que están cargadas
            # pero no aparecen en model_dump por defecto
            if hasattr(item, '__dict__'):
                sqlalchemy_dict = item.__dict__.copy()
                logger.info(f"DEBUG - __dict__ keys: {list(sqlalchemy_dict.keys())}")
                
                # Agregar relaciones que estén cargadas pero no en el model_dump
                for key, value in sqlalchemy_dict.items():
                    if not key.startswith('_'):  # Ignorar atributos privados
                        # Si la relación está cargada y no está en base_dict
                        if key not in base_dict and value is not None:
                            logger.info(f"DEBUG - Procesando relación '{key}' con valor: {type(value)}")
                            
                            # CRÍTICO: Verificar primero si es un objeto SQLModel/Pydantic antes que iterable
                            if hasattr(value, 'model_dump') or hasattr(value, 'dict') or (hasattr(value, '__dict__') and not isinstance(value, (str, bytes, int, float, bool, type(None)))):
                                # Es un objeto relacionado único (SQLModel, Pydantic, etc.)
                                try:
                                    converted_related = EnhancedFieldFilter._convert_to_dict_with_relations(value)
                                    base_dict[key] = converted_related
                                    logger.info(f"DEBUG - Relación objeto '{key}' agregada: {type(value).__name__}")
                                    logger.info(f"DEBUG - Contenido de relación '{key}': {converted_related}")
                                except Exception as e:
                                    logger.warning(f"Error procesando relación objeto '{key}': {e}")
                            
                            elif hasattr(value, '__iter__') and not isinstance(value, (str, bytes, dict)):
                                # Es una lista de objetos relacionados (verificar después de objeto único)
                                try:
                                    # Verificar si realmente es una lista de objetos relacionados
                                    if isinstance(value, (list, tuple)):
                                        converted_list = []
                                        for related_item in value:
                                            converted_related = EnhancedFieldFilter._convert_to_dict_with_relations(related_item)
                                            converted_list.append(converted_related)
                                        base_dict[key] = converted_list
                                        logger.info(f"DEBUG - Relación lista '{key}' agregada con {len(converted_list)} elementos")
                                    else:
                                        # Es iterable pero no es una lista típica, tratar como objeto único
                                        logger.warning(f"DEBUG - '{key}' es iterable ({type(value)}) pero no lista, tratando como objeto único")
                                        converted_related = EnhancedFieldFilter._convert_to_dict_with_relations(value)
                                        base_dict[key] = converted_related
                                except Exception as e:
                                    logger.warning(f"Error procesando relación iterable '{key}': {e}")
                                    base_dict[key] = []
                            
                            else:
                                # Valor primitivo que no estaba en model_dump
                                base_dict[key] = value
                                logger.info(f"DEBUG - Valor primitivo '{key}' agregado: {value}")            
            logger.info(f"DEBUG - Diccionario final con claves: {list(base_dict.keys())}")
            return base_dict
        
        # Caso 3: Objeto con __dict__
        if hasattr(item, '__dict__'):
            dict_result = EnhancedFieldFilter._extract_from_object_dict(item)
            logger.info(f"DEBUG - __dict__ extracción: {list(dict_result.keys())}")
            return dict_result
        
        return item
    
    @staticmethod
    def _extract_from_object_dict(obj):
        """Extrae datos de un objeto usando __dict__ con manejo mejorado de relaciones"""
        result = {}
        for key, value in obj.__dict__.items():
            if not key.startswith('_'):  # Ignorar atributos privados
                if isinstance(value, list):
                    result[key] = [EnhancedFieldFilter._convert_to_dict_with_relations(v) for v in value]
                elif hasattr(value, '__dict__') and not isinstance(value, (str, int, float, bool, type(None))):
                    result[key] = EnhancedFieldFilter._convert_to_dict_with_relations(value)
                else:
                    result[key] = value
        return result

class Filter(BaseModel):
    conditions: Optional[List[Union[Condition, ConditionGroup]]] = None
    logical_operator: LogicalOperator = LogicalOperator.AND
    relations: Optional[List[RelationConfig]] = None
    fields: Optional[List[str]] = Field(
        default=None,
        description="Campos específicos de la entidad principal. Si es None, carga todos los campos."
    )
    limit: Optional[int] = Field(default=10, ge=1, le=1000)
    offset: Optional[int] = Field(default=0, ge=0)
    order_by: Optional[str] = None
    order_direction: Optional[str] = Field(default="asc", pattern="^(asc|desc)$")
    
    class Config:
        use_enum_values = True

# Fix forward references
ConditionGroup.model_rebuild()
Filter.model_rebuild()

def extract_filter_fields(filters: Filter) -> tuple[Optional[List[str]], Optional[List[Dict[str, Any]]]]:
    """Extrae los campos solicitados del objeto Filter"""
    requested_fields = getattr(filters, 'fields', None)
    relations_raw = getattr(filters, 'relations', None)
    
    # Convertir RelationConfig a diccionarios si es necesario
    requested_relations = None
    if relations_raw:
        requested_relations = []
        for relation in relations_raw:
            if hasattr(relation, 'relation_name'):  # Es un objeto RelationConfig
                relation_dict = {
                    'relation_name': getattr(relation, 'relation_name', None),
                    'fields': getattr(relation, 'fields', []),
                    'relations': getattr(relation, 'nested_relations', []) or getattr(relation, 'relations', [])
                }
                requested_relations.append(relation_dict)
            elif isinstance(relation, dict):  # Ya es un diccionario
                requested_relations.append(relation)
    
    return requested_fields, requested_relations

def filter_response(data: Union[List[Dict[str, Any]], Dict[str, Any]], filters: Filter) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Función genérica para filtrar cualquier tipo de respuesta basándose en un objeto Filter"""
    requested_fields, requested_relations = extract_filter_fields(filters)
    return FieldFilter.filter_response_fields(data, requested_fields, requested_relations)

def filter_model_response(data: Union[List, Dict], filters: Filter) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Función genérica para filtrar respuestas que pueden ser modelos SQLModel/Pydantic"""
    requested_fields, requested_relations = extract_filter_fields(filters)
    return EnhancedFieldFilter.filter_model_response(data, requested_fields, requested_relations)

class QueryBuilder:
    """QueryBuilder simplificado y corregido"""
    
    def __init__(self, model_class):
        self.model_class = model_class
        self.query = select(model_class)
        self.joins_applied = set()
        self._model_registry = {}

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
            return None
    
    def _apply_relation_condition(self, attribute_path: List[str], condition: Condition):
        """Aplica condición en relación"""
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
                    logger.info(f"JOIN aplicado: {join_key}")
                
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
            raise
    
    def apply_relations(self, relations: List[RelationConfig]):
        """Aplica carga de relaciones - FORZANDO LA CARGA EAGER"""
        for relation_config in relations:
            try:
                self._apply_relation_loading(relation_config)
            except Exception as e:
                logger.error(f"Error cargando relación '{relation_config.relation_name}': {str(e)}")
                continue
        return self
    
    def _apply_relation_loading(self, relation_config: RelationConfig):
        """Aplica carga de una relación específica - FORZANDO EAGER LOADING"""
        if not hasattr(self.model_class, relation_config.relation_name):
            logger.warning(f"Relación '{relation_config.relation_name}' no encontrada en {self.model_class.__name__}")
            return
            
        relation_attr = getattr(self.model_class, relation_config.relation_name)
        logger.info(f"DEBUG - Aplicando relación: {relation_config.relation_name}")
        
        # CRÍTICO: FORZAR la carga eager de la relación
        if relation_config.load_strategy == "joined":
            loader = joinedload(relation_attr)
            logger.info(f"DEBUG - Usando joinedload para {relation_config.relation_name}")
        elif relation_config.load_strategy == "subquery":
            from sqlalchemy.orm import subqueryload
            loader = subqueryload(relation_attr)
            logger.info(f"DEBUG - Usando subqueryload para {relation_config.relation_name}")
        else:  # select (default)
            loader = selectinload(relation_attr)
            logger.info(f"DEBUG - Usando selectinload para {relation_config.relation_name}")
        
        # Aplicar relaciones anidadas de forma recursiva
        if relation_config.nested_relations:
            logger.info(f"DEBUG - Relaciones anidadas encontradas: {[nr.relation_name for nr in relation_config.nested_relations]}")
            for nested_relation in relation_config.nested_relations:
                try:
                    related_model = self._get_related_model(self.model_class, relation_config.relation_name)
                    if related_model and hasattr(related_model, nested_relation.relation_name):
                        nested_attr = getattr(related_model, nested_relation.relation_name)
                        
                        # Configurar loader anidado
                        if nested_relation.load_strategy == "joined":
                            nested_loader = loader.joinedload(nested_attr)
                        elif nested_relation.load_strategy == "subquery":
                            nested_loader = loader.subqueryload(nested_attr)
                        else:
                            nested_loader = loader.selectinload(nested_attr)
                        
                        loader = nested_loader
                        logger.info(f"DEBUG - Loader anidado aplicado para {nested_relation.relation_name}")
                        
                except Exception as e:
                    logger.error(f"Error en relación anidada '{nested_relation.relation_name}': {str(e)}")
                    continue
        
        # APLICAR EL LOADER A LA QUERY
        self.query = self.query.options(loader)
        logger.info(f"DEBUG - Loader aplicado exitosamente para {relation_config.relation_name}")
    
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
            
        return self
    
    def build(self):
        """Retorna la query construida"""
        return self.query

T = TypeVar('T')

class BaseServiceWithFilters(Generic[T]):
    def __init__(self, model_class: T):
        self.model_class = model_class
    
    def get_with_filters(self, session, filters: Filter):
        """
        Obtiene registros aplicando filtros - VERSIÓN CORREGIDA PARA RELACIONES
        """
        try:
            builder = QueryBuilder(self.model_class)
            
            # Aplicar condiciones (pueden requerir JOINs)
            if filters.conditions:
                builder.apply_conditions(filters.conditions, filters.logical_operator)
            
            # CRÍTICO: Aplicar relaciones ANTES de ejecutar la query
            if filters.relations:
                logger.info(f"DEBUG - Aplicando {len(filters.relations)} relaciones")
                builder.apply_relations(filters.relations)
                
            # Aplicar ordenamiento
            if filters.order_by:
                builder.apply_ordering(filters.order_by, filters.order_direction)
            
            # Aplicar paginación
            builder.apply_pagination(filters.limit, filters.offset)
            
            query = builder.build()
            
            # DEBUG: Imprimir la query generada
            logger.info(f"DEBUG - Query SQL generada: {query}")
            
            results = session.exec(query).all()
            
            logger.info(f"Query ejecutada exitosamente. Registros obtenidos: {len(results)}")
            
            # DEBUG: Verificar si las relaciones están cargadas
            if results and filters.relations:
                first_result = results[0]
                for relation_config in filters.relations:
                    relation_name = relation_config.relation_name
                    if hasattr(first_result, relation_name):
                        relation_value = getattr(first_result, relation_name)
                        logger.info(f"DEBUG - Relación '{relation_name}' cargada: {relation_value is not None}")
                        if relation_value:
                            logger.info(f"DEBUG - Tipo de relación: {type(relation_value)}")
                            if hasattr(relation_value, '__len__'):
                                logger.info(f"DEBUG - Cantidad de elementos: {len(relation_value)}")
                    else:
                        logger.warning(f"DEBUG - Relación '{relation_name}' NO encontrada en el resultado")
            
            return results
            
        except Exception as e:
            logger.error(f"Error ejecutando query con filtros: {str(e)}")
            raise Exception(f"Error ejecutando consulta: {str(e)}")
        
    def get_with_filters_clean(self, session, filters: Filter):
        """
        Obtiene registros con filtros y aplica filtrado de campos en el post-procesamiento
        VERSIÓN CORREGIDA PARA ASEGURAR CARGA DE RELACIONES
        """
        try:
            # Obtener resultados completos con relaciones cargadas
            raw_results = self.get_with_filters(session, filters)
            
            if not raw_results:
                return []
            
            # DEBUG: Inspeccionar primer resultado MÁS DETALLADAMENTE
            if raw_results:
                first_result = raw_results[0]
                logger.info(f"DEBUG - Tipo del primer resultado: {type(first_result)}")
                
                # Verificar todas las relaciones solicitadas
                if filters.relations:
                    for relation_config in filters.relations:
                        relation_name = relation_config.relation_name
                        logger.info(f"DEBUG - Verificando relación: {relation_name}")
                        
                        # Verificar usando hasattr
                        if hasattr(first_result, relation_name):
                            relation_value = getattr(first_result, relation_name)
                            logger.info(f"DEBUG - Relación '{relation_name}' encontrada con hasattr")
                            logger.info(f"DEBUG - Valor: {relation_value}")
                            logger.info(f"DEBUG - Tipo: {type(relation_value)}")
                            
                            # Si es una lista, mostrar detalles
                            if isinstance(relation_value, list):
                                logger.info(f"DEBUG - Es lista con {len(relation_value)} elementos")
                                if relation_value:
                                    logger.info(f"DEBUG - Primer elemento: {relation_value[0]}")
                                    logger.info(f"DEBUG - Tipo primer elemento: {type(relation_value[0])}")
                        else:
                            logger.warning(f"DEBUG - Relación '{relation_name}' NO encontrada con hasattr")
                        
                        # Verificar usando __dict__
                        if hasattr(first_result, '__dict__'):
                            dict_attrs = first_result.__dict__
                            if relation_name in dict_attrs:
                                logger.info(f"DEBUG - Relación '{relation_name}' encontrada en __dict__")
                                logger.info(f"DEBUG - Valor en __dict__: {dict_attrs[relation_name]}")
                            else:
                                logger.warning(f"DEBUG - Relación '{relation_name}' NO encontrada en __dict__")
                                logger.info(f"DEBUG - Claves disponibles en __dict__: {list(dict_attrs.keys())}")
                
                # Probar conversión a diccionario ANTES del filtrado
                try:
                    test_dict = EnhancedFieldFilter._convert_to_dict_with_relations(first_result)
                    logger.info(f"DEBUG - Conversión a dict exitosa. Claves: {list(test_dict.keys())}")
                    
                    # Verificar si las relaciones están en el diccionario convertido
                    if filters.relations:
                        for relation_config in filters.relations:
                            relation_name = relation_config.relation_name
                            if relation_name in test_dict:
                                logger.info(f"DEBUG - Relación '{relation_name}' presente en dict convertido: {test_dict[relation_name]}")
                            else:
                                logger.warning(f"DEBUG - Relación '{relation_name}' AUSENTE en dict convertido")
                                
                except Exception as conv_error:
                    logger.error(f"DEBUG - Error en conversión a dict: {conv_error}")
            
            # Aplicar filtrado de campos usando EnhancedFieldFilter
            requested_fields, requested_relations = extract_filter_fields(filters)
            
            logger.info(f"DEBUG - requested_fields: {requested_fields}")
            logger.info(f"DEBUG - requested_relations: {requested_relations}")
            
            # Convertir y filtrar usando el sistema de filtros mejorado
            filtered_results = EnhancedFieldFilter.filter_model_response(
                raw_results, 
                requested_fields, 
                requested_relations
            )
            
            logger.info(f"DEBUG - Resultado filtrado exitoso")
            logger.info(f"Post-procesamiento completado. Registros filtrados: {len(filtered_results) if isinstance(filtered_results, list) else 1}")
            
            # DEBUG FINAL: Verificar resultado filtrado
            if isinstance(filtered_results, list) and filtered_results:
                first_filtered = filtered_results[0]
                logger.info(f"DEBUG - Primer resultado filtrado: {first_filtered}")
                logger.info(f"DEBUG - Claves en resultado filtrado: {list(first_filtered.keys()) if isinstance(first_filtered, dict) else 'No es dict'}")
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Error en get_with_filters_clean: {str(e)}")
            raise
    
    def count_with_filters(self, session, filters: Filter) -> int:
        """Cuenta registros que coinciden con los filtros"""
        try:
            builder = QueryBuilder(self.model_class)
            
            if filters.conditions:
                builder.apply_conditions(filters.conditions, filters.logical_operator)
            
            # Para contar, no necesitamos relaciones, paginación ni ordenamiento
            query = builder.build()
            count_query = select(func.count()).select_from(query.subquery())
            
            return session.exec(count_query).scalar()
            
        except Exception as e:
            logger.error(f"Error contando registros: {str(e)}")
            return 0



class QueryBuilderErrorType(Enum):
    """Tipos de errores específicos del QueryBuilder"""
    
    # Errores de configuración
    INVALID_OPERATOR = "invalid_operator"
    INVALID_ATTRIBUTE = "invalid_attribute" 
    INVALID_VALUE = "invalid_value"
    INVALID_CONDITION = "invalid_condition"
    
    # Errores de relaciones
    RELATION_NOT_FOUND = "relation_not_found"
    INVALID_RELATION_CONFIG = "invalid_relation_config"
    CIRCULAR_RELATION = "circular_relation"
    NESTED_RELATION_ERROR = "nested_relation_error"
    
    # Errores de campos
    FIELD_NOT_FOUND = "field_not_found"
    INVALID_FIELD_NAME = "invalid_field_name"
    FIELD_TYPE_MISMATCH = "field_type_mismatch"
    
    # Errores de consulta
    QUERY_CONSTRUCTION_ERROR = "query_construction_error"
    JOIN_ERROR = "join_error"
    FILTER_ERROR = "filter_error"
    ORDERING_ERROR = "ordering_error"
    
    # Errores de paginación
    INVALID_LIMIT = "invalid_limit"
    INVALID_OFFSET = "invalid_offset"
    
    # Errores de base de datos
    DATABASE_ERROR = "database_error"
    CONNECTION_ERROR = "connection_error"
    
    # Errores generales
    CONFIGURATION_ERROR = "configuration_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_ERROR = "unknown_error"

class QueryBuilderError(Exception):
    """
    Excepción personalizada para errores del QueryBuilder con información detallada
    """
    
    def __init__(
        self,
        message: str,
        error_type: QueryBuilderErrorType = QueryBuilderErrorType.UNKNOWN_ERROR,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        field_name: Optional[str] = None,
        relation_name: Optional[str] = None,
        operator: Optional[str] = None,
        value: Optional[Any] = None,
        original_exception: Optional[Exception] = None
    ):
        """
        Inicializa la excepción con información detallada
        
        Args:
            message: Mensaje principal del error
            error_type: Tipo específico del error
            details: Información adicional del error
            suggestion: Sugerencia para resolver el error
            field_name: Nombre del campo relacionado con el error
            relation_name: Nombre de la relación relacionada con el error
            operator: Operador que causó el error
            value: Valor que causó el error
            original_exception: Excepción original si existe
        """
        self.message = message
        self.error_type = error_type
        self.details = details or {}
        self.suggestion = suggestion
        self.field_name = field_name
        self.relation_name = relation_name
        self.operator = operator
        self.value = value
        self.original_exception = original_exception
        
        # Construir mensaje completo
        full_message = self._build_full_message()
        super().__init__(full_message)
    
    def _build_full_message(self) -> str:
        """Construye el mensaje completo del error"""
        parts = [self.message]
        
        # Agregar contexto específico
        context_parts = []
        if self.field_name:
            context_parts.append(f"Campo: '{self.field_name}'")
        if self.relation_name:
            context_parts.append(f"Relación: '{self.relation_name}'")
        if self.operator:
            context_parts.append(f"Operador: '{self.operator}'")
        if self.value is not None:
            context_parts.append(f"Valor: '{self.value}'")
        
        if context_parts:
            parts.append(f"Contexto: {', '.join(context_parts)}")
        
        # Agregar detalles adicionales
        if self.details:
            details_str = ", ".join([f"{k}: {v}" for k, v in self.details.items()])
            parts.append(f"Detalles: {details_str}")
        
        # Agregar sugerencia
        if self.suggestion:
            parts.append(f"Sugerencia: {self.suggestion}")
        
        # Agregar excepción original
        if self.original_exception:
            parts.append(f"Error original: {str(self.original_exception)}")
        
        return " | ".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el error a diccionario para respuestas JSON"""
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "details": self.details,
            "suggestion": self.suggestion,
            "context": {
                "field_name": self.field_name,
                "relation_name": self.relation_name,
                "operator": self.operator,
                "value": self.value
            },
            "original_error": str(self.original_exception) if self.original_exception else None
        }
    
    @classmethod
    def invalid_operator(cls, operator: str, field_name: str = None, valid_operators: List[str] = None):
        """Crea un error para operador inválido"""
        suggestion = None
        if valid_operators:
            suggestion = f"Operadores válidos: {', '.join(valid_operators)}"
        
        return cls(
            message=f"Operador '{operator}' no es válido",
            error_type=QueryBuilderErrorType.INVALID_OPERATOR,
            suggestion=suggestion,
            field_name=field_name,
            operator=operator,
            details={"valid_operators": valid_operators} if valid_operators else None
        )
    
    @classmethod
    def relation_not_found(cls, relation_name: str, available_relations: List[str] = None):
        """Crea un error para relación no encontrada"""
        suggestion = None
        if available_relations:
            suggestion = f"Relaciones disponibles: {', '.join(available_relations)}"
        
        return cls(
            message=f"Relación '{relation_name}' no encontrada",
            error_type=QueryBuilderErrorType.RELATION_NOT_FOUND,
            suggestion=suggestion,
            relation_name=relation_name,
            details={"available_relations": available_relations} if available_relations else None
        )
    
    @classmethod
    def field_not_found(cls, field_name: str, relation_name: str = None, available_fields: List[str] = None):
        """Crea un error para campo no encontrado"""
        context = f"en la relación '{relation_name}'" if relation_name else "en la entidad principal"
        suggestion = None
        if available_fields:
            suggestion = f"Campos disponibles: {', '.join(available_fields)}"
        
        return cls(
            message=f"Campo '{field_name}' no encontrado {context}",
            error_type=QueryBuilderErrorType.FIELD_NOT_FOUND,
            suggestion=suggestion,
            field_name=field_name,
            relation_name=relation_name,
            details={"available_fields": available_fields} if available_fields else None
        )
    
    @classmethod
    def invalid_value(cls, value: Any, field_name: str = None, expected_type: str = None):
        """Crea un error para valor inválido"""
        suggestion = None
        if expected_type:
            suggestion = f"Se esperaba un valor de tipo: {expected_type}"
        
        return cls(
            message=f"Valor inválido: '{value}'",
            error_type=QueryBuilderErrorType.INVALID_VALUE,
            suggestion=suggestion,
            field_name=field_name,
            value=value,
            details={"expected_type": expected_type, "received_type": type(value).__name__}
        )
    
    @classmethod
    def query_construction_error(cls, message: str, original_exception: Exception = None):
        """Crea un error para problemas en la construcción de la consulta"""
        return cls(
            message=f"Error construyendo la consulta: {message}",
            error_type=QueryBuilderErrorType.QUERY_CONSTRUCTION_ERROR,
            original_exception=original_exception,
            suggestion="Verifique la configuración de filtros y relaciones"
        )
    
    @classmethod
    def database_error(cls, message: str, original_exception: Exception = None):
        """Crea un error para problemas de base de datos"""
        return cls(
            message=f"Error de base de datos: {message}",
            error_type=QueryBuilderErrorType.DATABASE_ERROR,
            original_exception=original_exception,
            suggestion="Verifique la conexión a la base de datos y la sintaxis SQL"
        )
    
    @classmethod
    def invalid_pagination(cls, limit: int = None, offset: int = None):
        """Crea un error para parámetros de paginación inválidos"""
        issues = []
        if limit is not None and limit < 0:
            issues.append(f"limit no puede ser negativo: {limit}")
        if offset is not None and offset < 0:
            issues.append(f"offset no puede ser negativo: {offset}")
        
        message = "Parámetros de paginación inválidos: " + ", ".join(issues)
        
        return cls(
            message=message,
            error_type=QueryBuilderErrorType.INVALID_LIMIT if limit is not None else QueryBuilderErrorType.INVALID_OFFSET,
            suggestion="Use valores no negativos para limit y offset",
            details={"limit": limit, "offset": offset}
        )

# Errores específicos adicionales
class QueryBuilderValidationError(QueryBuilderError):
    """Error específico para validaciones del QueryBuilder"""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('error_type', QueryBuilderErrorType.VALIDATION_ERROR)
        super().__init__(message, **kwargs)

class QueryBuilderConfigurationError(QueryBuilderError):
    """Error específico para configuración del QueryBuilder"""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('error_type', QueryBuilderErrorType.CONFIGURATION_ERROR)
        super().__init__(message, **kwargs)

class QueryBuilderJoinError(QueryBuilderError):
    """Error específico para problemas con JOINs"""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('error_type', QueryBuilderErrorType.JOIN_ERROR)
        super().__init__(message, **kwargs)
