// =======================
// QUERY BUILDER CLASS
// =======================


class QueryBuilder {
    constructor() {
      this.query = {
        conditions: [],
        relations: [],
        limit: 10,
        offset: 0,
        order_by: null,
        order_direction: 'asc'
      };
    }
  
    // Métodos para condiciones
    where(attribute, operator, value) {
      this.query.conditions.push({ attribute, operator, value });
      return this;
    }
  
    // Métodos de conveniencia para operadores comunes
    equals(attribute, value) {
      return this.where(attribute, 'eq', value);
    }
  
    contains(attribute, value) {
      return this.where(attribute, 'contains', value);
    }
  
    greaterThan(attribute, value) {
      return this.where(attribute, 'gt', value);
    }
  
    greaterOrEqual(attribute, value) {
      return this.where(attribute, 'gte', value);
    }
  
    lessThan(attribute, value) {
      return this.where(attribute, 'lt', value);
    }
  
    lessOrEqual(attribute, value) {
      return this.where(attribute, 'lte', value);
    }
  
    in(attribute, values) {
      return this.where(attribute, 'in', values);
    }
  
    notIn(attribute, values) {
      return this.where(attribute, 'not_in', values);
    }
  
    isNull(attribute) {
      return this.where(attribute, 'is_null', null);
    }
  
    isNotNull(attribute) {
      return this.where(attribute, 'is_not_null', null);
    }
  
    // Métodos para relaciones
    include(relationName, strategy = 'select', nestedRelations = []) {
      const relation = {
        relation_name: relationName,
        load_strategy: strategy
      };
      
      if (nestedRelations.length > 0) {
        relation.nested_relations = nestedRelations;
      }
      
      this.query.relations.push(relation);
      return this;
    }
  
    // Método para incluir relaciones anidadas de forma fluida
    includeNested(relationName, strategy = 'select') {
      const relationBuilder = new RelationBuilder(relationName, strategy);
      return {
        ...this,
        with: (callback) => {
          callback(relationBuilder);
          this.query.relations.push(relationBuilder.build());
          return this;
        }
      };
    }
  
    // Paginación
    limit(limit) {
      this.query.limit = limit;
      return this;
    }
  
    offset(offset) {
      this.query.offset = offset;
      return this;
    }
  
    page(pageNumber, pageSize = 10) {
      this.query.limit = pageSize;
      this.query.offset = (pageNumber - 1) * pageSize;
      return this;
    }
  
    // Ordenamiento
    orderBy(attribute, direction = 'asc') {
      this.query.order_by = attribute;
      this.query.order_direction = direction;
      return this;
    }
  
    orderByDesc(attribute) {
      return this.orderBy(attribute, 'desc');
    }
  
    // Construir la query final
    build() {
      return { ...this.query };
    }
  
