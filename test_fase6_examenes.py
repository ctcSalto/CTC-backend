"""
Test Fase 6 — Sistema de Examenes (v2 refactored)
Prueba: instancias de examen CRUD, inscripcion a examen (admin y estudiante),
calificacion de examen, marcar ausente, desinscripcion.
Usa instancia_examen en lugar de periodo_examen.
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

    print("\n=== FASE 6: TEST SISTEMA DE EXAMENES (v2 refactored) ===\n")

    admin_id = get_or_create_user("admin@ctcsalto.edu.uy", "Admin", "Test", RolUsuario.ADMINISTRATIVO)
    docente_id = get_or_create_user("docente@ctcsalto.edu.uy", "Docente", "Test", RolUsuario.DOCENTE)
    estudiante_id = get_or_create_user("estudiante@ctcsalto.edu.uy", "Estudiante", "Test", RolUsuario.ESTUDIANTE)

    ADMIN_H = make_headers("admin@ctcsalto.edu.uy", admin_id, "administrativo")
    DOCENTE_H = make_headers("docente@ctcsalto.edu.uy", docente_id, "docente")
    STUDENT_H = make_headers("estudiante@ctcsalto.edu.uy", estudiante_id, "estudiante")

    # Obtener datos base
    r = requests.get(f"{BASE}/v2/admin/programas", headers=ADMIN_H)
    programas = r.json()
    if not programas:
        print("[ERROR] No hay programas. Ejecuta fases anteriores.")
        return False
    programa_id = programas[0]["id"]

    r = requests.get(f"{BASE}/v2/admin/materias/por-programa/{programa_id}", headers=ADMIN_H)
    materias = r.json()
    prog1 = next((m for m in materias if "Programacion 1" in m.get("nombre", "")), None)
    if not prog1:
        print("[ERROR] No se encontro Programacion 1.")
        return False
    prog1_id = prog1["id"]

    # Buscar instancia_cursado
    r = requests.get(f"{BASE}/v2/admin/instancias-cursado/?materia_id={prog1_id}&anio_lectivo=2026", headers=ADMIN_H)
    ics = r.json() if r.status_code == 200 else []
    if not ics:
        print("[ERROR] No hay instancia_cursado para Prog1.")
        return False
    ic_prog1_id = ics[0]["id"]

    # Necesitamos una inscripcion en estado A_EXAMEN
    # Buscar inscripcion del estudiante
    with get_db_session() as session:
        from v2.models.inscripcion_materia import InscripcionMateria
        insc = session.exec(
            select(InscripcionMateria).where(
                InscripcionMateria.usuario_id == estudiante_id,
                InscripcionMateria.instancia_cursado_id == ic_prog1_id,
            )
        ).first()
        if insc:
            inscripcion_id = insc.id
            # Forzar estado A_EXAMEN para poder inscribirse a examen
            if insc.estado != EstadoInscripcionMateria.A_EXAMEN:
                insc.estado = EstadoInscripcionMateria.A_EXAMEN
                insc.nota_curso = 75  # Simular nota que da derecho a examen
                session.add(insc)
                session.commit()
                print(f"  [SETUP] Inscripcion {inscripcion_id} forzada a A_EXAMEN")
            else:
                print(f"  [SETUP] Inscripcion {inscripcion_id} ya esta en A_EXAMEN")
        else:
            # Crear inscripcion y forzar A_EXAMEN
            r = requests.post(f"{BASE}/v2/admin/inscripciones/inscribir", json={
                "usuario_id": estudiante_id,
                "instancia_cursado_id": ic_prog1_id,
            }, headers=ADMIN_H)
            inscripcion_id = r.json().get("id") if r.status_code == 200 else None
            if inscripcion_id:
                insc = session.get(InscripcionMateria, inscripcion_id)
                if insc:
                    insc.estado = EstadoInscripcionMateria.A_EXAMEN
                    insc.nota_curso = 75
                    session.add(insc)
                    session.commit()
                    print(f"  [SETUP] Inscripcion creada y forzada a A_EXAMEN")

    if not inscripcion_id:
        print("[ERROR] No se pudo obtener/crear inscripcion.")
        return False

    # ── 1. CRUD Instancias de Examen ──
    print("\n--- CRUD Instancias de Examen ---")

    ahora = datetime.utcnow()
    r = requests.post(f"{BASE}/v2/admin/instancias-examen/", json={
        "materia_id": prog1_id,
        "nombre": "Examen Febrero 2026",
        "fecha_inicio_inscripcion": (ahora - timedelta(days=1)).isoformat(),
        "fecha_fin_inscripcion": (ahora + timedelta(days=15)).isoformat(),
        "fecha_examen": (ahora + timedelta(days=20)).isoformat(),
        "hora": "09:00",
        "salon": "Salon Examen A",
        "modalidad": "presencial",
        "tipo": "ordinario",
        "habilitado": True,
    }, headers=ADMIN_H)
    test("Crear instancia examen", r, 201)
    instancia_examen_id = r.json().get("id") if r.status_code == 201 else None
    if r.status_code == 201 and r.json().get("id_rastreo"):
        passed += 1
        print(f"  [PASS] Instancia examen tiene id_rastreo")

    r = requests.get(f"{BASE}/v2/admin/instancias-examen/materia/{prog1_id}", headers=ADMIN_H)
    test("Listar instancias examen de materia", r)

    r = requests.get(f"{BASE}/v2/admin/instancias-examen/activas", headers=ADMIN_H)
    test("Listar instancias examen activas", r)

    r = requests.get(f"{BASE}/v2/admin/instancias-examen/{instancia_examen_id}", headers=ADMIN_H)
    test("Obtener instancia examen por ID", r)

    r = requests.put(f"{BASE}/v2/admin/instancias-examen/{instancia_examen_id}", json={
        "salon": "Salon Examen B",
    }, headers=ADMIN_H)
    test("Actualizar instancia examen", r)

    # Asignar profesor a instancia de examen
    r = requests.post(f"{BASE}/v2/admin/instancias-examen/{instancia_examen_id}/profesores", json={
        "docente_id": docente_id,
    }, headers=ADMIN_H)
    test("Asignar profesor a instancia examen", r)

    # ── 2. Inscripcion a examen (admin, bypass periodo) ──
    print("\n--- Inscripcion a examen (admin) ---")

    r = requests.post(f"{BASE}/v2/admin/examenes/inscribir", json={
        "inscripcion_materia_id": inscripcion_id,
        "instancia_examen_id": instancia_examen_id,
    }, headers=ADMIN_H)
    test("Inscribir a examen (admin)", r, 201)
    inscripcion_examen_id = r.json().get("id") if r.status_code == 201 else None
    if r.status_code == 201 and r.json().get("id_rastreo"):
        passed += 1
        print(f"  [PASS] Inscripcion examen tiene id_rastreo")

    # Duplicado
    r = requests.post(f"{BASE}/v2/admin/examenes/inscribir", json={
        "inscripcion_materia_id": inscripcion_id,
        "instancia_examen_id": instancia_examen_id,
    }, headers=ADMIN_H)
    test("Rechazar inscripcion duplicada a examen", r, 400)

    # ── 3. Listar inscriptos a instancia ──
    print("\n--- Listar inscriptos ---")

    r = requests.get(f"{BASE}/v2/admin/examenes/instancia/{instancia_examen_id}", headers=ADMIN_H)
    test("Listar inscriptos a instancia examen (admin)", r)
    if r.status_code == 200:
        inscriptos = r.json()
        print(f"  Inscriptos: {len(inscriptos)}")

    r = requests.get(f"{BASE}/v2/admin/instancias-examen/{instancia_examen_id}/inscriptos", headers=ADMIN_H)
    test("Listar inscriptos via instancias-examen", r)

    # ── 4. Mis examenes (estudiante) ──
    print("\n--- Portal estudiante ---")

    r = requests.get(
        f"{BASE}/v2/portal/estudiante/mis-examenes/{inscripcion_id}",
        headers=STUDENT_H,
    )
    test("Mis examenes (estudiante)", r)

    # ── 5. Calificar examen (docente) ──
    print("\n--- Calificar examen ---")

    if inscripcion_examen_id:
        r = requests.post(
            f"{BASE}/v2/portal/docente/materia/{prog1_id}/examenes/{inscripcion_examen_id}/calificar",
            json={"nota_examen": 85},
            headers=DOCENTE_H,
        )
        test("Calificar examen (docente, aprobado)", r)
        if r.status_code == 200:
            data = r.json()
            if data.get("estado") == "aprobado":
                passed += 1
                print(f"  [PASS] Examen aprobado con nota {data.get('nota_examen')}")
            else:
                failed += 1
                print(f"  [FAIL] Estado examen: {data.get('estado')}, esperado aprobado")

    # ── 6. Crear otra instancia y probar ausente + desinscripcion ──
    print("\n--- Ausente y desinscripcion ---")

    # Necesitamos que la inscripcion vuelva a A_EXAMEN para otro examen
    with get_db_session() as session:
        from v2.models.inscripcion_materia import InscripcionMateria
        insc = session.get(InscripcionMateria, inscripcion_id)
        if insc:
            insc.estado = EstadoInscripcionMateria.A_EXAMEN
            session.add(insc)
            session.commit()

    # Crear segunda instancia de examen
    r = requests.post(f"{BASE}/v2/admin/instancias-examen/", json={
        "materia_id": prog1_id,
        "nombre": "Examen Julio 2026",
        "fecha_inicio_inscripcion": (ahora - timedelta(days=1)).isoformat(),
        "fecha_fin_inscripcion": (ahora + timedelta(days=15)).isoformat(),
        "fecha_examen": (ahora + timedelta(days=45)).isoformat(),
        "modalidad": "presencial",
        "tipo": "ordinario",
        "habilitado": True,
    }, headers=ADMIN_H)
    ie2_id = r.json().get("id") if r.status_code == 201 else None

    if ie2_id:
        # Inscribir
        r = requests.post(f"{BASE}/v2/admin/examenes/inscribir", json={
            "inscripcion_materia_id": inscripcion_id,
            "instancia_examen_id": ie2_id,
        }, headers=ADMIN_H)
        ie2_inscripcion_id = r.json().get("id") if r.status_code == 201 else None

        if ie2_inscripcion_id:
            # Marcar ausente
            r = requests.post(
                f"{BASE}/v2/portal/docente/materia/{prog1_id}/examenes/{ie2_inscripcion_id}/ausente",
                headers=DOCENTE_H,
            )
            test("Marcar ausente (docente)", r)
            if r.status_code == 200 and r.json().get("estado") == "ausente":
                passed += 1
                print(f"  [PASS] Estado: ausente")

    # Crear tercera instancia para probar desinscripcion
    with get_db_session() as session:
        from v2.models.inscripcion_materia import InscripcionMateria
        insc = session.get(InscripcionMateria, inscripcion_id)
        if insc:
            insc.estado = EstadoInscripcionMateria.A_EXAMEN
            session.add(insc)
            session.commit()

    r = requests.post(f"{BASE}/v2/admin/instancias-examen/", json={
        "materia_id": prog1_id,
        "nombre": "Examen Diciembre 2026",
        "fecha_inicio_inscripcion": (ahora - timedelta(days=1)).isoformat(),
        "fecha_fin_inscripcion": (ahora + timedelta(days=15)).isoformat(),
        "fecha_examen": (ahora + timedelta(days=60)).isoformat(),
        "modalidad": "presencial",
        "tipo": "ordinario",
        "habilitado": True,
    }, headers=ADMIN_H)
    ie3_id = r.json().get("id") if r.status_code == 201 else None

    if ie3_id:
        # Inscribir via estudiante
        r = requests.post(f"{BASE}/v2/portal/estudiante/inscribirse-examen", json={
            "inscripcion_materia_id": inscripcion_id,
            "instancia_examen_id": ie3_id,
        }, headers=STUDENT_H)
        test("Inscribirse a examen (estudiante)", r, 201)
        ie3_inscripcion_id = r.json().get("id") if r.status_code == 201 else None

        if ie3_inscripcion_id:
            # Desinscribirse
            r = requests.delete(
                f"{BASE}/v2/portal/estudiante/desinscribir-examen/{ie3_inscripcion_id}",
                headers=STUDENT_H,
            )
            test("Desinscribirse de examen (estudiante)", r, 204)

    # ── Resumen ──
    print(f"\n=== RESULTADO: {passed} passed, {failed} failed ===\n")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
