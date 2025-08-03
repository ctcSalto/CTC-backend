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
        
        Args:
            data: Los datos de respuesta (lista de diccionarios o diccionario único)
            requested_fields: Lista de campos solicitados para la entidad principal
            requested_relations: Lista de relaciones con sus campos solicitados
            
        Returns:
            Datos filtrados con solo los campos solicitados
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
        """
        Filtra un objeto único de forma recursiva
        """
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
                nested_relations = relation.get('relations', [])  # Relaciones anidadas
                
                if relation_name and relation_name in obj:
                    relation_data = obj[relation_name]
                    
                    if relation_data is not None:
                        # Filtrar recursivamente la relación
                        filtered_relation = FieldFilter._filter_relation_recursive(
                            relation_data, 
                            relation_fields, 
                            nested_relations
                        )
                        filtered_obj[relation_name] = filtered_relation
        
        return filtered_obj
    
    @staticmethod
    def _filter_relation_recursive(
        relation_data: Union[List[Dict[str, Any]], Dict[str, Any]], 
        requested_fields: List[str],
        nested_relations: Optional[List[Dict[str, Any]]] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Filtra los campos de una relación de forma recursiva
        """
        if not relation_data:
            return relation_data
        
        # Procesar lista de objetos relacionados
        if isinstance(relation_data, list):
            return [
                FieldFilter._filter_single_relation_object(item, requested_fields, nested_relations)
                for item in relation_data
            ]
        
        # Procesar objeto relacionado único
        if isinstance(relation_data, dict):
            return FieldFilter._filter_single_relation_object(relation_data, requested_fields, nested_relations)
            
        return relation_data
    
    @staticmethod
    def _filter_single_relation_object(
        obj: Dict[str, Any],
        requested_fields: List[str],
        nested_relations: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Filtra un objeto de relación individual con soporte para relaciones anidadas
        """
        if not isinstance(obj, dict):
            return obj
        
        filtered_obj = {}
        
        # Obtener nombres de relaciones anidadas
        nested_relation_names = set()
        if nested_relations:
            nested_relation_names = {rel.get('relation_name', '') for rel in nested_relations}
        
        # Debug: mostrar qué campos se están procesando
        print(f"DEBUG - Processing object keys: {list(obj.keys())}")
        print(f"DEBUG - Requested fields for relation: {requested_fields}")
        print(f"DEBUG - Nested relation names: {nested_relation_names}")
        
        # Filtrar campos solicitados (excluyendo relaciones anidadas)
        if requested_fields:
            for field in requested_fields:
                if field in obj and field not in nested_relation_names:
                    filtered_obj[field] = obj[field]
                    print(f"DEBUG - Added field: {field} = {obj[field]}")
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
                        # Llamada recursiva para la relación anidada
                        filtered_nested = FieldFilter._filter_relation_recursive(
                            nested_data,
                            nested_fields,
                            deeper_relations
                        )
                        filtered_obj[nested_relation_name] = filtered_nested
        
        print(f"DEBUG - Final filtered object: {filtered_obj}")
        return filtered_obj

class EnhancedFieldFilter(FieldFilter):
    """
    Versión mejorada que maneja modelos SQLModel/Pydantic y objetos personalizados
    """
    
    @staticmethod
    def filter_model_response(
        data: Union[List[SQLModel], SQLModel, List[Dict], Dict],
        requested_fields: Optional[List[str]] = None,
        requested_relations: Optional[List[Dict[str, Any]]] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Filtra respuestas que pueden ser modelos SQLModel, objetos personalizados o diccionarios
        """
        # Convertir modelos a diccionarios si es necesario
        if isinstance(data, list):
            dict_data = []
            for item in data:
                converted_item = EnhancedFieldFilter._convert_to_dict(item)
                dict_data.append(converted_item)
        else:
            dict_data = EnhancedFieldFilter._convert_to_dict(data)
        
        return FieldFilter.filter_response_fields(dict_data, requested_fields, requested_relations)
    
    @staticmethod
    def _convert_to_dict(item):
        """
        Convierte un objeto a diccionario, manejando diferentes tipos
        """
        # Caso 1: Ya es un diccionario
        if isinstance(item, dict):
            return item
        
        # Caso 2: Modelo SQLModel/Pydantic v2
        if hasattr(item, 'model_dump'):
            return item.model_dump()
        
        # Caso 3: Modelo Pydantic v1
        if hasattr(item, 'dict'):
            return item.dict()
        
        # Caso 4: Objeto con __dict__ (como FilteredResult)
        if hasattr(item, '__dict__'):
            return EnhancedFieldFilter._extract_from_object_dict(item)
        
        # Caso 5: Objeto que implementa __getattribute__ o similares
        # Intentar obtener atributos comunes de forma dinámica
        try:
            return EnhancedFieldFilter._extract_from_dynamic_object(item)
        except:
            return item
    
    @staticmethod
    def _extract_from_object_dict(obj):
        """
        Extrae datos de un objeto usando __dict__
        """
        result = {}
        for key, value in obj.__dict__.items():
            if not key.startswith('_'):  # Ignorar atributos privados
                # Si el valor es una lista de objetos, convertir recursivamente
                if isinstance(value, list):
                    result[key] = [EnhancedFieldFilter._convert_to_dict(v) for v in value]
                # Si el valor es un objeto, convertir recursivamente
                elif hasattr(value, '__dict__') and not isinstance(value, (str, int, float, bool, type(None))):
                    result[key] = EnhancedFieldFilter._convert_to_dict(value)
                else:
                    result[key] = value
        return result
    
    @staticmethod
    def _extract_from_dynamic_object(obj):
        """
        Intenta extraer datos de un objeto de forma dinámica
        """
        result = {}
        
        # Intentar obtener todos los atributos del objeto
        try:
            # Obtener atributos del objeto
            for attr_name in dir(obj):
                if not attr_name.startswith('_') and not callable(getattr(obj, attr_name)):
                    try:
                        value = getattr(obj, attr_name)
                        
                        # Si es una lista, convertir cada elemento
                        if isinstance(value, list):
                            result[attr_name] = [EnhancedFieldFilter._convert_to_dict(v) for v in value]
                        # Si es un objeto complejo, convertir recursivamente
                        elif hasattr(value, '__dict__') and not isinstance(value, (str, int, float, bool, type(None))):
                            result[attr_name] = EnhancedFieldFilter._convert_to_dict(value)
                        else:
                            result[attr_name] = value
                    except:
                        continue
        except:
            pass
        
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
    """
    Extrae los campos solicitados del objeto Filter
    
    Args:
        filters: Objeto Filter que contiene la información de campos y relaciones
        
    Returns:
        Tupla con (campos_principales, relaciones_solicitadas)
    """
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
    """
    Función genérica para filtrar cualquier tipo de respuesta basándose en un objeto Filter
    """
    requested_fields, requested_relations = extract_filter_fields(filters)
    return FieldFilter.filter_response_fields(data, requested_fields, requested_relations)

def filter_model_response(data: Union[List, Dict], filters: Filter) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Función genérica para filtrar respuestas que pueden ser modelos SQLModel/Pydantic
    """
    requested_fields, requested_relations = extract_filter_fields(filters)
    
    # Debug logging
    print(f"DEBUG - Requested fields: {requested_fields}")
    print(f"DEBUG - Requested relations: {requested_relations}")
    
    result = EnhancedFieldFilter.filter_model_response(data, requested_fields, requested_relations)
    
    print(f"DEBUG - Filtered result: {result}")
    
    return result

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

# Funciones auxiliares para crear errores comunes
def create_field_validation_error(field_name: str, value: Any, expected_type: str = None):
    """Función auxiliar para crear errores de validación de campos"""
    return QueryBuilderError.invalid_value(value, field_name, expected_type)

def create_relation_error(relation_name: str, available_relations: List[str] = None):
    """Función auxiliar para crear errores de relaciones"""
    return QueryBuilderError.relation_not_found(relation_name, available_relations)

def create_operator_error(operator: str, field_name: str = None, valid_operators: List[str] = None):
    """Función auxiliar para crear errores de operadores"""
    return QueryBuilderError.invalid_operator(operator, field_name, valid_operators)

# Ejemplo de uso en context manager
class QueryBuilderErrorHandler:
    """Context manager para manejo de errores del QueryBuilder"""
    
    def __init__(self, operation: str = "QueryBuilder operation"):
        self.operation = operation
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and not isinstance(exc_val, QueryBuilderError):
            # Convertir excepción genérica a QueryBuilderError
            raise QueryBuilderError.query_construction_error(
                f"Error durante {self.operation}",
                original_exception=exc_val
            ) from exc_val
        return False

class QueryBuilder:
    def __init__(self, model_class):
        self.model_class = model_class
        self.query = select(model_class)
        self.joins_applied = set()
        self._model_registry = {}
        self._field_selection_applied = False
        self._selected_fields = None
        self._requires_joins = False
    
    def analyze_requirements(self, filters: 'Filter'):
        """Analiza si necesitamos JOINs antes de aplicar selección de campos"""
        if not filters.conditions:
            return self
            
        for condition in filters.conditions:
            if isinstance(condition, Condition):
                if '.' in condition.attribute:
                    self._requires_joins = True
                    break
            elif isinstance(condition, ConditionGroup):
                if self._analyze_condition_group_joins(condition):
                    self._requires_joins = True
                    break
                    
        # También verificar order_by
        if filters.order_by and '.' in filters.order_by:
            self._requires_joins = True
            
        return self
    
    def _analyze_condition_group_joins(self, condition_group: ConditionGroup) -> bool:
        """Verifica si un grupo de condiciones requiere JOINs"""
        for condition in condition_group.conditions:
            if isinstance(condition, Condition):
                if '.' in condition.attribute:
                    return True
            elif isinstance(condition, ConditionGroup):
                if self._analyze_condition_group_joins(condition):
                    return True
        return False

    def apply_field_selection(self, fields: Optional[List[str]]):
        """Aplica selección de campos específicos a la entidad principal"""
        if not fields:
            return self
            
        try:
            # Validar que todos los campos existen en el modelo
            valid_fields = []
            for field_name in fields:
                if hasattr(self.model_class, field_name):
                    valid_fields.append(getattr(self.model_class, field_name))
                else:
                    logger.warning(f"Campo '{field_name}' no encontrado en {self.model_class.__name__}")
            
            if valid_fields:
                # CLAVE: Solo aplicar selección de campos si NO necesitamos JOINs
                # Si necesitamos JOINs, los campos se filtrarán después en el procesamiento
                if not self._requires_joins:
                    self.query = select(*valid_fields)
                    self._field_selection_applied = True
                    logger.info(f"Selección de campos aplicada: {[f.name for f in valid_fields]}")
                else:
                    logger.info(f"Selección de campos diferida debido a JOINs requeridos")
                
                self._selected_fields = [f.name for f in valid_fields]
                
        except Exception as e:
            logger.error(f"Error aplicando selección de campos: {str(e)}")
            
        return self
    
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
        """Aplica condición en relación - CORREGIDO"""
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
                    
                    # CORREGIDO: Si tenemos selección de campos aplicada, revertir a selección completa
                    if self._field_selection_applied:
                        self.query = select(self.model_class).join(relation_attr)
                        self._field_selection_applied = False
                        logger.info(f"Selección de campos revertida para permitir JOIN con {relation_name}")
                    else:
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
            raise QueryBuilderError(f"Error en operador '{operator}': {str(e)}")
    
    def apply_relations(self, relations: List[RelationConfig]):
        """Aplica carga de relaciones con selección de campos - CORREGIDO"""
        for relation_config in relations:
            try:
                self._apply_relation_loading(relation_config)
            except Exception as e:
                logger.error(f"Error cargando relación '{relation_config.relation_name}': {str(e)}")
                continue
        return self
    
    def _apply_relation_loading(self, relation_config: RelationConfig):
        """Aplica carga de una relación específica con selección de campos - CORREGIDO"""
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
        
        # CORREGIDO: Aplicar selección de campos para esta relación
        if relation_config.fields:
            try:
                related_model = self._get_related_model(self.model_class, relation_config.relation_name)
                if related_model:
                    # Validar y obtener campos válidos
                    valid_fields = []
                    for field_name in relation_config.fields:
                        if hasattr(related_model, field_name):
                            valid_fields.append(field_name)
                        else:
                            logger.warning(f"Campo '{field_name}' no encontrado en relación {relation_config.relation_name}")
                    
                    if valid_fields:
                        # CLAVE: Usar load_only correctamente
                        loader = loader.load_only(*valid_fields)
                        logger.info(f"Campos específicos cargados para {relation_config.relation_name}: {valid_fields}")
                        
            except Exception as e:
                logger.error(f"Error aplicando selección de campos para relación {relation_config.relation_name}: {str(e)}")
        
        # Aplicar relaciones anidadas
        if relation_config.nested_relations:
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
                        
                        # Aplicar selección de campos para relación anidada
                        if nested_relation.fields:
                            nested_model = self._get_related_model(related_model, nested_relation.relation_name)
                            if nested_model:
                                valid_nested_fields = []
                                for field_name in nested_relation.fields:
                                    if hasattr(nested_model, field_name):
                                        valid_nested_fields.append(field_name)
                                    else:
                                        logger.warning(f"Campo '{field_name}' no encontrado en relación anidada {nested_relation.relation_name}")
                                
                                if valid_nested_fields:
                                    nested_loader = nested_loader.load_only(*valid_nested_fields)
                                    logger.info(f"Campos específicos cargados para relación anidada {nested_relation.relation_name}: {valid_nested_fields}")
                        
                        loader = nested_loader
                        
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
        """Aplica ordenamiento con mejor manejo de relaciones - CORREGIDO"""
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
                        
                        # CORREGIDO: Manejar conflicto con selección de campos
                        if self._field_selection_applied:
                            self.query = select(self.model_class).join(relation_attr)
                            self._field_selection_applied = False
                            logger.info(f"Selección de campos revertida para ordenamiento por {relation_name}")
                        else:
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
        """Obtiene registros aplicando filtros con selección de campos - CORREGIDO"""
        try:
            builder = QueryBuilder(self.model_class)
            
            # CLAVE: Analizar requisitos ANTES de aplicar selección de campos
            builder.analyze_requirements(filters)
            
            # Aplicar selección de campos (se diferirá si hay JOINs)
            if filters.fields:
                builder.apply_field_selection(filters.fields)
            
            # Aplicar condiciones (pueden requerir JOINs)
            if filters.conditions:
                builder.apply_conditions(filters.conditions, filters.logical_operator)
            
            # Aplicar relaciones
            if filters.relations:
                builder.apply_relations(filters.relations)
                
            # Aplicar ordenamiento
            if filters.order_by:
                builder.apply_ordering(filters.order_by, filters.order_direction)
            
            # Aplicar paginación
            builder.apply_pagination(filters.limit, filters.offset)
            
            query = builder.build()
            results = session.exec(query).all()
            
            # NUEVO: Post-procesamiento para aplicar selección de campos si fue diferida
            if filters.fields and builder._selected_fields and builder._requires_joins:
                filtered_results = []
                for result in results:
                    if hasattr(result, '__dict__'):
                        # Crear objeto filtrado con solo los campos solicitados
                        filtered_dict = {}
                        for field_name in builder._selected_fields:
                            if hasattr(result, field_name):
                                filtered_dict[field_name] = getattr(result, field_name)
                        
                        # Para relaciones, mantener las que están en el filtro
                        if filters.relations:
                            for relation_config in filters.relations:
                                if hasattr(result, relation_config.relation_name):
                                    filtered_dict[relation_config.relation_name] = getattr(result, relation_config.relation_name)
                        
                        # Crear un objeto que simule el resultado original pero filtrado
                        # Esto es una aproximación, idealmente deberías crear una instancia del modelo
                        class FilteredResult:
                            def __init__(self, data):
                                for key, value in data.items():
                                    setattr(self, key, value)
                        
                        filtered_results.append(FilteredResult(filtered_dict))
                    else:
                        filtered_results.append(result)
                        
                results = filtered_results
                logger.info(f"Post-procesamiento de campos aplicado")
            
            logger.info(f"Query ejecutada exitosamente. Registros obtenidos: {len(results)}")
            return results
        except QueryBuilderError:
            raise
        except Exception as e:
            logger.error(f"Error ejecutando query con filtros: {str(e)}")
            raise QueryBuilderError(f"Error ejecutando consulta: {str(e)}")
        
    def get_with_filters_clean(self, session, filters: Filter):
        """
        Obtiene usuarios con filtros y limpia valores None (incluyendo relaciones)
        """
        try:
            # Llamar al método padre para obtener los resultados
            raw_results = self.get_with_filters(session, filters)
            
            if not raw_results:
                return []
            
            # Convertir y limpiar los resultados
            cleaned_results = self._convert_and_clean_results(raw_results, filters)
            
            return cleaned_results
            
        except Exception as e:
            logger.error(f"Error en get_with_filters_clean: {str(e)}")
            raise
    
    def _convert_and_clean_results(self, results, filters: Filter):
        """
        Convierte Row objects a objetos User y limpia valores None
        """
        if not results:
            return []
        
        cleaned_results = []
        
        for result in results:
            cleaned_user = self._process_single_result(result, filters)
            if cleaned_user:
                cleaned_results.append(cleaned_user)
        
        return cleaned_results
    
    def _process_single_result(self, result, filters: Filter):
        """
        Procesa un solo resultado, manejando Row objects y objetos User
        """
        try:
            # Si es un Row object (cuando se usan campos específicos)
            if hasattr(result, '_fields'):
                print(f"DEBUG: Row object detectado con campos: {result._fields}")
                user_dict = self._row_to_dict(result, filters.fields)
            # Si es un objeto User completo
            elif hasattr(result, 'model_dump'):
                print(f"DEBUG: Objeto User con model_dump")
                user_dict = result.model_dump()
            elif hasattr(result, 'dict'):
                print(f"DEBUG: Objeto User con dict")
                user_dict = result.dict()
            elif hasattr(result, '__dict__'):
                print(f"DEBUG: Objeto con __dict__")
                user_dict = {k: v for k, v in result.__dict__.items() if not k.startswith('_')}
            else:
                print(f"DEBUG: Tipo desconocido: {type(result)}")
                return result
            
            print(f"DEBUG: user_dict antes de limpiar: {user_dict}")
            
            # Limpiar valores None del usuario principal
            cleaned_user_dict = self._clean_dict_none_values(user_dict, filters.fields)
            
            # Limpiar relaciones si existen
            if filters.relations:
                cleaned_user_dict = self._clean_relations_none_values(
                    cleaned_user_dict, filters.relations
                )
            
            print(f"DEBUG: user_dict después de limpiar: {cleaned_user_dict}")
            
            # Crear objeto User limpio
            return self._create_clean_result_object(cleaned_user_dict)
            
        except Exception as e:
            logger.error(f"Error procesando resultado individual: {str(e)}")
            return None
    
    def _row_to_dict(self, row, requested_fields):
        """
        Convierte un Row object a diccionario usando los campos solicitados
        """
        if not requested_fields:
            # Si no hay campos específicos, usar los nombres de las columnas del Row
            if hasattr(row, '_fields'):
                return dict(zip(row._fields, row))
            else:
                return {}
        
        # Mapear valores a los campos solicitados
        user_dict = {}
        for i, field_name in enumerate(requested_fields):
            if i < len(row):
                value = row[i]
                if value is not None:  # Solo agregar valores no None
                    user_dict[field_name] = value
        
        return user_dict
    
    def _clean_dict_none_values(self, user_dict, requested_fields=None):
        """
        Limpia valores None de un diccionario de usuario
        """
        cleaned_dict = {}
        
        # Si hay campos específicos solicitados, solo procesar esos
        fields_to_process = requested_fields if requested_fields else user_dict.keys()
        
        for field in fields_to_process:
            if field in user_dict:
                value = user_dict[field]
                # Solo agregar valores que no sean None
                if value is not None:
                    cleaned_dict[field] = value
        
        return cleaned_dict
    
    def _clean_relations_none_values(self, user_dict, relations_config):
        """
        Limpia valores None de las relaciones del usuario
        """
        for relation_config in relations_config:
            relation_name = relation_config.relation_name
            
            if relation_name in user_dict:
                relation_data = user_dict[relation_name]
                
                if relation_data is not None:
                    # Si es una lista de relaciones
                    if isinstance(relation_data, list):
                        cleaned_relations = []
                        for relation_item in relation_data:
                            cleaned_relation = self._clean_single_relation(
                                relation_item, relation_config
                            )
                            if cleaned_relation:
                                cleaned_relations.append(cleaned_relation)
                        user_dict[relation_name] = cleaned_relations
                    else:
                        # Si es una sola relación
                        cleaned_relation = self._clean_single_relation(
                            relation_data, relation_config
                        )
                        if cleaned_relation:
                            user_dict[relation_name] = cleaned_relation
                        else:
                            # Si la relación queda vacía, eliminarla
                            del user_dict[relation_name]
        
        return user_dict
    
    def _clean_single_relation(self, relation_item, relation_config):
        """
        Limpia una sola relación
        """
        try:
            # Convertir relación a diccionario
            if hasattr(relation_item, 'model_dump'):
                relation_dict = relation_item.model_dump()
            elif hasattr(relation_item, 'dict'):
                relation_dict = relation_item.dict()
            elif hasattr(relation_item, '__dict__'):
                relation_dict = {k: v for k, v in relation_item.__dict__.items() 
                               if not k.startswith('_')}
            elif isinstance(relation_item, dict):
                relation_dict = relation_item
            else:
                return relation_item
            
            # Limpiar campos None de la relación
            cleaned_relation_dict = {}
            fields_to_process = relation_config.fields if relation_config.fields else relation_dict.keys()
            
            for field in fields_to_process:
                if field in relation_dict:
                    value = relation_dict[field]
                    if value is not None:
                        cleaned_relation_dict[field] = value
            
            # Procesar relaciones anidadas recursivamente
            if relation_config.nested_relations:
                cleaned_relation_dict = self._clean_nested_relations(
                    cleaned_relation_dict, relation_config.nested_relations
                )
            
            return cleaned_relation_dict if cleaned_relation_dict else None
            
        except Exception as e:
            logger.error(f"Error limpiando relación: {str(e)}")
            return None
    
    def _clean_nested_relations(self, relation_dict, nested_relations_config):
        """
        Limpia relaciones anidadas recursivamente
        """
        for nested_config in nested_relations_config:
            nested_name = nested_config.relation_name
            
            if nested_name in relation_dict:
                nested_data = relation_dict[nested_name]
                
                if nested_data is not None:
                    if isinstance(nested_data, list):
                        cleaned_nested = []
                        for nested_item in nested_data:
                            cleaned_item = self._clean_single_relation(nested_item, nested_config)
                            if cleaned_item:
                                cleaned_nested.append(cleaned_item)
                        relation_dict[nested_name] = cleaned_nested
                    else:
                        cleaned_nested = self._clean_single_relation(nested_data, nested_config)
                        if cleaned_nested:
                            relation_dict[nested_name] = cleaned_nested
                        else:
                            del relation_dict[nested_name]
        
        return relation_dict
    
    def _create_clean_result_object(self, cleaned_dict):
        """
        Crea un objeto User limpio a partir del diccionario limpio
        """
        class CleanModel:
            def __init__(self, data):
                for key, value in data.items():
                    setattr(self, key, value)
            
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
            
            def dict(self):
                return self.model_dump()
        
        return CleanModel(cleaned_dict)
    
    def count_with_filters(self, session, filters: Filter) -> int:
        """Cuenta registros que coinciden con los filtros"""
        try:
            builder = QueryBuilder(self.model_class)
            
            if filters.conditions:
                builder.apply_conditions(filters.conditions, filters.logical_operator)
            
            # Para contar, no necesitamos selección de campos, relaciones, paginación ni ordenamiento
            query = builder.build()
            count_query = select(func.count()).select_from(query.subquery())
            
            return session.exec(count_query).scalar()
            
        except Exception as e:
            logger.error(f"Error contando registros: {str(e)}")
            return 0