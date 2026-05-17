"""
Test Fase 3 — CRUD Administrativo (v2 refactored)
Prueba el flujo completo: politicas -> programas -> materias -> instancias_cursado ->
previaturas -> instancias_evaluacion -> docentes
"""
import requests
import sys

BASE = "http://localhost:8000"

from v2.auth.security import create_v2_token
TOKEN = create_v2_token(
    email="admin@ctcsalto.edu.uy",
    usuario_id=1,
    rol="administrativo",
)
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

from database.database import get_db_session
from v2.models.usuario import Usuario
from v2.models.enums import RolUsuario


def setup_admin_user():
    """Crear usuario admin de prueba si no existe"""
    global TOKEN, HEADERS
    with get_db_session() as session:
        from sqlmodel import select
        existing = session.exec(
            select(Usuario).where(Usuario.email == "admin@ctcsalto.edu.uy")
        ).first()
        if not existing:
            admin = Usuario(
                email="admin@ctcsalto.edu.uy",
                nombre="Admin",
                apellido="Test",
                rol=RolUsuario.ADMINISTRATIVO,
                activo=True,
            )
            session.add(admin)
            session.commit()
            session.refresh(admin)
            print(f"[OK] Usuario admin creado con id={admin.id}")
            usuario_id = admin.id
        else:
            print(f"[OK] Usuario admin ya existe con id={existing.id}")
            usuario_id = existing.id

        TOKEN = create_v2_token(
            email="admin@ctcsalto.edu.uy",
            usuario_id=usuario_id,
            rol="administrativo",
        )
        HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def setup_docente_user():
    """Crear usuario docente de prueba si no existe"""
    with get_db_session() as session:
        from sqlmodel import select
        existing = session.exec(
            select(Usuario).where(Usuario.email == "docente@ctcsalto.edu.uy")
        ).first()
        if not existing:
            docente = Usuario(
                email="docente@ctcsalto.edu.uy",
                nombre="Docente",
                apellido="Test",
                rol=RolUsuario.DOCENTE,
                activo=True,
            )
            session.add(docente)
            session.commit()
            session.refresh(docente)
            print(f"[OK] Usuario docente creado con id={docente.id}")
            return docente.id
        else:
            print(f"[OK] Usuario docente ya existe con id={existing.id}")
            return existing.id


passed = 0
failed = 0


def test(name, response, expected_status=200):
    global passed, failed
    if response.status_code == expected_status:
        passed += 1
        print(f"  [PASS] {name} ({response.status_code})")
        return True
    else:
        failed += 1
        detail = ""
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:200]
        print(f"  [FAIL] {name} — esperado {expected_status}, obtuvo {response.status_code}: {detail}")
        return False


