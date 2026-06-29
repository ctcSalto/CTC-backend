# Fase 5: Sistema de Notificaciones por Email — Plan de Implementacion

**Fecha:** Junio 2026
**Rama:** `develop`
**Canal:** Email via Gmail (webhook n8n). WhatsApp planteado a futuro (misma interfaz, distinta clase).

---

## Contexto

El portal academico v2 no tiene sistema de notificaciones. La infraestructura base existe (webhook n8n para credenciales, APScheduler, patron de servicios singleton), pero no se notifica a estudiantes sobre inscripciones, calificaciones, examenes, ni eventos academicos. Esta fase implementa el envio de emails via n8n, con soporte individual y masivo, y un historial auditable.

---

## Arquitectura (3 capas)

```
[Triggers]                    [Orquestacion]              [Entrega]
  Servicios existentes   -->  NotificationService    -->  EmailService  --> n8n webhook --> Gmail
  Scheduler (cron jobs)       (templates, log, logica)    (futuro: WhatsAppService)
  Admin (endpoints)
```

- **EmailService** — solo entrega: recibe (destinatario, asunto, html) y llama al webhook n8n
- **NotificationService** — orquesta: decide que enviar, renderiza templates con variables, registra en log
- **NotificacionLog** — modelo BD: auditoria de todo lo enviado

---

## Prerequisito: Webhook n8n

El backend asume que existe un workflow generico en n8n que recibe este payload por POST:

```json
{
  "to": "estudiante@ejemplo.com",
  "subject": "Inscripcion confirmada",
  "html_body": "<html>...contenido HTML con estilos inline...</html>"
}
```

El workflow n8n debe:
1. Recibir el POST con autenticacion (header configurable)
2. Tomar los campos `to`, `subject`, `html_body`
3. Enviar el email via Gmail (o el servicio configurado)
4. Retornar 200 si se envio correctamente

**Variable de entorno:** `N8N_EMAIL_WEBHOOK_URL`
**Estado:** Pendiente de crear en n8n. El backend se testea con mocks hasta que el webhook este listo.

---

## Tipos de notificacion (12)

### Automaticas (se disparan desde servicios existentes)

| # | Tipo | Trigger | Servicio que lo dispara |
|---|------|---------|------------------------|
| 1 | Inscripcion a materia confirmada | `inscribir_materia()` exitoso | `inscripcion_service.py` |
| 2 | Inscripcion a examen confirmada | `inscribir_examen()` exitoso | `inscripcion_examen_service.py` |
| 3 | Recordatorio de examen proximo | Scheduler diario 8:00 AM | Job cron (X dias antes) |
| 4 | Apertura periodo inscripcion | Admin abre periodo | Endpoint de periodos |
| 5 | Apertura examen | Admin crea instancia examen | Endpoint de examenes |
| 6 | Cierre inscripcion proximo | Scheduler diario 9:00 AM | Job cron (X dias antes) |
| 7 | Reprobado ultima rendicion | Agotadas oportunidades examen | `inscripcion_examen_service.py` |
| 8 | Baja/abandono procesado | Admin procesa baja programa | `inscripcion_programa_service.py` |

### Semi-automaticas (admin revisa y dispara desde dashboard)

| # | Tipo | Flujo |
|---|------|-------|
| 9 | Calificacion disponible | Profesor sube nota → admin ve pendiente → admin envia |
| 10 | Exoneracion lograda | Igual, admin revisa y envia |

### Manuales (admin escribe o selecciona template)

| # | Tipo | Descripcion |
|---|------|-------------|
| 11 | Envio individual | Admin selecciona estudiante, escribe asunto y mensaje |
| 12 | Envio masivo | Admin filtra grupo (por programa, materia, instancia) y envia a todos |

---

## Archivos nuevos

### `v2/services/email_service.py` — Clase de entrega

```python
class EmailService:
    def send_single(self, destinatario: str, asunto: str, html_body: str) -> dict
    def send_batch(self, destinatarios: list[dict], asunto: str, html_body_template: str) -> dict
```

