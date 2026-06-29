# Roadmap de Testing - Endpoints Portal Estudiante y Docente

Guia para testear manualmente los endpoints agregados en la rama `bedelia`.
Todos requieren autenticacion JWT v2. Usar Swagger (`/docs`) o herramientas como Postman/Insomnia.

**Base URL:** `http://localhost:8000`

**Header requerido en todos:**
```
Authorization: Bearer <token_jwt>
```

---

## Prerequisitos

1. Tener al menos 1 usuario con rol `ESTUDIANTE` y 1 con rol `DOCENTE` en tabla `usuario`
2. Tener al menos 1 `programa` con `materias` asociadas
3. Tener al menos 1 `instancia_cursado` activa
4. Tener el alumno inscripto en un programa (`inscripcion_programa`) y en al menos 1 materia (`inscripcion_materia`)
5. Tener al menos 1 `docente_materia` asignando un docente a una instancia de cursado
6. (Opcional) Tener `instancias_evaluacion` y `instancias_examen` creadas

---

## PORTAL ESTUDIANTE (`/v2/portal/estudiante`)

Auth: token de usuario con rol `ESTUDIANTE`

### 1. GET /mi-perfil

**Request:** Sin body ni params
```
GET /v2/portal/estudiante/mi-perfil
```

**Resultado esperado:**
```json
{
  "id": 1,
  "nombre": "Juan",
  "apellido": "Perez",
  "email": "juan@ctcsalto.edu.uy",
  "rol": "ESTUDIANTE",
  "perfil_alumno": {
    "alumno_id": 1,
    "fecha_ingreso": "2025-03-01"
  }
}
```
- `perfil_alumno` puede ser `null` si no existe registro en tabla `alumno`

---

### 2. GET /mis-programas

**Request:** Sin body ni params
```
GET /v2/portal/estudiante/mis-programas
```

**Resultado esperado:**
```json
[
  {
    "inscripcion_id": 1,
    "programa_id": 5,
    "nombre": "Analista Programador",
    "tipo": "CARRERA",
    "area": "IT",
    "estado": "ACTIVA",
    "anio_ingreso": 2025,
    "fecha_inscripcion": "2025-03-01T00:00:00"
  }
]
```
- Array vacio `[]` si no hay inscripciones a programas
- Verificar que solo muestra programas del alumno autenticado

---

### 3. GET /programa/{programa_id}

**Request:**
```
GET /v2/portal/estudiante/programa/5
```

**Resultado esperado:**
- Objeto con info del programa + lista de materias
- **403** si el alumno NO esta inscripto en ese programa (estado ACTIVA)
- **404** si el programa no existe

**Verificar:**
- Que no devuelve programas donde el alumno no esta inscripto
- Que incluye la lista de materias con nombre, codigo, semestre, creditos

---

### 4. GET /programa/{programa_id}/previaturas

**Request:**
```
GET /v2/portal/estudiante/programa/5/previaturas
```

**Resultado esperado:**
```json
[
  {
    "materia_id": 10,
    "nombre": "Programacion 2",
    "codigo": "P2",
    "semestre": 2,
    "previaturas": [
      {
        "materia_previa_id": 9,
        "nombre": "Programacion 1",
        "tipo_requerido": "APROBADA"
      }
    ],
    "estado_alumno": "pendiente"
  }
]
```
- `estado_alumno` puede ser: `aprobada`, `exonerada`, `cursando`, `a_examen`, `reprobada`, `pendiente`
- El Integrador deberia listar TODAS las materias del programa como previaturas

---

### 5. GET /mis-materias?anio_lectivo=2026

**Request:**
```
GET /v2/portal/estudiante/mis-materias?anio_lectivo=2026
```

