"""
Test Fase 7 — Integracion End-to-End (v2 refactored)
Flujos completos que cruzan multiples fases del sistema academico.
Incluye: verificacion de egreso, id_rastreo, soft-delete, perfiles usuario.
"""
import requests
import sys
from datetime import datetime, timedelta

from v2.auth.security import create_v2_token
from database.database import get_db_session
from v2.models.usuario import Usuario
from v2.models.enums import RolUsuario, EstadoInscripcionMateria
from sqlmodel import select

BASE = "http://localhost:8000"


def get_or_create_user(email, nombre, apellido, rol):
    with get_db_session() as session:
        existing = session.exec(
            select(Usuario).where(Usuario.email == email)
        ).first()
        if not existing:
            user = Usuario(
                email=email, nombre=nombre, apellido=apellido,
                rol=rol, activo=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user.id
        return existing.id


def make_headers(email, usuario_id, rol):
    token = create_v2_token(email=email, usuario_id=usuario_id, rol=rol)
    return {"Authorization": f"Bearer {token}"}


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

    print("\n=== FASE 7: TEST INTEGRACION E2E (v2 refactored) ===\n")

    admin_id = get_or_create_user("admin@ctcsalto.edu.uy", "Admin", "Test", RolUsuario.ADMINISTRATIVO)
    docente_id = get_or_create_user("docente@ctcsalto.edu.uy", "Docente", "Test", RolUsuario.DOCENTE)
    # Nuevo estudiante limpio para el flujo E2E
    est_e2e_id = get_or_create_user("e2e@ctcsalto.edu.uy", "E2E", "Integracion", RolUsuario.ESTUDIANTE)

    ADMIN_H = make_headers("admin@ctcsalto.edu.uy", admin_id, "administrativo")
    DOCENTE_H = make_headers("docente@ctcsalto.edu.uy", docente_id, "docente")
    E2E_H = make_headers("e2e@ctcsalto.edu.uy", est_e2e_id, "estudiante")

    # ── 1. Crear programa con creditos_requeridos para egreso ──
    print("\n--- Setup: programa con creditos ---")

    r = requests.post(f"{BASE}/v2/admin/programas", json={
        "nombre": "Curso E2E Test",
        "tipo": "curso",
        "duracion_semestres": 2,
        "creditos_requeridos": 20,
    }, headers=ADMIN_H)
    test("Crear programa E2E", r, 201)
    programa_e2e_id = r.json().get("id") if r.status_code == 201 else None

    # Politica para curso corto (aprobacion directa)
    r = requests.get(f"{BASE}/v2/admin/politicas-calificacion", headers=ADMIN_H)
    politicas = r.json()
    pol_curso = next((p for p in politicas if "Curso" in p.get("nombre", "")), None)
    if not pol_curso:
        r = requests.post(f"{BASE}/v2/admin/politicas-calificacion", json={
            "nombre": "Base 100 - Curso E2E",
            "nota_maxima": 100,
            "tipo_nota": "numerica",
            "umbral_aprobacion": 70,
        }, headers=ADMIN_H)
        pol_curso_id = r.json().get("id") if r.status_code == 201 else None
    else:
        pol_curso_id = pol_curso["id"]

    # Crear 2 materias de 10 creditos cada una
    r = requests.post(f"{BASE}/v2/admin/materias", json={
        "programa_id": programa_e2e_id,
        "nombre": "Materia E2E A",
        "codigo": "E2EA",
        "semestre": 1,
        "creditos": 10,
        "politica_id": pol_curso_id,
    }, headers=ADMIN_H)
    test("Crear materia E2E A", r, 201)
    mat_a_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.post(f"{BASE}/v2/admin/materias", json={
        "programa_id": programa_e2e_id,
        "nombre": "Materia E2E B",
        "codigo": "E2EB",
        "semestre": 1,
        "creditos": 10,
        "politica_id": pol_curso_id,
    }, headers=ADMIN_H)
    test("Crear materia E2E B", r, 201)
    mat_b_id = r.json().get("id") if r.status_code == 201 else None

    # Crear instancias de cursado
    r = requests.post(f"{BASE}/v2/admin/instancias-cursado/", json={
        "materia_id": mat_a_id,
        "anio_lectivo": 2026,
    }, headers=ADMIN_H)
    ic_a_id = r.json().get("id") if r.status_code == 200 else None

    r = requests.post(f"{BASE}/v2/admin/instancias-cursado/", json={
        "materia_id": mat_b_id,
        "anio_lectivo": 2026,
    }, headers=ADMIN_H)
    ic_b_id = r.json().get("id") if r.status_code == 200 else None

    # Crear instancia de evaluacion para cada materia (una sola, 100%)
    r = requests.post(f"{BASE}/v2/admin/instancias-evaluacion", json={
        "instancia_cursado_id": ic_a_id,
        "nombre": "Evaluacion Final A",
        "peso_maximo": 100,
        "orden": 1,
        "es_grupal": False,
    }, headers=ADMIN_H)
    eval_a_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.post(f"{BASE}/v2/admin/instancias-evaluacion", json={
        "instancia_cursado_id": ic_b_id,
        "nombre": "Evaluacion Final B",
        "peso_maximo": 100,
        "orden": 1,
        "es_grupal": False,
    }, headers=ADMIN_H)
    eval_b_id = r.json().get("id") if r.status_code == 201 else None

    # Asignar docente
    requests.post(f"{BASE}/v2/admin/docentes-materia", json={
        "docente_id": docente_id,
        "instancia_cursado_id": ic_a_id,
        "rol_docente": "titular",
    }, headers=ADMIN_H)
    requests.post(f"{BASE}/v2/admin/docentes-materia", json={
        "docente_id": docente_id,
        "instancia_cursado_id": ic_b_id,
        "rol_docente": "titular",
    }, headers=ADMIN_H)

    # Periodo de inscripcion
    ahora = datetime.utcnow()
    requests.post(f"{BASE}/v2/admin/periodos-inscripcion", json={
        "programa_id": programa_e2e_id,
        "anio_lectivo": 2026,
        "fecha_inicio": (ahora - timedelta(days=1)).isoformat(),
        "fecha_fin": (ahora + timedelta(days=30)).isoformat(),
        "habilitado": True,
    }, headers=ADMIN_H)

    # ── 2. Inscribir alumno y cargar notas para aprobar ──
    print("\n--- Flujo completo: inscripcion -> calificacion -> egreso ---")

    # Inscribir a ambas materias
    r = requests.post(f"{BASE}/v2/admin/inscripciones/inscribir", json={
        "usuario_id": est_e2e_id,
        "instancia_cursado_id": ic_a_id,
    }, headers=ADMIN_H)
    test("Inscribir E2E a materia A", r, 200)
    insc_a_id = r.json().get("id") if r.status_code == 200 else None

    r = requests.post(f"{BASE}/v2/admin/inscripciones/inscribir", json={
        "usuario_id": est_e2e_id,
        "instancia_cursado_id": ic_b_id,
    }, headers=ADMIN_H)
    test("Inscribir E2E a materia B", r, 200)
    insc_b_id = r.json().get("id") if r.status_code == 200 else None

    # Cargar nota en A (80 = aprobado directo para curso corto)
    if insc_a_id and eval_a_id:
        r = requests.post(
            f"{BASE}/v2/portal/docente/instancia-cursado/{ic_a_id}/calificaciones",
            json={
                "inscripcion_id": insc_a_id,
                "instancia_evaluacion_id": eval_a_id,
                "nota": 80,
            },
            headers=DOCENTE_H,
        )
        test("Cargar nota materia A (80/100)", r)

    # Cargar nota en B
    if insc_b_id and eval_b_id:
        r = requests.post(
            f"{BASE}/v2/portal/docente/instancia-cursado/{ic_b_id}/calificaciones",
            json={
                "inscripcion_id": insc_b_id,
                "instancia_evaluacion_id": eval_b_id,
                "nota": 90,
            },
            headers=DOCENTE_H,
        )
        test("Cargar nota materia B (90/100)", r)

    # ── 3. Verificar egreso ──
    print("\n--- Verificacion de egreso ---")

    # Verificar como admin
    r = requests.get(
        f"{BASE}/v2/admin/inscripciones/verificar-egreso/{est_e2e_id}?programa_id={programa_e2e_id}",
        headers=ADMIN_H,
    )
    test("Verificar egreso (admin)", r)
    if r.status_code == 200:
        egreso = r.json()
        print(f"  Cumple: {egreso.get('cumple')}")
        print(f"  Creditos: {egreso.get('creditos_obtenidos')}/{egreso.get('creditos_requeridos')}")
        print(f"  Materias aprobadas: {egreso.get('materias_aprobadas')}/{egreso.get('materias_totales')}")
        print(f"  Porcentaje: {egreso.get('porcentaje_avance')}%")

    # Verificar como estudiante
    r = requests.get(
        f"{BASE}/v2/portal/estudiante/mi-egreso?programa_id={programa_e2e_id}",
        headers=E2E_H,
    )
    test("Mi egreso (estudiante)", r)

    # ── 4. Trazabilidad id_rastreo ──
    print("\n--- Trazabilidad id_rastreo ---")

    # Verificar que las entidades tienen id_rastreo
    r = requests.get(f"{BASE}/v2/admin/instancias-cursado/{ic_a_id}", headers=ADMIN_H)
    if r.status_code == 200 and r.json().get("id_rastreo"):
        passed += 1
        print(f"  [PASS] Instancia cursado tiene id_rastreo")
    else:
        failed += 1
        print(f"  [FAIL] Instancia cursado sin id_rastreo")

    r = requests.get(f"{BASE}/v2/admin/materias/{mat_a_id}", headers=ADMIN_H)
    if r.status_code == 200 and r.json().get("id_rastreo"):
        passed += 1
        print(f"  [PASS] Materia tiene id_rastreo")
    else:
        failed += 1
        print(f"  [FAIL] Materia sin id_rastreo")

    # ── 5. Docente: mis materias ──
    print("\n--- Portal docente ---")

    r = requests.get(
        f"{BASE}/v2/portal/docente/mis-materias?anio_lectivo=2026",
        headers=DOCENTE_H,
    )
    test("Mis materias (docente)", r)
    if r.status_code == 200:
        mis_materias = r.json()
        print(f"  Materias asignadas: {len(mis_materias)}")
        # Deberia incluir las materias E2E
        e2e_materias = [m for m in mis_materias if "E2E" in m.get("nombre", "")]
        if len(e2e_materias) >= 2:
            passed += 1
            print(f"  [PASS] Docente tiene al menos 2 materias E2E")

    # ── 6. Escolaridad completa ──
    print("\n--- Escolaridad E2E ---")

    r = requests.get(
        f"{BASE}/v2/portal/estudiante/mi-escolaridad?programa_id={programa_e2e_id}",
        headers=E2E_H,
    )
    test("Escolaridad E2E (estudiante)", r)

    # ── 7. Materias disponibles (no deberia haber materias disponibles si ya esta inscripto en todas) ──
    r = requests.get(
        f"{BASE}/v2/portal/estudiante/materias-disponibles?programa_id={programa_e2e_id}&anio_lectivo=2026",
        headers=E2E_H,
    )
    test("Materias disponibles E2E", r)

    # ── Resumen ──
    print(f"\n=== RESULTADO: {passed} passed, {failed} failed ===\n")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
