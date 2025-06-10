Librerias a instalar con pip:

1. sqlmodel
2. fastapi
3. uvicorn
4. python-dotenv

Detalle de la aplicación:

Desde el archivo main.py se ejecuta el servidor fastapi con el comando:

-> python main.py
Al ejecutar la aplicación se creara la base de datos y las tablas con la función create_db_and_tables() importada de database.database.py

Arquitectura de la aplicación:

1. main.py: archivo principal que ejecuta el servidor fastapi
2. routes/: carpeta que contiene las rutas de la aplicación
3. database/models/: carpeta que contiene los modelos de la base de datos
4. database/services/: carpeta que contiene los servicios de la base de datos
5. database/database.py: archivo que contiene la configuración de la base de datos y las tablas