- POST al webhook n8n con `{to, subject, html_body}`
- `send_batch` itera secuencialmente con `time.sleep(0.1)` entre envios
- Retorna `{"ok": True}` o `{"ok": False, "error": "detalle"}`
- Config: `N8N_EMAIL_WEBHOOK_URL`, `N8N_EMAIL_TIMEOUT`

### `v2/services/notification_service.py` — Orquestador

```python
class NotificationService:
    # Automaticas
    def notificar_inscripcion_materia(inscripcion, usuario, materia, session)
    def notificar_inscripcion_examen(inscripcion_examen, usuario, materia, instancia_examen, session)
    def notificar_recordatorio_examen(session)           # llamado por scheduler
    def notificar_apertura_inscripcion(periodo, programa, session)
    def notificar_apertura_examen(instancia_examen, materia, session)
    def notificar_cierre_inscripcion_proximo(session)    # llamado por scheduler
    def notificar_reprobado_rendiciones(inscripcion, usuario, materia, session)
    def notificar_baja_procesada(inscripcion_programa, usuario, programa, session)

    # Semi-automaticas (admin-triggered)
    def notificar_calificacion(inscripcion_id, admin_id, session)
    def notificar_exoneracion(inscripcion_id, admin_id, session)

    # Manuales
    def enviar_individual(usuario_id, asunto, html_body, admin_id, session)
    def enviar_masivo(filtro: dict, asunto, html_body, admin_id, session) -> dict

    # Consultas
    def get_pendientes_calificacion(session) -> list
    def get_historial(session, page, per_page, tipo?, usuario_id?) -> dict

    # Internos
    def _renderizar_template(template_key, variables) -> str
    def _registrar_log(tipo, usuario_id, email, asunto, ref_id, ref_tipo, estado, error, admin_id, session)
    def _get_email_estudiante(usuario) -> str   # email_personal o email institucional
```

### `v2/models/notificacion.py` — Modelo de log

```python
class NotificacionLog(SQLModel, table=True):
    id: int (PK)
    tipo: TipoNotificacion
    canal: CanalNotificacion (default EMAIL)
    usuario_id: int (FK usuario.id)
    email_destino: str
    asunto: str
    referencia_id: int? (ID de inscripcion/examen/etc)
    referencia_tipo: str? ("inscripcion_materia", "inscripcion_examen", etc)
    estado: EstadoNotificacion (ENVIADA / ERROR)
    error_detalle: str?
    enviado_por_id: int? (FK usuario.id — admin que disparo, null si automatica)
    fecha_envio: datetime
    id_rastreo: str (UUID)
```

### `v2/templates/email_templates.py` — Templates HTML

12 templates como constantes string con placeholders `{nombre}`, `{materia}`, `{nota}`, etc. Todos envueltos en `BASE_TEMPLATE` con branding CTC (header, footer, estilos inline).

Templates:
1. `INSCRIPCION_MATERIA` — confirmacion de inscripcion a materia
2. `INSCRIPCION_EXAMEN` — confirmacion de inscripcion a examen
3. `RECORDATORIO_EXAMEN` — examen en X dias (fecha, hora, salon)
4. `APERTURA_INSCRIPCION` — periodo de inscripcion abierto
5. `APERTURA_EXAMEN` — instancia de examen disponible para inscripcion
6. `CIERRE_INSCRIPCION` — periodo cierra en X dias
7. `CALIFICACION_DISPONIBLE` — nota disponible (materia, nota, estado)
8. `EXONERACION` — felicitaciones, exoneraste la materia
9. `REPROBADO_RENDICIONES` — agotaste las rendiciones, debes recursar
10. `BAJA_PROCESADA` — tu baja del programa fue procesada
11. `MANUAL_INDIVIDUAL` — wrapper para email libre (solo branding)
12. `MANUAL_MASIVO` — wrapper para email masivo (solo branding)

