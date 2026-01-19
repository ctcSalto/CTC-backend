# Backend-CTC - Documentación de Arquitectura

## Tabla de Contenidos
- [Stack Tecnológico](#stack-tecnológico)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Patrones de Arquitectura](#patrones-de-arquitectura)
- [Arquitectura de Base de Datos](#arquitectura-de-base-de-datos)
- [Diseño de API](#diseño-de-api)
- [Sistema de Filtros Avanzados](#sistema-de-filtros-avanzados)
- [Arquitectura de Seguridad](#arquitectura-de-seguridad)
- [Integración de Servicios Externos](#integración-de-servicios-externos)
- [Configuración y Entorno](#configuración-y-entorno)
- [Decisiones Arquitectónicas Clave](#decisiones-arquitectónicas-clave)
- [Despliegue](#despliegue)

---

## Stack Tecnológico

### Framework Core y Runtime
- **FastAPI 0.115.12** - Framework web moderno y de alto rendimiento
- **Uvicorn 0.34.3** - Servidor ASGI para producción
- **Python 3.x** - Lenguaje de programación
- **Scalar FastAPI 1.3.0** - Documentación de API mejorada

### Base de Datos y ORM
- **PostgreSQL** - Base de datos relacional principal
- **SQLModel 0.0.24** - ORM que combina SQLAlchemy y Pydantic
- **SQLAlchemy 2.0.41** - Toolkit SQL y ORM
- **Psycopg2 2.9.10** - Adaptador PostgreSQL
- **Alembic 1.16.1** - Herramienta de migración de base de datos

### Caché y Gestión de Sesiones
- **Redis 6.4.0** - Caché en memoria y almacenamiento de lista negra de tokens
- **Python-Redis 0.4.0** - Cliente Redis

### Autenticación y Seguridad
- **PyJWT 2.10.1** - Generación y validación de tokens JWT
- **Python-Jose 3.5.0** - Implementación JOSE para JWT
- **Bcrypt 4.3.0** - Hashing de contraseñas
- **Passlib 1.7.4** - Librería de hashing de contraseñas

### Integración de Servicios Externos
- **Supabase 2.15.3** - Backend-as-a-Service para almacenamiento de archivos
- **Storage3 0.11.3** - Cliente de almacenamiento Supabase
- **MercadoPago SDK 2.3.0** - Procesamiento de pagos
- **Moodle API** - Integración personalizada para LMS

### Procesamiento de Archivos
- **Pillow 11.3.0** - Procesamiento de imágenes y conversión WebP
- **Python-Multipart 0.0.20** - Análisis de datos multipart/form-data

### Utilidades y Desarrollo
- **Pydantic 2.11.5** - Validación de datos usando anotaciones de tipo Python
- **Python-Dotenv 1.1.0** - Gestión de variables de entorno
- **IceCream 2.1.4** - Depuración mejorada
- **Pytest 8.4.1** - Framework de testing
- **Email-Validator 2.2.0** - Validación de emails

---

## Estructura del Proyecto

```
Backend-CTC/
├── main.py                    # Punto de entrada de la aplicación
├── requirements.txt           # Dependencias Python
├── alembic.ini               # Configuración de Alembic
├── Procfile                  # Configuración de despliegue Heroku
├── .env.example              # Template de variables de entorno
│
├── database/                 # Capa de base de datos
│   ├── database.py          # Conexión DB, gestión de sesiones, inicialización de servicios
│   ├── models/              # Definiciones de entidades SQLModel
│   │   ├── user.py         # Modelo User con roles y autenticación
│   │   ├── career.py       # Modelos Career/Course/Workshop/Diploma
│   │   ├── testimony.py    # Testimonios de estudiantes
│   │   ├── news.py         # Noticias/anuncios
│   │   └── test/           # Modelos de prueba
│   └── services/            # Capa de lógica de negocio
│       ├── user_service.py
│       ├── carrer_service.py
│       ├── testimony_service.py
│       ├── news_services.py
│       ├── auth/           # Servicios de autenticación
│       │   ├── security.py    # Hashing de contraseñas, creación/validación JWT
│       │   └── dependencies.py # Dependencias FastAPI para auth
│       ├── filter/         # Sistema de filtros avanzado
│       │   └── filters.py  # QueryBuilder, modelos Filter, filtrado de campos
│       ├── redis/          # Servicios de caché
│       │   └── redis.py    # Operaciones Redis y lista negra de tokens
│       └── supabase/       # Servicios de almacenamiento de archivos
│           └── image_service.py # Carga de imágenes, conversión WebP
│
├── routes/                  # Endpoints API (controladores)
│   ├── auth.py             # Endpoints de autenticación
│   ├── career.py           # Operaciones CRUD de carreras
│   ├── testimony.py        # Gestión de testimonios
│   ├── news.py             # Gestión de noticias
│   ├── moodle/            # Endpoints de integración Moodle
│   │   ├── moodle_user.py
│   │   ├── moodle_course.py
│   │   ├── moodle_category.py
│   │   └── moodle_enrolment.py
│   ├── mercadopago/       # Endpoints de pagos
│   │   └── mercadopago.py
│   └── test/              # Endpoints de testing
│       └── test_filters.py
│
├── external_services/       # Integraciones de APIs externas
│   ├── moodle_api/         # Integración Moodle LMS
│   │   ├── controllers/    # Controladores API Moodle
│   │   ├── models/         # Modelos de datos Moodle
│   │   ├── payloads/       # Esquemas request/response
│   │   └── moodle_config.py
│   └── mercadopago_api/    # Integración de pagos MercadoPago
│       ├── controllers/
│       └── models/
│
├── exceptions/             # Manejo de excepciones personalizado
│   ├── base.py            # Clase base AppException
│   ├── user_exeption.py
│   └── example_exception.py
│
├── utils/                 # Módulos de utilidad
│   └── logger.py         # Configuración logger IceCream
│
├── pages/                # Páginas HTML
│   └── welcome.py        # HTML página de bienvenida
│
└── alembic/              # Migraciones de base de datos
    ├── env.py           # Configuración de entorno Alembic
    └── versions/        # Scripts de migración
```

---

## Patrones de Arquitectura

### 1. Arquitectura por Capas

La aplicación sigue una arquitectura por capas limpia:

- **Capa de Presentación** (`routes/`) - Routers FastAPI manejando peticiones/respuestas HTTP
- **Capa de Lógica de Negocio** (`database/services/`) - Clases Service conteniendo reglas de negocio
- **Capa de Acceso a Datos** (`database/models/`) - Entidades SQLModel y operaciones de base de datos
- **Capa de Servicios Externos** (`external_services/`) - Integraciones de APIs de terceros

### 2. Inyección de Dependencias

El sistema de inyección de dependencias de FastAPI se usa extensivamente:
- `get_session()` - Gestión de sesiones de base de datos
- `get_services()` - Proveedor de instancias singleton de servicios
- `get_current_user()` - Middleware de autenticación
- Decoradores de autorización basada en roles (`require_admin_role`, `require_student_role`)

### 3. Patrón Service

Servicios centralizados instanciados a través de la clase `Services` en [database.py](database/database.py):
```python
class Services:
    - userService: UserService
    - careerService: CareerService
    - testimonyService: TestimonyService
    - newsService: NewsService
    - supabaseService: SupabaseService
    - mercadoPagoController: MercadoPagoController
    - redisService: RedisService
```

---

## Arquitectura de Base de Datos

### Modelo Entidad-Relación

**Entidades Principales:**

#### 1. User (Entidad principal para autenticación y auditoría)
- **Campos:** userId, email, name, lastname, phone, document, rol (admin/student), password (hasheado), confirmed, active
- **Relaciones:**
  - Careers, testimonies, news creados/modificados (audit trail)
- **Enums:** `UserRole` (ADMIN, STUDENT)
- **Ubicación:** [database/models/user.py](database/models/user.py)

#### 2. Career (Ofertas educativas)
- **Campos:** careerId, careerType, area, name, subtitle, aboutCourse1/2, graduateProfile, studyPlan, imageLink
- **Campos Fase 2:** duration, hourlyLoad, cost, startClasses, certificationType
- **Publicación:** published (bool), publicationDate
- **Auditoría:** creator, modifier, creationDate, modificationDate
- **Enums:**
  - `CareerType`: CAREER, COURSE, WORKSHOP, DIPLOMA
  - `Area`: ADMINISTRATION, COMMUNICATION, CULTURE, GENERAL, IT
- **Relaciones:** Tiene muchos testimonies y news
- **Ubicación:** [database/models/career.py](database/models/career.py)

#### 3. Testimony (Testimonios de estudiantes)
- **Campos:** testimonyId, text, name, lastname, career (FK)
- **Auditoría:** creator, modifier, creationDate, modificationDate
- **Relaciones:** Pertenece a una career
- **Ubicación:** [database/models/testimony.py](database/models/testimony.py)

#### 4. News (Noticias institucionales)
- **Campos:** newsId, area, career (FK opcional), title, text, videoLink, imagesLink (array JSON, máx 6)
- **Publicación:** published, publicationDate
- **Auditoría:** creator, modifier, creationDate, modificationDate
- **Relaciones:** Opcionalmente pertenece a una career
- **Ubicación:** [database/models/news.py](database/models/news.py)

### Características de Base de Datos

- **Audit Trail:** Todas las entidades rastrean creator, modifier, fechas de creación/modificación
- **Soft Deletes:** Desactivación de usuarios en lugar de eliminación física
- **Flujo de Publicación:** Flag published separado y fecha de publicación para gestión de contenido
- **Manejo de Timezone:** Zona horaria Uruguay (America/Montevideo) para todas las operaciones de fecha
- **Campos JSON:** News.imagesLink almacenado como array JSON para múltiples imágenes

### Estrategia de Migración

- **Alembic** gestiona cambios de esquema de base de datos
- Auto-generación de migraciones desde cambios de modelo
- Configuración consciente del entorno (desarrollo/producción)
- Historial de migraciones:
  - Migración inicial con todos los modelos
  - Añadido tipo diploma y nuevos campos de carrera (Fase 2)

---

## Diseño de API

### Autenticación y Autorización

#### Autenticación basada en JWT:
- Access tokens con expiración configurable (default: 480 minutos)
- Lista negra de tokens usando Redis para funcionalidad de logout
- JTI (JWT ID) para identificación única de tokens
- Hashing de contraseñas con Bcrypt

**Implementación:** [database/services/auth/security.py](database/services/auth/security.py)

#### Niveles de Autorización:
1. **Pública** - No requiere autenticación
2. **Autenticada** - Cualquier usuario logueado
3. **Estudiante** - Requiere rol de estudiante
4. **Admin** - Requiere rol de admin

**Implementación:** [database/services/auth/dependencies.py](database/services/auth/dependencies.py)

### Estructura de Endpoints de API

#### Autenticación (`/auth`)
**Archivo:** [routes/auth.py](routes/auth.py)

- `POST /create-first-user` - Bootstrap primer admin
- `POST /register` - Registro de usuario
- `POST /login` - Generación de token JWT
- `POST /logout` - Lista negra de tokens
- `GET /me` - Información del usuario actual
- `POST /confirm/{userId}` - Admin confirma usuario
- `POST /activate/{userId}` - Admin activa usuario
- `POST /deactivate/{userId}` - Admin desactiva usuario
- `GET /users` - Lista todos los usuarios (admin)
- `POST /filters` - Filtrado avanzado de usuarios (admin)
- `PUT /users/{userId}` - Actualizar usuario (admin)
- `DELETE /users/{userId}` - Soft delete usuario (admin)

#### Carreras (`/careers`)
**Archivo:** [routes/career.py](routes/career.py)

- `GET /types` - Obtener enum de tipos de carrera (admin)
- `GET /areas` - Obtener enum de áreas (admin)
- `POST /create` - Crear carrera con carga de imagen (admin)
- `GET /careers` - Lista pública de carreras (paginada)
- `GET /admin/careers` - Lista admin de carreras
- `GET /admin/dropdown` - Dropdown de carreras (solo id, nombre)
- `POST /public/filters` - Filtrado avanzado (público, solo publicadas)
- `POST /admin/filters` - Filtrado avanzado (admin, todas)
- `GET /career-optimized/{id}` - Vista optimizada pública de carrera
- `GET /admin/career-optimized/{id}` - Vista optimizada admin de carrera
- `GET /public/random` - Carreras aleatorias (una por área)
- `GET /public/random-for-area` - Carreras aleatorias por áreas específicas
- `PUT /{careerId}` - Actualizar carrera (admin)
- `PUT /image/{careerId}` - Actualizar imagen de carrera (admin)
- `PATCH /{careerId}/publish` - Publicar carrera (admin)
- `PATCH /{careerId}/unpublish` - Despublicar carrera (admin)
- `DELETE /{careerId}` - Eliminar carrera (admin)
- `GET /stats/count` - Estadísticas de carreras (admin)

**Patrones similares para:**
- Testimonios (`/testimonies`) - [routes/testimony.py](routes/testimony.py)
- Noticias (`/news`) - [routes/news.py](routes/news.py)
- Integración Moodle (`/moodle/*`) - [routes/moodle/](routes/moodle/)
- MercadoPago (`/mercadopago/*`) - [routes/mercadopago/mercadopago.py](routes/mercadopago/mercadopago.py)

---

## Sistema de Filtros Avanzados

**Ubicación:** [database/services/filter/filters.py](database/services/filter/filters.py)

### Arquitectura del Sistema de Filtros

El proyecto implementa un sofisticado sistema de filtrado:

#### Componentes Clave:

**1. Filter Model** - Esquema Pydantic para peticiones de filtro:
```python
- conditions: Lista de condiciones de filtro
- logical_operator: AND/OR
- relations: Lista de relaciones a cargar
- fields: Campos específicos a retornar
- limit/offset: Paginación
- order_by/order_direction: Ordenamiento
```

**2. Sistema de Condiciones:**
- Condiciones simples: `{attribute, operator, value}`
- Grupos de condiciones: Grupos lógicos anidados con AND/OR
- Operadores soportados: eq, ne, gt, gte, lt, lte, contains, icontains, startswith, endswith, in, not_in, is_null, is_not_null

**3. QueryBuilder:**
- Construcción dinámica de queries
- Manejo automático de JOINs para relaciones
- Soporte de relaciones anidadas
- Estrategias de eager loading (select, joined, subquery)

**4. Filtrado de Campos:**
- Filtrado de campos post-query
- Filtrado recursivo de campos de relación
- Limpieza de campos null
- Soporte para relaciones anidadas (multi-nivel)

**5. Enhanced Field Filter:**
- Conversión de objetos SQLModel/Pydantic a dict
- Fuerza inclusión de relaciones lazy-loaded de SQLAlchemy
- Maneja prevención de referencias circulares

### Filtrado Público vs Admin:
- `get_with_filters_clean_public()` - Automáticamente añade published=true y restricciones de fecha
- `get_with_filters_clean()` - Sin restricciones para usuarios admin

---

## Arquitectura de Seguridad

### Flujo de Autenticación

**1. Registro de Usuario:**
- Validación de contraseña (mín 8 caracteres, mayúscula, número, carácter especial @.*$)
- Hashing con Bcrypt (auto-salted)
- Verificación de unicidad de email y documento
- Default: no confirmado, inactivo

**2. Login:**
- Autenticación email + contraseña
- Verificación de estado activo y confirmado
- Generación de token JWT con JTI
- Expiración de token configurable

**3. Autorización de Peticiones:**
- Bearer token en header Authorization
- Validación y decodificación JWT
- Verificación de lista negra vía Redis
- Recuperación de usuario y verificación de rol

**4. Logout:**
- Token añadido a lista negra Redis
- TTL basado en expiración del token
- Previene reutilización del token

**Implementación:** [database/services/auth/](database/services/auth/)

### Características de Seguridad

- **Seguridad de Contraseñas:** Bcrypt con salting automático
- **Seguridad de Tokens:** JTI para identificación única, lista negra Redis
- **Control de Acceso Basado en Roles (RBAC):** Roles Admin vs Estudiante
- **Validación de Entrada:** Modelos Pydantic para todas las entradas
- **Prevención de Inyección SQL:** Queries parametrizadas SQLAlchemy
- **CORS:** Configurado (actualmente permite todos los orígenes - debería restringirse en producción)

---

## Integración de Servicios Externos

### 1. Supabase Storage

**Ubicación:** [database/services/supabase/image_service.py](database/services/supabase/image_service.py)

**Propósito:** Almacenamiento de archivos (imágenes, videos)

**Características:**
- Conversión automática a WebP para imágenes (85% calidad, método 6)
- Preservación de formato original como fallback
- Generación de nombres de archivo únicos (UUID)
- Organización basada en carpetas (images/, videos/)
- Validación de tipo de archivo
- Corrección de rotación EXIF
- Capacidad de rollback en errores
- Generación de URL pública

**Flujo de Carga de Imagen:**
1. Recibir UploadFile
2. Validar tipo de archivo
3. Convertir a WebP (si es imagen)
4. Generar nombre único
5. Subir a bucket Supabase
6. Retornar URL pública

### 2. Integración Moodle LMS

**Ubicación:** [external_services/moodle_api/](external_services/moodle_api/)

**Propósito:** Sincronización con Sistema de Gestión de Aprendizaje

**Módulos:**
- Gestión de usuarios (crear, actualizar usuarios)
- Gestión de cursos (crear, actualizar cursos)
- Gestión de categorías
- Gestión de inscripciones (inscribir estudiantes, asignar roles)

**Configuración:**
- Autenticación basada en token
- URL base configurable
- Soporte para métodos de autenticación manual, LDAP, email
- Enums de roles: Student, Teacher, Editing Teacher, Manager

### 3. MercadoPago Payment Gateway

**Ubicación:** [external_services/mercadopago_api/](external_services/mercadopago_api/)

**Propósito:** Procesamiento de pagos y suscripciones

**Características:**
- Creación de preferencias de pago
- Gestión de planes de suscripción
- Handlers de webhook para notificaciones de pago
- Validación segura de webhooks

---

## Configuración y Entorno

### Variables de Entorno

**Base de Datos:**
- `DATABASE_URL` - String de conexión PostgreSQL

**Seguridad:**
- `SECRET_KEY` - Clave de firma JWT
- `ALGORITHM` - Algoritmo JWT (HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Vida del token (default: 480)

**Redis:**
- `REDIS_HOST` - Host servidor Redis
- `REDIS_PORT` - Puerto Redis (default: 6379)
- `REDIS_PASSWORD` - Autenticación Redis

**Supabase:**
- `SUPABASE_URL` - URL del proyecto Supabase
- `SUPABASE_ANON_KEY` - Clave anónima pública
- `SUPABASE_BUCKET_NAME` - Nombre del bucket de almacenamiento

**Moodle:**
- `MOODLE_URL` - URL instancia Moodle
- `MOODLE_TOKEN` - Token de acceso API

**MercadoPago:**
- `MERCADOPAGO_ACESS_TOKEN` - Token de acceso
- `MERCADOPAGO_CLIENT_ID` - ID de cliente
- `MERCADOPAGO_CLIENT_SECRET` - Secret de cliente
- `MERCADOPAGO_PUBLIC_KEY` - Clave pública
- `MERCADOPAGO_WEBHOOK_SECRET_KEY` - Validación webhook

**Aplicación:**
- `PORT` - Puerto del servidor (default: 8000)
- `TIME_ZONE` - Zona horaria (default: America/Montevideo)
- `PRODUCTION` - Flag de producción para logging

**Archivo de referencia:** [.env.example](.env.example)

---

## Decisiones Arquitectónicas Clave

### 1. SQLModel sobre SQLAlchemy puro
**Razón:**
- Combina SQLAlchemy y Pydantic
- Type safety y validación
- Generación automática de esquemas
- Menos código boilerplate

### 2. Redis para Lista Negra de Tokens
**Razón:**
- Búsqueda rápida en memoria
- Expiración automática (TTL)
- Escala mejor que lista negra basada en base de datos
- Separación de responsabilidades de la base de datos principal

### 3. Supabase para Almacenamiento de Archivos
**Razón:**
- Almacenamiento basado en nube, escalable
- No necesita gestionar sistema de archivos
- Generación de URL pública
- Costo-efectivo para archivos multimedia

### 4. Sistema de Filtros Avanzado
**Razón:**
- Flexible, reutilizable en todas las entidades
- Soporta queries complejas sin endpoints personalizados
- Selección a nivel de campo reduce tamaño de payload
- Patrón QueryBuilder para mantenibilidad

### 5. Audit Trail en Todas las Entidades
**Razón:**
- Rastrea quién creó/modificó registros
- Esencial para cumplimiento institucional
- Útil para depuración y rendición de cuentas

### 6. Endpoints Públicos vs Admin
**Razón:**
- Clara separación de responsabilidades
- Endpoints públicos fuerzan estado publicado
- Endpoints admin tienen visibilidad completa
- Estructura de URL hace la intención obvia

### 7. Conversión de Imágenes a WebP
**Razón:**
- Reduce costos de ancho de banda y almacenamiento
- Cargas de página más rápidas
- Soporte de formato moderno
- Fallback automático a formato original

### 8. Manejo de Fechas con Timezone
**Razón:**
- Zona horaria consistente (Uruguay)
- Previene confusión de fechas
- Programación de publicación adecuada

---

## Patrones y Mejores Prácticas Notables

1. **Patrón Service Singleton** - Instancia única de servicios compartida entre peticiones
2. **Inyección de Dependencias** - Depends() de FastAPI para código limpio y testeable
3. **Patrón Repository** - Clases Service abstraen operaciones de base de datos
4. **Patrón DTO** - Modelos separados para operaciones Create, Update, Read
5. **Uso de Enums** - Datos categóricos type-safe (roles, tipos de carrera, áreas)
6. **Context Managers** - Manejo adecuado de sesiones y conexiones
7. **Configuración Basada en Entorno** - Configuraciones desarrollo vs producción
8. **Manejo Completo de Errores** - Excepciones personalizadas con códigos de estado
9. **Logging para Desarrollo** - IceCream (ic) para depuración, deshabilitado en producción
10. **Documentación de API** - UI Scalar con theming personalizado

---

## Despliegue

### Arquitectura de Despliegue en Heroku

**Configuración:**
- `Procfile` configurado para web dyno
- Variables de entorno vía config Heroku
- PostgreSQL vía addon Heroku Postgres
- Redis vía addon Heroku Redis

**Consideraciones de Producción:**
- Servidor ASGI Uvicorn
- Connection pooling (pre-ping, reciclado 1 hora)
- Manejo graceful de startup/shutdown
- Endpoint de health check (`/health`)

**Archivo de configuración:** [Procfile](Procfile)

---

## Áreas de Mejora / Deuda Técnica

Basado en comentarios de código y estructura:

1. **Configuración CORS** - Actualmente permite todos los orígenes (`"*"`)
2. **Eliminación de Carreras** - Nota de bug: testimonios no se eliminan cuando se elimina una carrera
3. **Lifespan Comentado** - Lifespan de inicialización de base de datos está comentado en [main.py](main.py)
4. **Cobertura de Tests** - Endpoints de test existen pero suite completa de tests no es evidente
5. **Documentación** - Documentación de API existe pero docs arquitectónicas podrían expandirse
6. **Manejo de Errores** - Algunos bloques try/except genéricos podrían ser más específicos

---

## Diagrama de Arquitectura Simplificado

```
┌─────────────────────────────────────────────────────────────┐
│                    Cliente (Frontend)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/HTTPS
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI Application (main.py)                │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │    Routes    │  │ Middleware   │  │  Exception   │      │
│  │  (auth, api) │  │   (CORS)     │  │   Handlers   │      │
│  └──────┬───────┘  └──────────────┘  └──────────────┘      │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────────────────────────┐      │
│  │           Services Layer (Singleton)              │      │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐  │      │
│  │  │  User  │ │ Career │ │  News  │ │Testimony │  │      │
│  │  │Service │ │Service │ │Service │ │ Service  │  │      │
│  │  └────┬───┘ └────┬───┘ └────┬───┘ └─────┬────┘  │      │
│  └───────┼──────────┼──────────┼───────────┼───────┘      │
│          │          │          │           │               │
│          ▼          ▼          ▼           ▼               │
│  ┌──────────────────────────────────────────────────┐      │
│  │              SQLModel Models                      │      │
│  │         (User, Career, News, Testimony)           │      │
│  └──────────────────┬───────────────────────────────┘      │
└───────────────────┬─┴────────┬──────────┬───────────┬──────┘
                    │          │          │           │
         ┌──────────▼──┐  ┌───▼────┐  ┌──▼─────┐  ┌─▼────────┐
         │ PostgreSQL  │  │ Redis  │  │Supabase│  │ Moodle   │
         │  Database   │  │ Cache  │  │Storage │  │   API    │
         └─────────────┘  └────────┘  └────────┘  └──────────┘
```

---

## Conclusión

Este proyecto Backend-CTC demuestra una aplicación FastAPI bien diseñada y lista para producción con:

- Clara separación de responsabilidades
- Autenticación robusta basada en JWT
- Sistema de filtros avanzado y flexible
- Integraciones completas de servicios externos
- Arquitectura escalable y mantenible

La arquitectura está optimizada para las necesidades de una institución educativa, proporcionando gestión de contenido, integración LMS, procesamiento de pagos y un sistema robusto de control de acceso.

---

**Última actualización:** 2025-12-28
**Versión:** 1.0
**Autor:** Análisis de arquitectura automatizado