**Resultado esperado:**
```json
[
  {
    "inscripcion_id": 1,
    "instancia_cursado_id": 3,
    "materia_nombre": "Programacion 1",
    "materia_codigo": "P1",
    "semestre": 1,
    "estado": "CURSANDO",
    "nota_curso": null,
    "faltas": 2,
    "faltas_maximas": 15
  }
]
```
- `anio_lectivo` es query param obligatorio
- Solo muestra materias donde el alumno tiene inscripcion activa (CURSANDO, A_EXAMEN, etc.)
- `faltas_maximas` viene de la instancia de cursado

---

### 6. GET /mi-materia/{inscripcion_id}

**Request:**
```
GET /v2/portal/estudiante/mi-materia/1
```

**Resultado esperado:**
```json
{
  "inscripcion_id": 1,
  "materia_nombre": "Programacion 1",
  "materia_codigo": "P1",
  "semestre": 1,
  "creditos": 10,
  "estado": "CURSANDO",
  "nota_curso": null,
  "nota_final": null,
  "faltas": 2,
  "faltas_maximas": 15,
  "calificaciones": [
    {
      "instancia_evaluacion_id": 1,
      "nombre": "Parcial 1",
      "nota": 8.5,
      "peso_maximo": 30.0
    }
  ]
}
```
- **403** si la inscripcion no pertenece al usuario autenticado
- **400** si inscripcion_id no existe
- Incluye calificaciones desglosadas por evaluacion

---

### 7. GET /mi-escolaridad?programa_id=5

**Request:**
```
GET /v2/portal/estudiante/mi-escolaridad?programa_id=5
```

**Resultado esperado:** Historial academico completo del alumno en ese programa (materias cursadas, notas, estados)

---

### 8. GET /materias-disponibles?programa_id=5&anio_lectivo=2026

**Request:**
```
GET /v2/portal/estudiante/materias-disponibles?programa_id=5&anio_lectivo=2026
```

**Resultado esperado:** Lista de materias a las que el alumno puede inscribirse (previaturas cumplidas, periodo activo, no ya inscripto)

---

### 9. POST /inscribirse-materia

**Request:**
```
POST /v2/portal/estudiante/inscribirse-materia
Content-Type: application/json

{
  "instancia_cursado_id": 3
}
```

**Resultado esperado:**
- **200** con `InscripcionMateriaRead` (la inscripcion creada)
- **400** si no cumple previaturas
- **400** si no hay periodo de inscripcion activo
- **400** si ya esta inscripto
- **400** si cupo lleno

---

### 10. GET /mis-calificaciones/{inscripcion_id}

**Request:**
```
GET /v2/portal/estudiante/mis-calificaciones/1
```

**Resultado esperado:**
```json
[
  {
    "id": 1,
    "inscripcion_id": 1,
    "instancia_evaluacion_id": 1,
    "nota": 8.5,
    "docente_id": 2,
    "fecha_calificacion": "2026-04-15T10:30:00"
  }
]
```
- **403** si no es su inscripcion
- **404** si inscripcion no existe

---

### 11. POST /inscribirse-examen

**Request:**
```
POST /v2/portal/estudiante/inscribirse-examen
Content-Type: application/json

{
  "inscripcion_materia_id": 1,
  "instancia_examen_id": 5
}
```

**Resultado esperado:**
- **201** con `InscripcionExamenRead`
- **403** si la inscripcion no es del usuario
- **404** si inscripcion_materia no existe
- **400** si no esta en estado A_EXAMEN, periodo cerrado, etc.

---

### 12. GET /mis-examenes/{inscripcion_id}

**Request:**
```
GET /v2/portal/estudiante/mis-examenes/1
```

**Resultado esperado:** Array de `InscripcionExamenRead` con historial de examenes de esa materia
- **403** si no es su inscripcion

---

### 13. DELETE /desinscribir-examen/{inscripcion_examen_id}

**Request:**
```
DELETE /v2/portal/estudiante/desinscribir-examen/3
```