### `v2/routes/admin_notificaciones.py` — Endpoints admin

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/v2/admin/notificaciones/pendientes` | Calificaciones sin notificar |
| POST | `/v2/admin/notificaciones/calificacion/{inscripcion_id}` | Enviar notif de calificacion |
| POST | `/v2/admin/notificaciones/calificacion/batch` | Enviar notif de calificaciones (lista de IDs) |
| POST | `/v2/admin/notificaciones/individual` | Enviar email libre a un estudiante |
| POST | `/v2/admin/notificaciones/masivo` | Enviar email a grupo (filtro por programa/materia) |
| GET | `/v2/admin/notificaciones/historial` | Log paginado de notificaciones enviadas |

### `utils/jobs/notificaciones_jobs.py` — Jobs del scheduler

- `recordatorio_examenes()` — diario 8:00 AM: busca examenes en X dias, envia a inscriptos
- `recordatorio_cierre_inscripcion()` — diario 9:00 AM: busca periodos cerrando en X dias

Ambos usan `get_db_session()` (context manager fuera de request) y verifican en `NotificacionLog` que no se envio duplicado hoy.

---

## Archivos existentes a modificar

| Archivo | Cambio |
|---------|--------|
| `v2/models/enums.py` | +3 enums: `TipoNotificacion`, `CanalNotificacion`, `EstadoNotificacion` |
| `v2/models/__init__.py` | Registrar `NotificacionLog` |
| `v2/models/inscripcion_materia.py` | +campo `notificacion_calificacion_enviada: bool = False` |
| `v2/services/__init__.py` | Registrar `EmailService` y `NotificationService` en `V2Services` |
| `v2/services/inscripcion_service.py` | Hook en `inscribir_materia()`: llamar `notificar_inscripcion_materia()` (best-effort) |
| `v2/services/inscripcion_examen_service.py` | Hook en `inscribir_examen()` y `_reprobar_materia_por_rendiciones()` |
| `utils/scheduler.py` | +2 jobs cron (recordatorio examenes 8AM, cierre inscripcion 9AM) |
| `main.py` | Registrar router `admin_notificaciones` |

---

## Migracion Alembic

Una sola migracion:
1. Crear tabla `notificacion_log`
2. Agregar columna `notificacion_calificacion_enviada` (bool, default false) a `inscripcion_materia`

---

## Decisiones de diseno

1. **Templates en codigo** (no archivos separados) — versionados con el repo, sin I/O en runtime
2. **Pendientes = consulta computada** — inscripciones con estado final + `notificacion_calificacion_enviada == false`
3. **Un solo webhook generico en n8n** — recibe `{to, subject, html_body}`, toda diferenciacion en el HTML
4. **Batch = loop secuencial** con `sleep(0.1)` — per-recipient status logging, no sobrecarga n8n
5. **Notificaciones nunca son criticas** — todo hook automatico va en try/except, un fallo de email nunca bloquea una operacion de negocio
6. **Email destino**: `email_personal` si existe, sino `email` institucional
7. **Prevencion de duplicados** en scheduler: consulta `NotificacionLog` antes de enviar (mismo tipo + usuario + referencia + dia)

---

## Variables de entorno nuevas

```bash
N8N_EMAIL_WEBHOOK_URL=          # webhook generico de envio de email en n8n
N8N_EMAIL_TIMEOUT=30            # timeout en segundos
NOTIF_EXAM_REMINDER_DAYS=3      # dias antes del examen para recordatorio
NOTIF_ENROLLMENT_CLOSING_DAYS=2 # dias antes del cierre para recordatorio
```

---

## Secuencia de implementacion

1. Enums + modelo NotificacionLog + campo en InscripcionMateria + migracion
2. EmailService (delivery puro, testeable aislado)
3. Templates HTML (12 templates)
4. NotificationService (orquestacion, usa EmailService)
5. Endpoints admin (admin_notificaciones.py)
6. Hooks automaticos en servicios existentes
7. Jobs del scheduler
8. Tests

---

## Verificacion

- Test unitario: EmailService con mock del webhook
- Test unitario: NotificationService renderiza templates correctamente
- Test de integracion: crear inscripcion y verificar que se registra NotificacionLog
- Test manual: enviar email real via webhook n8n y verificar recepcion en Gmail
- Verificar que operaciones de negocio no fallan si el webhook esta caido
- Verificar que scheduler no envia duplicados en ejecuciones consecutivas

---

*Plan generado: Junio 2026 — CTC Salto*