    // Resetear builder
    reset() {
      this.query = {
        conditions: [],
        relations: [],
        limit: 10,
        offset: 0,
        order_by: null,
        order_direction: 'asc'
      };
      return this;
    }
  }
  
  // =======================
  // RELATION BUILDER CLASS
  // =======================
  
  class RelationBuilder {
    constructor(relationName, strategy = 'select') {
      this.relation = {
        relation_name: relationName,
        load_strategy: strategy,
        nested_relations: []
      };
    }
  
    include(relationName, strategy = 'select') {
      this.relation.nested_relations.push({
        relation_name: relationName,
        load_strategy: strategy
      });
      return this;
    }
  
    includeNested(relationName, strategy = 'select') {
      const nestedBuilder = new RelationBuilder(relationName, strategy);
      return {
        ...this,
        with: (callback) => {
          callback(nestedBuilder);
          this.relation.nested_relations.push(nestedBuilder.build());
          return this;
        }
      };
    }
  
    build() {
      return { ...this.relation };
    }
  }
  
  // =======================
  // FUNCIONES DE UTILIDAD
  // =======================
  
  // Factory function para crear nuevos builders
  function createQuery() {
    return new QueryBuilder();
  }
  
  // Función para búsquedas rápidas
  function quickSearch(searchTerm, searchFields = ['name']) {
    const builder = createQuery();
    
    searchFields.forEach(field => {
      builder.contains(field, searchTerm);
    });
    
    return builder;
  }
  
  // Función para rangos de fecha
  function dateRange(dateField, startDate, endDate) {
    return createQuery()
      .greaterOrEqual(dateField, startDate)
      .lessOrEqual(dateField, endDate);
  }
  
  // Función para filtros de estado común
  function statusFilter(status) {
    return createQuery().equals('status', status);
  }
  
  // =======================
  // EJEMPLOS DE USO
  // =======================
  
  // Ejemplo 1: Búsqueda simple
  const simpleQuery = createQuery()
    .contains('name', 'test')
    .equals('status', 'active')
    .include('user')
    .limit(20)
    .build();
  
  console.log('Simple Query:', JSON.stringify(simpleQuery, null, 2));
  
  // Ejemplo 2: Búsqueda compleja con relaciones anidadas
  const complexQuery = createQuery()
    .contains('name', 'test')
    .equals('user.email', 'user@example.com')
    .greaterOrEqual('user.profile.age', 18)
    .includeNested('user')
    .with(userRelation => {
      userRelation
        .include('profile', 'joined')
        .include('permissions', 'select');
    })
    .include('category', 'joined')
    .orderByDesc('user.profile.created_at')
    .page(1, 20)
    .build();
  
  console.log('Complex Query:', JSON.stringify(complexQuery, null, 2));
  
  // Ejemplo 3: Usando funciones de utilidad
  const quickSearchQuery = quickSearch('john', ['name', 'email'])
    .include('profile')
    .build();
  
  console.log('Quick Search:', JSON.stringify(quickSearchQuery, null, 2));
  
  // Ejemplo 4: Filtro de rango de fechas
  const dateRangeQuery = dateRange('created_at', '2024-01-01', '2024-12-31')
    .include('user')
    .build();
  
  console.log('Date Range Query:', JSON.stringify(dateRangeQuery, null, 2));
  
  // =======================
  // INTEGRACIÓN CON API
  // =======================
  
  class ApiClient {
    constructor(baseUrl) {
      this.baseUrl = baseUrl;
    }
  
    async searchWithQuery(endpoint, queryBuilder) {
      const query = queryBuilder.build();
      
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(query)
      });
  
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
  
      return await response.json();
    }
  }
  
  // Ejemplo de uso con API
  const api = new ApiClient('https://api.example.com');
  
  async function searchUsers() {
    const query = createQuery()
      .contains('name', 'john')
      .greaterOrEqual('age', 18)
      .include('profile')
      .orderBy('created_at', 'desc')
      .page(1, 10);
  
    try {
      const users = await api.searchWithQuery('/users/search', query);
      console.log('Users found:', users);
      return users;
    } catch (error) {
      console.error('Search failed:', error);
    }
  }
  
  // =======================
  // VALIDACIÓN Y HELPERS
  // =======================
  
  class QueryValidator {
    static validateOperator(operator) {
      const validOperators = [
        'eq', 'ne', 'gt', 'gte', 'lt', 'lte', 
        'contains', 'icontains', 'startswith', 'endswith',
        'in', 'not_in', 'is_null', 'is_not_null'
      ];
      return validOperators.includes(operator);
    }
  
    static validateLoadStrategy(strategy) {
      const validStrategies = ['select', 'joined', 'subquery'];
      return validStrategies.includes(strategy);
    }
  
    static validate(query) {
      const errors = [];
  
      // Validar condiciones
      query.conditions?.forEach((condition, index) => {
        if (!this.validateOperator(condition.operator)) {
          errors.push(`Invalid operator '${condition.operator}' at condition ${index}`);
        }
      });
  
      // Validar estrategias de carga
      query.relations?.forEach((relation, index) => {
        if (!this.validateLoadStrategy(relation.load_strategy)) {
          errors.push(`Invalid load strategy '${relation.load_strategy}' at relation ${index}`);
        }
      });
  
      return errors;
    }
  }
  
  // Helper para autocompletar atributos (se podría alimentar desde el backend)
  const AVAILABLE_ATTRIBUTES = {
    user: ['id', 'name', 'email', 'created_at', 'status'],
    'user.profile': ['age', 'city', 'country', 'phone'],
    'user.profile.address': ['street', 'city', 'postal_code'],
    product: ['id', 'name', 'price', 'category', 'stock'],
    order: ['id', 'total', 'status', 'created_at']
  };
  
  function getAvailableAttributes(prefix = '') {
    return Object.keys(AVAILABLE_ATTRIBUTES)
      .filter(key => key.startsWith(prefix))
      .reduce((acc, key) => {
        acc[key] = AVAILABLE_ATTRIBUTES[key];
        return acc;
      }, {});
  }
  
  // =======================
  // EXPORT PARA MÓDULOS
  // =======================
  
  // Si estás usando módulos ES6
  // export { QueryBuilder, RelationBuilder, createQuery, quickSearch, dateRange, statusFilter, ApiClient, QueryValidator };
  
  // Para usar en el navegador directamente
  window.QueryBuilder = QueryBuilder;
  window.createQuery = createQuery;
  window.quickSearch = quickSearch;
  window.dateRange = dateRange;
  window.ApiClient = ApiClient;