def main():
    global passed, failed

    print("\n=== FASE 3: TEST CRUD ADMINISTRATIVO (v2 refactored) ===\n")

    # Setup
    setup_admin_user()
    docente_id = setup_docente_user()

    # ── 1. Politica de Calificacion ──
    print("\n--- Politicas de Calificacion ---")

    r = requests.post(f"{BASE}/v2/admin/politicas-calificacion", json={
        "nombre": "Base 100 - Carrera AP",
        "nota_maxima": 100,
        "tipo_nota": "numerica",
        "umbral_aprobacion": 70,
        "umbral_examen": 70,
        "umbral_exoneracion": 86,
    }, headers=HEADERS)
    test("Crear politica calificacion (carrera)", r, 201)
    politica_carrera_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.post(f"{BASE}/v2/admin/politicas-calificacion", json={
        "nombre": "Base 100 - Curso Corto",
        "nota_maxima": 100,
        "tipo_nota": "numerica",
        "umbral_aprobacion": 70,
    }, headers=HEADERS)
    test("Crear politica calificacion (curso corto)", r, 201)

    r = requests.get(f"{BASE}/v2/admin/politicas-calificacion/{politica_carrera_id}", headers=HEADERS)
    test("Obtener politica por ID", r)
    if r.status_code == 200 and r.json().get("id_rastreo"):
        passed += 1
        print(f"  [PASS] Politica tiene id_rastreo")

    r = requests.get(f"{BASE}/v2/admin/politicas-calificacion", headers=HEADERS)
    test("Listar politicas", r)
    assert len(r.json()) >= 2, "Deberian haber al menos 2 politicas"

    r = requests.put(f"{BASE}/v2/admin/politicas-calificacion/{politica_carrera_id}", json={
        "descripcion": "Politica estandar para carreras"
    }, headers=HEADERS)
    test("Actualizar politica", r)

    r = requests.post(f"{BASE}/v2/admin/politicas-calificacion/filters", json={
        "conditions": [{"attribute": "nombre", "operator": "icontains", "value": "carrera"}],
        "limit": 10
    }, headers=HEADERS)
    test("Filtrar politicas", r)

    # ── 2. Politica de Examen ──
    print("\n--- Politicas de Examen ---")

    r = requests.post(f"{BASE}/v2/admin/politicas-examen", json={
        "nombre": "Examen estandar base 100",
        "nota_maxima": 100,
        "umbral_aprobacion": 70,
    }, headers=HEADERS)
    test("Crear politica examen", r, 201)
    politica_examen_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.get(f"{BASE}/v2/admin/politicas-examen", headers=HEADERS)
    test("Listar politicas examen", r)

    # ── 3. Programas ──
    print("\n--- Programas ---")

    r = requests.post(f"{BASE}/v2/admin/programas", json={
        "nombre": "Analista Programador",
        "tipo": "carrera",
        "duracion_semestres": 6,
    }, headers=HEADERS)
    test("Crear programa", r, 201)
    programa_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.get(f"{BASE}/v2/admin/programas/{programa_id}", headers=HEADERS)
    test("Obtener programa por ID", r)

    r = requests.get(f"{BASE}/v2/admin/programas", headers=HEADERS)
    test("Listar programas", r)

    r = requests.put(f"{BASE}/v2/admin/programas/{programa_id}", json={
        "moodle_category_id": 5
    }, headers=HEADERS)
    test("Actualizar programa", r)

    # ── 4. Materias ──
    print("\n--- Materias ---")

    r = requests.post(f"{BASE}/v2/admin/materias", json={
        "programa_id": programa_id,
        "nombre": "Programacion 1",
        "codigo": "PROG1",
        "semestre": 1,
        "creditos": 10,
        "politica_id": politica_carrera_id,
        "politica_examen_id": politica_examen_id,
    }, headers=HEADERS)
    test("Crear materia Prog1", r, 201)
    materia_prog1_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.post(f"{BASE}/v2/admin/materias", json={
        "programa_id": programa_id,
        "nombre": "Programacion 2",
        "codigo": "PROG2",
        "semestre": 2,
        "creditos": 10,
        "politica_id": politica_carrera_id,
        "politica_examen_id": politica_examen_id,
    }, headers=HEADERS)
    test("Crear materia Prog2", r, 201)
    materia_prog2_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.post(f"{BASE}/v2/admin/materias", json={
        "programa_id": programa_id,
        "nombre": "Base de Datos 1",
        "codigo": "BD1",
        "semestre": 1,
        "creditos": 10,
        "politica_id": politica_carrera_id,
    }, headers=HEADERS)
    test("Crear materia BD1", r, 201)

    r = requests.get(f"{BASE}/v2/admin/materias/por-programa/{programa_id}", headers=HEADERS)
    test("Listar materias por programa", r)
    assert len(r.json()) == 3, f"Deberian ser 3 materias, son {len(r.json())}"

    r = requests.get(f"{BASE}/v2/admin/materias/{materia_prog1_id}", headers=HEADERS)
    test("Obtener materia por ID", r)
    if r.status_code == 200 and r.json().get("id_rastreo"):
        passed += 1
        print(f"  [PASS] Materia tiene id_rastreo")

    # Validacion: programa inexistente
    r = requests.post(f"{BASE}/v2/admin/materias", json={
        "programa_id": 9999,
        "nombre": "Materia fantasma",
        "semestre": 1,
        "creditos": 5,
        "politica_id": politica_carrera_id,
    }, headers=HEADERS)
    test("Rechazar materia con programa inexistente", r, 400)

    # ── 5. Programa con materias (eager load) ──
    print("\n--- Programa con materias ---")

    r = requests.get(f"{BASE}/v2/admin/programas/{programa_id}/con-materias", headers=HEADERS)
    test("Programa con materias eager loaded", r)

    # ── 6. Previaturas ──
    print("\n--- Previaturas ---")

    r = requests.post(f"{BASE}/v2/admin/previaturas", json={
        "materia_id": materia_prog2_id,
        "materia_previa_id": materia_prog1_id,
        "tipo_requerido": "aprobada",
    }, headers=HEADERS)
    test("Crear previatura (Prog2 requiere Prog1)", r, 201)
    previatura_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.get(f"{BASE}/v2/admin/previaturas/materia/{materia_prog2_id}", headers=HEADERS)
    test("Obtener previaturas de Prog2", r)
    if r.status_code == 200:
        prevs = r.json()
        assert len(prevs) == 1, f"Deberia haber 1 previatura, hay {len(prevs)}"
        assert prevs[0]["materia_previa_nombre"] == "Programacion 1"

    r = requests.post(f"{BASE}/v2/admin/previaturas", json={
        "materia_id": materia_prog1_id,
        "materia_previa_id": materia_prog1_id,
        "tipo_requerido": "aprobada",
    }, headers=HEADERS)
    test("Rechazar previatura consigo misma", r, 400)

    r = requests.post(f"{BASE}/v2/admin/previaturas", json={
        "materia_id": materia_prog1_id,
        "materia_previa_id": materia_prog2_id,
        "tipo_requerido": "aprobada",
    }, headers=HEADERS)
    test("Rechazar ciclo de previaturas", r, 400)

    r = requests.post(f"{BASE}/v2/admin/previaturas", json={
        "materia_id": materia_prog2_id,
        "materia_previa_id": materia_prog1_id,
        "tipo_requerido": "aprobada",
    }, headers=HEADERS)
    test("Rechazar previatura duplicada", r, 400)

    r = requests.get(f"{BASE}/v2/admin/previaturas/malla/{programa_id}", headers=HEADERS)
    test("Malla curricular del programa", r)

    # ── 7. Instancias de Cursado (NUEVA ENTIDAD) ──
    print("\n--- Instancias de Cursado ---")

    r = requests.post(f"{BASE}/v2/admin/instancias-cursado/", json={
        "materia_id": materia_prog1_id,
        "anio_lectivo": 2026,
        "salon": "Salon A",
        "horario": "Lunes y Miercoles 18:00-20:00",
        "cupo_maximo": 40,
    }, headers=HEADERS)
    test("Crear instancia cursado Prog1 2026", r, 200)
    ic_prog1_id = r.json().get("id") if r.status_code == 200 else None
    if r.status_code == 200 and r.json().get("id_rastreo"):
        passed += 1
        print(f"  [PASS] Instancia cursado tiene id_rastreo")

    r = requests.get(f"{BASE}/v2/admin/instancias-cursado/{ic_prog1_id}", headers=HEADERS)
    test("Obtener instancia cursado por ID", r)

    r = requests.get(f"{BASE}/v2/admin/instancias-cursado/?materia_id={materia_prog1_id}&anio_lectivo=2026", headers=HEADERS)
    test("Listar instancias cursado con filtros", r)
    if r.status_code == 200:
        assert len(r.json()) >= 1, "Deberia haber al menos 1 instancia de cursado"

    r = requests.put(f"{BASE}/v2/admin/instancias-cursado/{ic_prog1_id}", json={
        "salon": "Salon B",
    }, headers=HEADERS)
    test("Actualizar instancia cursado", r)

    # ── 8. Instancias de Evaluacion (via instancia_cursado_id) ──
    print("\n--- Instancias de Evaluacion ---")

    r = requests.post(f"{BASE}/v2/admin/instancias-evaluacion", json={
        "instancia_cursado_id": ic_prog1_id,
        "nombre": "Primer Parcial",
        "peso_maximo": 15,
        "orden": 1,
        "es_grupal": False,
    }, headers=HEADERS)
    test("Crear instancia (Primer Parcial)", r, 201)

    r = requests.post(f"{BASE}/v2/admin/instancias-evaluacion", json={
        "instancia_cursado_id": ic_prog1_id,
        "nombre": "Segundo Parcial",
        "peso_maximo": 30,
        "orden": 2,
        "es_grupal": False,
    }, headers=HEADERS)
    test("Crear instancia (Segundo Parcial)", r, 201)

    r = requests.post(f"{BASE}/v2/admin/instancias-evaluacion", json={
        "instancia_cursado_id": ic_prog1_id,
        "nombre": "Proyecto Obligatorio",
        "peso_maximo": 40,
        "orden": 3,
        "es_grupal": True,
    }, headers=HEADERS)
    test("Crear instancia (Proyecto Obligatorio, grupal)", r, 201)

    r = requests.post(f"{BASE}/v2/admin/instancias-evaluacion", json={
        "instancia_cursado_id": ic_prog1_id,
        "nombre": "Valoracion Docente",
        "peso_maximo": 15,
        "orden": 4,
        "es_grupal": False,
    }, headers=HEADERS)
    test("Crear instancia (Valoracion Docente)", r, 201)

    r = requests.get(
        f"{BASE}/v2/admin/instancias-evaluacion/instancia-cursado/{ic_prog1_id}",
        headers=HEADERS,
    )
    test("Listar instancias por instancia_cursado", r)
    assert len(r.json()) == 4, f"Deberian ser 4 instancias, son {len(r.json())}"

    # ── 9. Docentes por Materia (via instancia_cursado_id) ──
    print("\n--- Docentes por Materia ---")

    r = requests.post(f"{BASE}/v2/admin/docentes-materia", json={
        "docente_id": docente_id,
        "instancia_cursado_id": ic_prog1_id,
        "rol_docente": "titular",
    }, headers=HEADERS)
    test("Asignar docente a instancia cursado", r, 201)
    asignacion_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.get(
        f"{BASE}/v2/admin/docentes-materia/instancia-cursado/{ic_prog1_id}",
        headers=HEADERS,
    )
    test("Listar docentes de instancia cursado", r)

    # Validacion: duplicado
    r = requests.post(f"{BASE}/v2/admin/docentes-materia", json={
        "docente_id": docente_id,
        "instancia_cursado_id": ic_prog1_id,
        "rol_docente": "adjunto",
    }, headers=HEADERS)
    test("Rechazar asignacion duplicada", r, 400)

    r = requests.put(f"{BASE}/v2/admin/docentes-materia/{asignacion_id}", json={
        "rol_docente": "adjunto",
    }, headers=HEADERS)
    test("Cambiar rol de docente", r)

    # ── 10. Delete protegido ──
    print("\n--- Delete protegido ---")

    r = requests.delete(f"{BASE}/v2/admin/politicas-calificacion/{politica_carrera_id}", headers=HEADERS)
    test("Rechazar eliminar politica con materias", r, 400)

    r = requests.delete(f"{BASE}/v2/admin/programas/{programa_id}", headers=HEADERS)
    test("Rechazar eliminar programa con materias", r, 400)

    # ── 11. Cleanup (delete en orden correcto) ──
    print("\n--- Cleanup ---")

    r = requests.delete(f"{BASE}/v2/admin/docentes-materia/{asignacion_id}", headers=HEADERS)
    test("Eliminar asignacion docente", r, 204)

    r = requests.delete(f"{BASE}/v2/admin/previaturas/{previatura_id}", headers=HEADERS)
    test("Eliminar previatura", r, 204)

    # ── Resumen ──
    print(f"\n=== RESULTADO: {passed} passed, {failed} failed ===\n")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
