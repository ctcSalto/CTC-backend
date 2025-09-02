# Backend CTC

Backend para el instituto CTC de Salto construido con FastAPI.

## Descripción

Sistema backend para la gestión integral del Instituto CTC (Centro de Tecnologías de la Comunicación) de Salto, Uruguay. Proporciona APIs para la administración de carreras, testimonios, noticias, usuarios y integración con sistemas externos como Moodle y MercadoPago.

## Características Principales

- **API REST** con FastAPI
- **Autenticación JWT** con roles de usuario (admin/student)
- **Base de datos** PostgreSQL con SQLModel/SQLAlchemy
- **Cache** con Redis
- **Almacenamiento de imágenes** con Supabase
- **Integración con Moodle** para gestión académica
- **Integración con MercadoPago** para pagos y suscripciones
- **Migraciones** con Alembic
- **Validaciones** robustas con Pydantic

## Módulos

### Gestión de Carreras
- CRUD completo de carreras educativas
- Soporte para carreras, cursos y talleres
- Categorización por áreas (administración, comunicación, cultura, general, IT)
- Control de publicación y fechas

### Gestión de Usuarios
- Sistema de autenticación con JWT
- Roles diferenciados (admin/student)
- Validación de contraseñas seguras
- Gestión de perfiles y accesos

### Testimonios y Noticias
- Sistema de testimonios de estudiantes
- Gestión de noticias institucionales
- Relación con carreras específicas

### Integraciones Externas
- **Moodle API**: Sincronización de usuarios, cursos, categorías y inscripciones
- **MercadoPago**: Procesamiento de pagos y gestión de suscripciones
- **Supabase**: Almacenamiento y gestión de imágenes

## Tecnologías

- **FastAPI** - Framework web moderno y rápido
- **SQLModel** - ORM basado en SQLAlchemy y Pydantic
- **PostgreSQL** - Base de datos principal
- **Redis** - Sistema de cache
- **Alembic** - Migraciones de base de datos
- **JWT** - Autenticación y autorización
- **Supabase** - Backend como servicio para storage
- **Uvicorn** - Servidor ASGI

## Instalación

1. Clonar el repositorio
2. Crear entorno virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```
3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Configurar variables de entorno:
   ```bash
   cp .env.example .env
   # Editar .env con tus configuraciones
   ```

## Configuración

Configurar las siguientes variables en `.env`:

- `DATABASE_URL` - URL de conexión a PostgreSQL
- `SECRET_KEY` - Clave secreta para JWT
- `SUPABASE_URL` y `SUPABASE_ANON_KEY` - Configuración de Supabase
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` - Configuración de Redis
- `MOODLE_URL` y `MOODLE_TOKEN` - Integración con Moodle
- `MERCADOPAGO_*` - Claves de MercadoPago

## Ejecución

### Desarrollo
```bash
python main.py
```

### Producción
```bash
uvicorn main:app --host=0.0.0.0 --port=8000
```

## Estructura del Proyecto

```
├── database/
│   ├── models/          # Modelos SQLModel
│   ├── services/        # Lógica de negocio
│   └── database.py      # Configuración de DB
├── routes/              # Endpoints de la API
├── external_services/   # Integraciones externas
├── exceptions/          # Manejo de excepciones
├── utils/              # Utilidades
├── alembic/            # Migraciones
└── main.py             # Punto de entrada
```

## API Endpoints

- `/auth` - Autenticación y gestión de usuarios
- `/careers` - Gestión de carreras educativas
- `/testimonies` - Testimonios de estudiantes
- `/news` - Noticias institucionales
- `/moodle` - Integración con Moodle
- `/mercadopago` - Procesamiento de pagos

## Desarrollo

El proyecto utiliza migraciones con Alembic para cambios en la base de datos:

```bash
# Crear migración
alembic revision --autogenerate -m "descripción"

# Aplicar migraciones
alembic upgrade head
```

## Despliegue

Configurado para despliegue en Heroku con `Procfile` incluido.