**Resultado esperado:**
- **204** No Content (exito)
- **400** si no esta en estado INSCRIPTO
- **403** si no es su inscripcion
- **404** si no existe

---

### 14. DELETE /desinscribir-materia/{inscripcion_id}

**Request:**
```
DELETE /v2/portal/estudiante/desinscribir-materia/1
```

**Resultado esperado:**
- **204** No Content (exito)
- **400** si no esta en estado CURSANDO o fuera de periodo
- **400** si inscripcion no es del usuario

---

### 15. GET /examenes-disponibles?programa_id=5

**Request:**
```
GET /v2/portal/estudiante/examenes-disponibles?programa_id=5
```

**Resultado esperado:**
```json
[
  {
    "instancia_examen_id": 5,
    "inscripcion_materia_id": 1,
    "materia_id": 10,
    "materia_nombre": "Programacion 1",
    "materia_codigo": "P1",
    "nombre_examen": "Examen Julio 2026",
    "fecha_examen": "2026-07-15",
    "hora": "09:00",
    "salon": "Salon A",
    "modalidad": "PRESENCIAL",
    "tipo": "REGULAR",
    "ya_inscripto": false
  }
]
```
- Solo muestra examenes de materias donde el alumno esta en estado `A_EXAMEN`
- Solo muestra examenes con inscripcion abierta (entre fecha_inicio_inscripcion y fecha_fin_inscripcion)
- `ya_inscripto` indica si el alumno ya se inscribio a ese examen

---

### 16. GET /todos-mis-examenes

**Request:**
```
GET /v2/portal/estudiante/todos-mis-examenes
```

**Resultado esperado:** Array con todos los examenes del alumno en todas las materias, ordenados por fecha descendente
```json
[
  {
    "inscripcion_examen_id": 3,
    "inscripcion_materia_id": 1,
    "materia_nombre": "Programacion 1",
    "materia_codigo": "P1",
    "nombre_examen": "Examen Julio 2026",
    "fecha_examen": "2026-07-15",
    "estado": "INSCRIPTO",
    "nota_examen": null
  }
]
```

---

### 17. GET /mi-egreso?programa_id=5

**Request:**
```
GET /v2/portal/estudiante/mi-egreso?programa_id=5
```

**Resultado esperado:** Progreso de egreso del alumno en el programa (materias aprobadas, pendientes, porcentaje completado)

---

## PORTAL DOCENTE (`/v2/portal/docente`)

Auth: token de usuario con rol `DOCENTE` o `ADMINISTRATIVO`

### 1. GET /mi-perfil

**Request:**
```
GET /v2/portal/docente/mi-perfil
```

**Resultado esperado:**
```json
{
  "id": 2,
  "nombre": "Maria",
  "apellido": "Garcia",
  "email": "maria@ctcsalto.edu.uy",
  "rol": "DOCENTE",
  "perfil_profesor": {
    "profesor_id": 1,
    "cargo": "TITULAR",
    "dedicacion": "TIEMPO_COMPLETO",
    "especialidad": "Programacion"
  }
}
```
- `perfil_profesor` puede ser `null` si no existe registro en tabla `profesor`

---

### 2. GET /mis-programas

**Request:**
```
GET /v2/portal/docente/mis-programas
```

**Resultado esperado:**
```json
[
  {
    "programa_id": 5,
    "nombre": "Analista Programador",
    "tipo": "CARRERA",
    "area": "IT",
    "cantidad_materias": 15
  }
]
```
- Solo programas donde el profesor es `coordinador_id`
- Array vacio si no coordina ningun programa

---

### 3. GET /mis-materias?anio_lectivo=2026

**Request:**
```
GET /v2/portal/docente/mis-materias?anio_lectivo=2026
```

