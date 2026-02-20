# Scheduler - Tareas Programadas

Este documento explica la configuración y uso del sistema de tareas programadas (cron jobs) del backend.

## Configuración

### Variables de Entorno Requeridas

```env
# Entorno de ejecución
ENVIRONMENT=production  # El scheduler SOLO se ejecuta en 'production'

# URL del servidor (debe apuntar al servidor donde corre la aplicación)
BASE_URL=https://backend-backend-ctc-develop.vtu0xl.easypanel.host
```

### ⚠️ IMPORTANTE

El scheduler **solo se ejecuta en entorno de producción** (`ENVIRONMENT=production`). En desarrollo (`ENVIRONMENT=development`) el scheduler está deshabilitado para evitar ejecuciones automáticas no deseadas.

## Tareas Programadas

### 1. Actualización de Fotos de Perfil en Moodle

**Descripción:** Actualiza automáticamente las fotos de perfil de todos los usuarios en Moodle con el logo institucional (CTC).

**Programación:**
- **Día:** Domingos
- **Hora:** 2:00 AM (Hora de Montevideo - America/Montevideo)
- **Frecuencia:** Semanal

**Endpoint ejecutado:**
```
POST {BASE_URL}/api/moodle/usuarios/actualizar-fotos-perfil
```

## Verificar el Estado del Scheduler

Puedes verificar si el scheduler está activo y ver la próxima ejecución programada llamando al endpoint:

```bash
GET /scheduler/status
```

**Respuesta en Producción:**
```json
{
  "status": "running",
  "jobs": [
    {
      "id": "actualizar_fotos_perfil_moodle",
      "name": "Actualizar fotos de perfil en Moodle",
      "next_run": "2026-02-16T02:00:00-03:00",
      "trigger": "cron[day_of_week='sun', hour='2', minute='0']"
    }
  ],
  "timezone": "America/Montevideo"
}
```

**Respuesta en Desarrollo:**
```json
{
  "status": "stopped",
  "message": "El scheduler no está corriendo"
}
```

## Configuración para Producción

### Paso 1: Configurar Variables de Entorno

En tu servidor de producción, asegúrate de tener estas variables:

```env
ENVIRONMENT=production
BASE_URL=https://tu-dominio-de-produccion.com
```

### Paso 2: Reiniciar la Aplicación

El scheduler se inicia automáticamente cuando la aplicación arranca. Verás estos mensajes en los logs:

```
🔄 [STARTUP] Iniciando scheduler de tareas programadas...
✅ Scheduler iniciado correctamente en PRODUCCIÓN
📅 Próxima actualización de fotos: 2026-02-16 02:00:00-03:00
✅ [STARTUP] Scheduler iniciado exitosamente
```

### Paso 3: Verificar

Llama al endpoint `/scheduler/status` para confirmar que el scheduler está activo.

## Ejecución Manual

Si necesitas ejecutar la tarea manualmente (sin esperar al domingo a las 2 AM), puedes llamar directamente al endpoint:

```bash
POST /api/moodle/usuarios/actualizar-fotos-perfil
```

Este endpoint ejecutará el proceso inmediatamente en background, independientemente del entorno.

## Agregar Nuevas Tareas Programadas

Para agregar nuevas tareas al scheduler, edita el archivo `utils/scheduler.py`:

```python
def start_scheduler():
    # ... código existente ...

    # Agregar nueva tarea
    scheduler.add_job(
        mi_nueva_funcion,
        trigger=CronTrigger(
            day_of_week='mon',  # Lunes
            hour=10,            # 10 AM
            minute=30,          # 10:30 AM
            timezone=URUGUAY_TZ
        ),
        id='mi_nueva_tarea',
        name='Nombre descriptivo de la tarea',
        replace_existing=True
    )
```

## Troubleshooting

### El scheduler no se está ejecutando

1. Verifica que `ENVIRONMENT=production` en tus variables de entorno
2. Revisa los logs del startup para ver mensajes de error
3. Llama a `/scheduler/status` para verificar el estado

### La tarea no se ejecutó a la hora programada

1. Verifica la zona horaria del servidor
2. Revisa los logs del servidor en la hora programada
3. Confirma que `BASE_URL` apunta correctamente al servidor

### Error al ejecutar la tarea

Las tareas ejecutadas por el scheduler registran sus errores en los logs del servidor con el prefijo `[CRON]`. Busca estos mensajes en los logs.

## Archivos Relacionados

- `utils/scheduler.py` - Configuración del scheduler y tareas programadas
- `main.py` - Integración del scheduler en el startup/shutdown de la aplicación
- `routes/moodle/moodle_user.py` - Endpoint de actualización de fotos de perfil
- `external_services/moodle_api/scripts/actualizar_fotos_perfil.py` - Script de Playwright
