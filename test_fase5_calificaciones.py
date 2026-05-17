"""
Test Fase 5 — Motor de Calificaciones (v2 refactored)
Prueba: grading engine (unitario), carga de notas docente via instancia_cursado,
recalculo automatico, carga batch, nota final directa, equipos.
Reutiliza datos de fases 3 y 4.
"""
import requests
import sys
from decimal import Decimal

from v2.auth.security import create_v2_token
from database.database import get_db_session
from v2.models.usuario import Usuario
from v2.models.enums import RolUsuario
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

    print("\n=== FASE 5: TEST MOTOR DE CALIFICACIONES (v2 refactored) ===\n")

    # ── 1. Test unitario del grading engine ──
    print("--- Grading Engine (unitario) ---")
    from v2.services.calificacion_service import calcular_estado

    # Caso 1: Exonerado (86/100 con umbral_exoneracion=86)
    estado = calcular_estado(
        nota_curso=86,
        nota_maxima=100,
        umbral_aprobacion=70,
        umbral_examen=70,
        umbral_exoneracion=86,
    )
    if estado == "exonerado":
        passed += 1
        print(f"  [PASS] 86/100 -> exonerado")
    else:
        failed += 1
        print(f"  [FAIL] 86/100 -> {estado}, esperado exonerado")

    # Caso 2: A examen (75/100, umbral_examen=70, umbral_exoneracion=86)
    estado = calcular_estado(
        nota_curso=75,
        nota_maxima=100,
        umbral_aprobacion=70,
        umbral_examen=70,
        umbral_exoneracion=86,
    )
    if estado == "a_examen":
        passed += 1
        print(f"  [PASS] 75/100 -> a_examen")
    else:
        failed += 1
        print(f"  [FAIL] 75/100 -> {estado}, esperado a_examen")

    # Caso 3: Reprobado (50/100, umbral_examen=70)
    estado = calcular_estado(
        nota_curso=50,
        nota_maxima=100,
        umbral_aprobacion=70,
        umbral_examen=70,
        umbral_exoneracion=86,
    )
    if estado == "reprobado":
        passed += 1
        print(f"  [PASS] 50/100 -> reprobado")
    else:
        failed += 1
        print(f"  [FAIL] 50/100 -> {estado}, esperado reprobado")

    # Caso 4: Aprobado directo (curso corto, sin examen, 75/100, umbral_aprobacion=70)
    estado = calcular_estado(
        nota_curso=75,
        nota_maxima=100,
        umbral_aprobacion=70,
        umbral_examen=None,
        umbral_exoneracion=None,
    )
    if estado == "aprobado":
        passed += 1
        print(f"  [PASS] 75/100 curso corto -> aprobado")
    else:
        failed += 1
        print(f"  [FAIL] 75/100 curso corto -> {estado}, esperado aprobado")

    # ── 2. Test E2E via API ──
    print("\n--- Setup para test E2E ---")

    admin_id = get_or_create_user("admin@ctcsalto.edu.uy", "Admin", "Test", RolUsuario.ADMINISTRATIVO)
    docente_id = get_or_create_user("docente@ctcsalto.edu.uy", "Docente", "Test", RolUsuario.DOCENTE)
    estudiante_id = get_or_create_user("estudiante@ctcsalto.edu.uy", "Estudiante", "Test", RolUsuario.ESTUDIANTE)

    ADMIN_H = make_headers("admin@ctcsalto.edu.uy", admin_id, "administrativo")
    DOCENTE_H = make_headers("docente@ctcsalto.edu.uy", docente_id, "docente")
    STUDENT_H = make_headers("estudiante@ctcsalto.edu.uy", estudiante_id, "estudiante")

    # Obtener datos de fases anteriores
    r = requests.get(f"{BASE}/v2/admin/programas", headers=ADMIN_H)
    programas = r.json()
    if not programas:
        print("[ERROR] No hay programas. Ejecuta test_fase3 y test_fase4 primero.")
        return False
    programa_id = programas[0]["id"]

    r = requests.get(f"{BASE}/v2/admin/materias/por-programa/{programa_id}", headers=ADMIN_H)
    materias = r.json()
    prog1 = next((m for m in materias if "Programacion 1" in m.get("nombre", "")), None)
    if not prog1:
        print("[ERROR] No se encontro Programacion 1.")
        return False
    prog1_id = prog1["id"]

    # Buscar instancia_cursado de Prog1
    r = requests.get(f"{BASE}/v2/admin/instancias-cursado/?materia_id={prog1_id}&anio_lectivo=2026", headers=ADMIN_H)
    ics = r.json() if r.status_code == 200 else []
    if not ics:
        print("[ERROR] No hay instancia_cursado para Prog1 2026.")
        return False
    ic_prog1_id = ics[0]["id"]

    # Asegurar docente asignado
    r = requests.get(f"{BASE}/v2/admin/docentes-materia/instancia-cursado/{ic_prog1_id}", headers=ADMIN_H)
    docentes = r.json() if r.status_code == 200 else []
    if not any(d.get("docente_id") == docente_id for d in docentes):
        r = requests.post(f"{BASE}/v2/admin/docentes-materia", json={
            "docente_id": docente_id,
            "instancia_cursado_id": ic_prog1_id,
            "rol_docente": "titular",
        }, headers=ADMIN_H)
        print(f"  [SETUP] Docente asignado: {r.status_code}")

    # Asegurar alumno inscripto
    with get_db_session() as session:
        from v2.models.inscripcion_materia import InscripcionMateria
        insc = session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.usuario_id == estudiante_id,
                InscripcionMateria.instancia_cursado_id == ic_prog1_id,
            )
        ).first()
        if not insc:
            r = requests.post(f"{BASE}/v2/admin/inscripciones/inscribir", json={
                "usuario_id": estudiante_id,
                "instancia_cursado_id": ic_prog1_id,
            }, headers=ADMIN_H)
            print(f"  [SETUP] Estudiante inscripto: {r.status_code}")
            inscripcion_id = r.json().get("id") if r.status_code == 200 else None
        else:
            inscripcion_id = insc.id
            # Si esta en estado terminal, reinscribir no es posible, usar el existente
            print(f"  [SETUP] Estudiante ya inscripto id={inscripcion_id} estado={insc.estado.value}")

    # Obtener instancias de evaluacion
    r = requests.get(
        f"{BASE}/v2/admin/instancias-evaluacion/instancia-cursado/{ic_prog1_id}",
        headers=ADMIN_H,
    )
    test("Obtener instancias evaluacion", r)
    instancias_eval = r.json() if r.status_code == 200 else []
    if not instancias_eval:
        print("[ERROR] No hay instancias de evaluacion. Ejecuta test_fase3 primero.")
        return False

    primer_parcial = next((ie for ie in instancias_eval if "Primer" in ie.get("nombre", "")), None)
    segundo_parcial = next((ie for ie in instancias_eval if "Segundo" in ie.get("nombre", "")), None)

    if not primer_parcial or not segundo_parcial:
        print("[ERROR] No se encontraron parciales.")
        return False

    # ── 3. Carga de calificaciones (docente) ──
    print("\n--- Carga de calificaciones ---")

    r = requests.post(
        f"{BASE}/v2/portal/docente/instancia-cursado/{ic_prog1_id}/calificaciones",
        json={
            "inscripcion_id": inscripcion_id,
            "instancia_evaluacion_id": primer_parcial["id"],
            "nota": 12,
        },
        headers=DOCENTE_H,
    )
    test("Cargar nota primer parcial (12/15)", r)

    r = requests.post(
        f"{BASE}/v2/portal/docente/instancia-cursado/{ic_prog1_id}/calificaciones",
        json={
            "inscripcion_id": inscripcion_id,
            "instancia_evaluacion_id": segundo_parcial["id"],
            "nota": 25,
        },
        headers=DOCENTE_H,
    )
    test("Cargar nota segundo parcial (25/30)", r)

    # ── 4. Ver calificaciones (docente) ──
    r = requests.get(
        f"{BASE}/v2/portal/docente/instancia-cursado/{ic_prog1_id}/calificaciones?instancia_evaluacion_id={primer_parcial['id']}",
        headers=DOCENTE_H,
    )
    test("Ver calificaciones instancia cursado (docente)", r)

    # ── 5. Ver calificaciones (estudiante) ──
    r = requests.get(
        f"{BASE}/v2/portal/estudiante/mis-calificaciones/{inscripcion_id}",
        headers=STUDENT_H,
    )
    test("Ver mis calificaciones (estudiante)", r)
    if r.status_code == 200:
        cals = r.json()
        print(f"  Calificaciones cargadas: {len(cals)}")

    # ── 6. Carga batch ──
    print("\n--- Carga batch ---")

    # Crear otro estudiante para batch
    est2_id = get_or_create_user("estudiante2@ctcsalto.edu.uy", "Estudiante2", "Test", RolUsuario.ESTUDIANTE)
    # Inscribir
    r = requests.post(f"{BASE}/v2/admin/inscripciones/inscribir", json={
        "usuario_id": est2_id,
        "instancia_cursado_id": ic_prog1_id,
    }, headers=ADMIN_H)
    inscripcion2_id = r.json().get("id") if r.status_code == 200 else None

    if inscripcion2_id:
        r = requests.post(
            f"{BASE}/v2/portal/docente/instancia-cursado/{ic_prog1_id}/calificaciones/batch",
            json={
                "instancia_evaluacion_id": primer_parcial["id"],
                "calificaciones": [
                    {"inscripcion_id": inscripcion_id, "nota": 13},
                    {"inscripcion_id": inscripcion2_id, "nota": 10},
                ],
            },
            headers=DOCENTE_H,
        )
        test("Carga batch de calificaciones", r)

    # ── 7. Nota final directa ──
    print("\n--- Nota final directa ---")

    if inscripcion2_id:
        r = requests.post(
            f"{BASE}/v2/portal/docente/instancia-cursado/{ic_prog1_id}/nota-final-directa",
            json={
                "inscripcion_id": inscripcion2_id,
                "nota": 88,
            },
            headers=DOCENTE_H,
        )
        test("Cargar nota final directa", r)
        if r.status_code == 200:
            data = r.json()
            if data.get("nota_final_directa") is not None:
                passed += 1
                print(f"  [PASS] nota_final_directa guardada: {data.get('nota_final_directa')}")

    # ── 8. Alumnos de instancia cursado (docente) ──
    print("\n--- Alumnos instancia ---")

    r = requests.get(
        f"{BASE}/v2/portal/docente/instancia-cursado/{ic_prog1_id}/alumnos",
        headers=DOCENTE_H,
    )
    test("Listar alumnos de instancia cursado", r)
    if r.status_code == 200:
        alumnos = r.json()
        print(f"  Alumnos inscriptos: {len(alumnos)}")

    # ── Resumen ──
    print(f"\n=== RESULTADO: {passed} passed, {failed} failed ===\n")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