**Resultado esperado:**
```json
[
  {
    "asignacion_id": 1,
    "instancia_cursado_id": 3,
    "materia_id": 10,
    "nombre": "Programacion 1",
    "codigo": "P1",
    "semestre": 1,
    "anio_lectivo": 2026,
    "salon": "Lab 1",
    "horario": "Lunes 18:00-20:00",
    "estado": "EN_CURSO",
    "rol_docente": "TITULAR"
  }
]
```
- Solo materias asignadas via `docente_materia`
- `anio_lectivo` es query param obligatorio

---

### 4. GET /instancia-cursado/{id}/alumnos

**Request:**
```
GET /v2/portal/docente/instancia-cursado/3/alumnos
```

**Resultado esperado:**
```json
[
  {
    "inscripcion_id": 1,
    "usuario_id": 5,
    "nombre": "Juan",
    "apellido": "Perez",
    "estado": "CURSANDO",
    "nota_curso": null
  }
]
```
- **403** si el docente no esta asignado a esa instancia (excepto ADMINISTRATIVO)

---

### 5. GET /instancia-cursado/{id}/detalle

**Request:**
```
GET /v2/portal/docente/instancia-cursado/3/detalle
```

**Resultado esperado:**
```json
{
  "instancia_cursado_id": 3,
  "materia_id": 10,
  "materia_nombre": "Programacion 1",
  "materia_codigo": "P1",
  "anio_lectivo": 2026,
  "salon": "Lab 1",
  "horario": "Lunes 18:00-20:00",
  "fecha_inicio": "2026-03-01",
  "fecha_fin": "2026-11-30",
  "estado": "EN_CURSO",
  "cupo_maximo": 30,
  "faltas_maximas": 15,
  "total_inscriptos": 25,
  "evaluaciones": [
    {
      "id": 1,
      "nombre": "Parcial 1",
      "peso_maximo": 30.0,
      "orden": 1,
      "es_grupal": false,
      "activo": true
    }
  ]
}
```
- **403** si no esta asignado (excepto ADMINISTRATIVO)

---

### 6. GET /instancia-cursado/{id}/resultados

**Request:**
```
GET /v2/portal/docente/instancia-cursado/3/resultados
```

**Resultado esperado:**
```json
{
  "instancia_cursado_id": 3,
  "materia_nombre": "Programacion 1",
  "materia_codigo": "P1",
  "anio_lectivo": 2026,
  "estado": "EN_CURSO",
  "evaluaciones": [
    {"id": 1, "nombre": "Parcial 1", "orden": 1}
  ],
  "alumnos": [
    {
      "inscripcion_id": 1,
      "usuario_id": 5,
      "nombre": "Juan",
      "apellido": "Perez",
      "estado": "CURSANDO",
      "nota_curso": null,
      "nota_final": null,
      "faltas": 2,
      "notas_evaluaciones": [
        {"instancia_evaluacion_id": 1, "nombre": "Parcial 1", "nota": 8.5}
      ]
    }
  ]
}
```
- Tabla completa para que el frontend renderice el acta

---

### 7. GET /instancia-cursado/{id}/estadisticas

**Request:**
```
GET /v2/portal/docente/instancia-cursado/3/estadisticas
```

**Resultado esperado:**
```json
{
  "total_inscriptos": 25,
  "por_estado": {
    "CURSANDO": 20,
    "APROBADO": 3,
    "REPROBADO": 1,
    "PERDIDO_INASISTENCIA": 1
  },
  "promedio_notas": 7.5,
  "tasa_aprobacion": 12.0,
  "tasa_asistencia": 85.5
}
```
- `tasa_asistencia` es `null` si `faltas_maximas` no esta configurado

---

### 8. GET /instancia-cursado/{id}/calificaciones?instancia_evaluacion_id=1

**Request:**
```
GET /v2/portal/docente/instancia-cursado/3/calificaciones?instancia_evaluacion_id=1
```

**Resultado esperado:** Array con las notas de todos los alumnos en esa evaluacion especifica

---

### 9. POST /instancia-cursado/{id}/calificaciones

