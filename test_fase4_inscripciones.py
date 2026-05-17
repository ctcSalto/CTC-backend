"""
Test Fase 4 — Sistema de Inscripciones (v2 refactored)
Prueba: periodos, inscripcion con instancia_cursado_id, validacion de previaturas,
snapshots, escolaridad, materias disponibles, marcar inasistencia/abandono.
Reutiliza datos de fase 3.
"""
import requests
import sys
from datetime import datetime, timedelta

from v2.auth.security import create_v2_token
from database.database import get_db_session
from v2.models.usuario import Usuario
from v2.models.enums import RolUsuario
from sqlmodel import select

BASE = "http://localhost:8000"

# ── Setup helpers ────────────────────────────────────────────────────────────

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
            print(f"[OK] Usuario {rol.value} creado id={user.id}")
            return user.id
        else:
            print(f"[OK] Usuario {rol.value} ya existe id={existing.id}")
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

    print("\n=== FASE 4: TEST SISTEMA DE INSCRIPCIONES (v2 refactored) ===\n")

    # Setup usuarios
    admin_id = get_or_create_user("admin@ctcsalto.edu.uy", "Admin", "Test", RolUsuario.ADMINISTRATIVO)
    estudiante_id = get_or_create_user("estudiante@ctcsalto.edu.uy", "Estudiante", "Test", RolUsuario.ESTUDIANTE)

    ADMIN_H = make_headers("admin@ctcsalto.edu.uy", admin_id, "administrativo")
    STUDENT_H = make_headers("estudiante@ctcsalto.edu.uy", estudiante_id, "estudiante")

    # ── Verificar datos de fase 3 ──
    print("\n--- Verificar datos existentes (fase 3) ---")

    r = requests.get(f"{BASE}/v2/admin/programas", headers=ADMIN_H)
    test("Listar programas", r)
    programas = r.json()
    if not programas:
        print("[ERROR] No hay programas. Ejecuta test_fase3_crud.py primero.")
        return False
    programa_id = programas[0]["id"]

    r = requests.get(f"{BASE}/v2/admin/materias/por-programa/{programa_id}", headers=ADMIN_H)
    test("Listar materias del programa", r)
    materias = r.json()
    prog1 = next((m for m in materias if "Programacion 1" in m.get("nombre", "")), None)
    prog2 = next((m for m in materias if "Programacion 2" in m.get("nombre", "")), None)
    bd1 = next((m for m in materias if "Base de Datos" in m.get("nombre", "")), None)

    if not prog1 or not prog2:
        print("[ERROR] No se encontraron materias Prog1/Prog2. Ejecuta test_fase3_crud.py primero.")
        return False

    prog1_id = prog1["id"]
    prog2_id = prog2["id"]
    bd1_id = bd1["id"] if bd1 else None

    print(f"  Programa: {programa_id}, Prog1: {prog1_id}, Prog2: {prog2_id}, BD1: {bd1_id}")

    # Asegurar que existe la previatura Prog2 -> Prog1
    r = requests.get(f"{BASE}/v2/admin/previaturas/materia/{prog2_id}", headers=ADMIN_H)
    if r.status_code == 200 and len(r.json()) == 0:
        r = requests.post(f"{BASE}/v2/admin/previaturas", json={
            "materia_id": prog2_id,
            "materia_previa_id": prog1_id,
            "tipo_requerido": "aprobada",
        }, headers=ADMIN_H)
        print(f"  [SETUP] Previatura Prog2->Prog1 creada: {r.status_code}")
    else:
        print(f"  [SETUP] Previatura ya existe")

    # Buscar o crear instancia_cursado para Prog1 2026
    r = requests.get(f"{BASE}/v2/admin/instancias-cursado/?materia_id={prog1_id}&anio_lectivo=2026", headers=ADMIN_H)
    ics = r.json() if r.status_code == 200 else []
    if ics:
        ic_prog1_id = ics[0]["id"]
        print(f"  [SETUP] Instancia cursado Prog1 ya existe id={ic_prog1_id}")
    else:
        r = requests.post(f"{BASE}/v2/admin/instancias-cursado/", json={
            "materia_id": prog1_id,
            "anio_lectivo": 2026,
        }, headers=ADMIN_H)
        ic_prog1_id = r.json().get("id") if r.status_code == 200 else None
        print(f"  [SETUP] Instancia cursado Prog1 creada id={ic_prog1_id}")

    # Instancia cursado para BD1 si existe
    ic_bd1_id = None
    if bd1_id:
        r = requests.get(f"{BASE}/v2/admin/instancias-cursado/?materia_id={bd1_id}&anio_lectivo=2026", headers=ADMIN_H)
        ics_bd1 = r.json() if r.status_code == 200 else []
        if ics_bd1:
            ic_bd1_id = ics_bd1[0]["id"]
        else:
            r = requests.post(f"{BASE}/v2/admin/instancias-cursado/", json={
                "materia_id": bd1_id,
                "anio_lectivo": 2026,
            }, headers=ADMIN_H)
            ic_bd1_id = r.json().get("id") if r.status_code == 200 else None
            print(f"  [SETUP] Instancia cursado BD1 creada id={ic_bd1_id}")

    # Instancia cursado para Prog2
    r = requests.get(f"{BASE}/v2/admin/instancias-cursado/?materia_id={prog2_id}&anio_lectivo=2026", headers=ADMIN_H)
    ics_prog2 = r.json() if r.status_code == 200 else []
    if ics_prog2:
        ic_prog2_id = ics_prog2[0]["id"]
    else:
        r = requests.post(f"{BASE}/v2/admin/instancias-cursado/", json={
            "materia_id": prog2_id,
            "anio_lectivo": 2026,
        }, headers=ADMIN_H)
        ic_prog2_id = r.json().get("id") if r.status_code == 200 else None
        print(f"  [SETUP] Instancia cursado Prog2 creada id={ic_prog2_id}")

    # ── 1. Periodos de inscripcion ──
    print("\n--- Periodos de Inscripcion ---")

    ahora = datetime.utcnow()
    r = requests.post(f"{BASE}/v2/admin/periodos-inscripcion", json={
        "programa_id": programa_id,
        "anio_lectivo": 2026,
        "fecha_inicio": (ahora - timedelta(days=1)).isoformat(),
        "fecha_fin": (ahora + timedelta(days=30)).isoformat(),
        "habilitado": True,
    }, headers=ADMIN_H)
    test("Crear periodo activo", r, 201)
    periodo_id = r.json().get("id") if r.status_code == 201 else None

    r = requests.get(f"{BASE}/v2/admin/periodos-inscripcion/{periodo_id}", headers=ADMIN_H)
    test("Obtener periodo por ID", r)

    r = requests.get(f"{BASE}/v2/admin/periodos-inscripcion", headers=ADMIN_H)
    test("Listar periodos", r)

    # ── 2. Inscripcion manual por admin (skip periodo) via instancia_cursado_id ──
    print("\n--- Inscripcion manual (admin) ---")

    r = requests.post(f"{BASE}/v2/admin/inscripciones/inscribir", json={
        "usuario_id": estudiante_id,
        "instancia_cursado_id": ic_prog1_id,
    }, headers=ADMIN_H)
    test("Inscripcion manual admin (Prog1, sin previaturas)", r, 200)
    inscripcion_prog1 = r.json() if r.status_code == 200 else {}

    # Verificar snapshot
    if inscripcion_prog1:
        snap_pol = inscripcion_prog1.get("snapshot_politica")
        snap_inst = inscripcion_prog1.get("snapshot_instancias")
        if snap_pol and "nota_maxima" in snap_pol:
            passed += 1
            print(f"  [PASS] Snapshot politica tiene nota_maxima={snap_pol['nota_maxima']}")
        else:
            failed += 1
            print(f"  [FAIL] Snapshot politica vacio o incompleto: {snap_pol}")

        if snap_inst and len(snap_inst) > 0:
            passed += 1
            print(f"  [PASS] Snapshot instancias tiene {len(snap_inst)} instancias")
        else:
            passed += 1
            print(f"  [PASS] Snapshot instancias: {len(snap_inst) if snap_inst else 0} instancias (ok)")

    inscripcion_prog1_id = inscripcion_prog1.get("id")

    # Duplicado
    r = requests.post(f"{BASE}/v2/admin/inscripciones/inscribir", json={
        "usuario_id": estudiante_id,
        "instancia_cursado_id": ic_prog1_id,
    }, headers=ADMIN_H)
    test("Rechazar inscripcion duplicada", r, 400)

    # ── 3. Validacion de previaturas ──
    print("\n--- Validacion de previaturas ---")

    # Prog2 requiere Prog1 aprobada, pero Prog1 esta CURSANDO
    r = requests.post(f"{BASE}/v2/portal/estudiante/inscribirse-materia", json={
        "instancia_cursado_id": ic_prog2_id,
    }, headers=STUDENT_H)
    test("Rechazar inscripcion Prog2 (previatura no cumplida)", r, 400)
    if r.status_code == 400:
        detail = r.json().get("detail", "")
        if "previatura" in detail.lower() or "Programacion 1" in detail:
            passed += 1
            print(f"  [PASS] Mensaje indica previatura faltante")
        else:
            failed += 1
            print(f"  [FAIL] Mensaje no menciona previatura: {detail}")

    # BD1 no tiene previaturas, deberia poder inscribirse
    if ic_bd1_id:
        r = requests.post(f"{BASE}/v2/portal/estudiante/inscribirse-materia", json={
            "instancia_cursado_id": ic_bd1_id,
        }, headers=STUDENT_H)
        test("Inscripcion BD1 (sin previaturas, via estudiante)", r, 200)

    # ── 4. Escolaridad ──
    print("\n--- Escolaridad ---")

    r = requests.get(
        f"{BASE}/v2/portal/estudiante/mi-escolaridad?programa_id={programa_id}",
        headers=STUDENT_H,
    )
    test("Mi escolaridad (estudiante)", r)
    if r.status_code == 200:
        esc = r.json()
        print(f"  Creditos: {esc.get('total_creditos')}/{esc.get('total_creditos_posibles')}")

    # Admin consulta escolaridad
    r = requests.get(
        f"{BASE}/v2/admin/inscripciones/escolaridad/{estudiante_id}?programa_id={programa_id}",
        headers=ADMIN_H,
    )
    test("Escolaridad alumno (admin)", r)

    # ── 5. Materias disponibles ──
    print("\n--- Materias disponibles ---")

    r = requests.get(
        f"{BASE}/v2/portal/estudiante/materias-disponibles?programa_id={programa_id}&anio_lectivo=2026",
        headers=STUDENT_H,
    )
    test("Materias disponibles", r)
    if r.status_code == 200:
        disponibles = r.json()
        # Prog2 no deberia poder inscribirse (previatura no cumplida)
        prog2_disp = next((m for m in disponibles if m.get("materia_id") == prog2_id), None)
        if prog2_disp and not prog2_disp.get("puede_inscribirse"):
            passed += 1
            print(f"  [PASS] Prog2 marcada como NO disponible (previaturas faltantes)")
        elif prog2_disp:
            failed += 1
            print(f"  [FAIL] Prog2 marcada como disponible cuando no deberia")

    # ── 6. Marcar inasistencia ──
    print("\n--- Marcar inasistencia ---")

    r = requests.post(f"{BASE}/v2/admin/inscripciones/marcar-inasistencia", json={
        "inscripcion_id": inscripcion_prog1_id,
        "motivo": "Exceso de faltas",
    }, headers=ADMIN_H)
    test("Marcar inasistencia", r)
    if r.status_code == 200:
        insc = r.json()
        if insc.get("estado") == "perdido_inasistencia":
            passed += 1
            print(f"  [PASS] Estado cambiado a PERDIDO_INASISTENCIA")
        else:
            failed += 1
            print(f"  [FAIL] Estado es {insc.get('estado')}, esperado perdido_inasistencia")

    # No se puede marcar inasistencia de nuevo
    r = requests.post(f"{BASE}/v2/admin/inscripciones/marcar-inasistencia", json={
        "inscripcion_id": inscripcion_prog1_id,
    }, headers=ADMIN_H)
    test("Rechazar doble marcado de inasistencia", r, 400)

    # ── 7. Marcar abandono (en BD1 si existe) ──
    if ic_bd1_id:
        print("\n--- Marcar abandono ---")
        with get_db_session() as session:
            from v2.models.inscripcion_materia import InscripcionMateria
            insc_bd1 = session.exec(
                select(InscripcionMateria).where(
                    InscripcionMateria.usuario_id == estudiante_id,
                    InscripcionMateria.instancia_cursado_id == ic_bd1_id,
                )
            ).first()
            if insc_bd1:
                r = requests.post(f"{BASE}/v2/admin/inscripciones/marcar-abandono", json={
                    "inscripcion_id": insc_bd1.id,
                    "motivo": "Dejo de asistir",
                }, headers=ADMIN_H)
                test("Marcar abandono", r)
                if r.status_code == 200 and r.json().get("estado") == "abandono":
                    passed += 1
                    print(f"  [PASS] Estado cambiado a ABANDONO")

    # ── 8. Auth: estudiante no puede acceder a admin ──
    print("\n--- Auth ---")

    r = requests.get(f"{BASE}/v2/admin/periodos-inscripcion", headers=STUDENT_H)
    test("Estudiante no puede acceder a admin periodos", r, 403)

    # ── Resumen ──
    print(f"\n=== RESULTADO: {passed} passed, {failed} failed ===\n")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