**Request:**
```
POST /v2/portal/docente/instancia-cursado/3/calificaciones
Content-Type: application/json

{
  "inscripcion_id": 1,
  "instancia_evaluacion_id": 1,
  "nota": 8.5,
  "equipo_id": null,
  "observaciones": "Buen trabajo"
}
```

**Resultado esperado:** `CalificacionRead` con la calificacion creada/actualizada
- **400** si inscripcion_id o instancia_evaluacion_id no existen

---

### 10. POST /instancia-cursado/{id}/calificaciones/batch

**Request:**
```
POST /v2/portal/docente/instancia-cursado/3/calificaciones/batch
Content-Type: application/json

{
  "instancia_evaluacion_id": 1,
  "calificaciones": [
    {"inscripcion_id": 1, "nota": 8.5},
    {"inscripcion_id": 2, "nota": 7.0},
    {"inscripcion_id": 3, "nota": 9.0}
  ]
}
```

**Resultado esperado:** Objeto con `creadas`, `actualizadas`, `errores`

---

### 11. POST /instancia-cursado/{id}/nota-final-directa

**Request:**
```
POST /v2/portal/docente/instancia-cursado/3/nota-final-directa
Content-Type: application/json

{
  "inscripcion_id": 1,
  "nota": 8.0
}
```

**Resultado esperado:** `InscripcionMateriaRead` con `nota_final` y estado actualizado

---

### 12. GET /instancia-cursado/{id}/equipos?instancia_evaluacion_id=2

**Request:**
```
GET /v2/portal/docente/instancia-cursado/3/equipos?instancia_evaluacion_id=2
```

**Resultado esperado:** Array de equipos con miembros para esa evaluacion grupal

---

### 13. POST /instancia-cursado/{id}/equipos

**Request:**
```
POST /v2/portal/docente/instancia-cursado/3/equipos
Content-Type: application/json

{
  "instancia_evaluacion_id": 2,
  "nombre": "Equipo Alpha",
  "miembros_ids": [1, 2, 3]
}
```

**Resultado esperado:**
```json
{
  "id": 1,
  "nombre": "Equipo Alpha",
  "instancia_evaluacion_id": 2
}
```

---

### 14. DELETE /instancia-cursado/{id}/equipos/{equipo_id}

**Request:**
```
DELETE /v2/portal/docente/instancia-cursado/3/equipos/1
```

**Resultado esperado:** **204** No Content

---

### 15. POST /instancia-cursado/{id}/faltas

**Request:**
```
POST /v2/portal/docente/instancia-cursado/3/faltas
Content-Type: application/json

{
  "inscripcion_id": 1
}
```

**Resultado esperado:** `InscripcionMateriaRead` con `faltas` incrementado en 1
- Si `faltas >= faltas_maximas`, el estado cambia automaticamente a `PERDIDO_INASISTENCIA`
- **403** si no esta asignado a la instancia

**Test importante:** Repetir hasta alcanzar `faltas_maximas` y verificar cambio de estado automatico

---

### 16. DELETE /instancia-cursado/{id}/faltas

**Request:**
```
DELETE /v2/portal/docente/instancia-cursado/3/faltas
Content-Type: application/json

{
  "inscripcion_id": 1
}
```

**Resultado esperado:** `InscripcionMateriaRead` con `faltas` decrementado en 1 (minimo 0)

---

### 17. GET /materia/{materia_id}/examenes?instancia_examen_id=5

**Request:**
```
GET /v2/portal/docente/materia/10/examenes?instancia_examen_id=5
```

**Resultado esperado:** Lista de alumnos inscriptos a ese examen con estado y nota

---

### 18. POST /materia/{materia_id}/examenes/{inscripcion_examen_id}/calificar

**Request:**
```
POST /v2/portal/docente/materia/10/examenes/3/calificar
Content-Type: application/json

{
  "nota_examen": 7.5
}
```

**Resultado esperado:** `InscripcionExamenRead` con nota y estado actualizado

---

### 19. POST /materia/{materia_id}/examenes/{inscripcion_examen_id}/ausente

**Request:**
```
POST /v2/portal/docente/materia/10/examenes/3/ausente
```

**Resultado esperado:** `InscripcionExamenRead` con estado `AUSENTE`

---

## Orden sugerido de testing

### Dia 1: Flujo basico

1. **Docente mi-perfil** — verificar que devuelve datos del perfil profesor
2. **Estudiante mi-perfil** — verificar que devuelve datos del perfil alumno
3. **Estudiante mis-programas** — verificar programas inscriptos
4. **Estudiante programa/{id}** — ver info del programa con materias
5. **Estudiante programa/{id}/previaturas** — verificar mapa de previaturas
6. **Docente mis-programas** — verificar programas donde es coordinador
7. **Docente mis-materias** — verificar materias asignadas

### Dia 2: Cursado y calificaciones

8. **Estudiante materias-disponibles** — ver materias disponibles para inscripcion
9. **Estudiante inscribirse-materia** — inscribirse a una materia
10. **Estudiante mis-materias** — verificar que aparece la nueva inscripcion
11. **Estudiante mi-materia/{id}** — ver detalle de la inscripcion
12. **Docente alumnos** — ver que aparece el alumno inscripto
13. **Docente detalle** — ver detalle de instancia de cursado
14. **Docente calificaciones POST** — cargar una nota
15. **Docente calificaciones/batch** — carga masiva
16. **Estudiante mis-calificaciones** — verificar que el alumno ve sus notas
17. **Docente resultados** — ver tabla completa de resultados
18. **Docente estadisticas** — verificar calculo de estadisticas

### Dia 3: Faltas y examenes

19. **Docente faltas POST** — registrar faltas, verificar incremento
20. **Docente faltas DELETE** — quitar falta, verificar decremento
21. **Docente faltas POST x N** — llevar a faltas_maximas, verificar PERDIDO_INASISTENCIA
22. **Estudiante examenes-disponibles** — ver examenes abiertos
23. **Estudiante inscribirse-examen** — inscribirse a examen
24. **Estudiante mis-examenes** — ver examenes de una materia
25. **Estudiante todos-mis-examenes** — ver todos los examenes
26. **Docente examenes GET** — ver inscriptos a examen
27. **Docente calificar examen** — poner nota de examen
28. **Docente marcar ausente** — marcar ausente en examen
29. **Estudiante desinscribir-examen** — desinscribirse de examen
30. **Estudiante desinscribir-materia** — desinscribirse de materia
31. **Estudiante mi-egreso** — verificar progreso de egreso
32. **Estudiante mi-escolaridad** — ver escolaridad completa

---

## Casos de error a verificar

| Test | Endpoint | Que probar | Resultado esperado |
|------|----------|------------|-------------------|
| Auth | Cualquiera | Sin token JWT | 401 Unauthorized |
| Auth | Portal estudiante | Token de docente | 403 Forbidden |
| Auth | Portal docente | Token de estudiante | 403 Forbidden |
| Propiedad | mi-materia/{id} | Inscripcion de otro alumno | 403 |
| Propiedad | mis-calificaciones/{id} | Inscripcion de otro alumno | 403 |
| Asignacion | Docente endpoints | Instancia no asignada al docente | 403 |
| Existencia | programa/{id} | Programa inexistente | 404 |
| Negocio | inscribirse-materia | Sin previaturas cumplidas | 400 |
| Negocio | inscribirse-materia | Fuera de periodo | 400 |
| Negocio | desinscribir-materia | Estado != CURSANDO | 400 |
| Negocio | desinscribir-examen | Estado != INSCRIPTO | 400 |
| Negocio | faltas | Mas alla de faltas_maximas | Auto-PERDIDO_INASISTENCIA |
