"""
Test - Sistema de documentos (LocalFileService + endpoints)
Prueba upload, listado, descarga, soft-delete y permisos.
Requiere servidor corriendo en localhost:8000
"""
import requests
import sys
import os
import tempfile

BASE = "http://localhost:8000"

from v2.auth.security import create_v2_token
from database.database import get_db_session
from v2.models.usuario import Usuario
from v2.models.enums import RolUsuario
from v2.models.alumno import Alumno
from v2.models.profesor import Profesor
from sqlmodel import select


# -- Setup -------------------------------------------------------------------

def setup_usuarios():
    """Crear usuarios de prueba si no existen"""
    usuarios = {}
    with get_db_session() as session:
        # Admin
        admin = session.exec(
            select(Usuario).where(Usuario.email == "admin_doc@ctcsalto.edu.uy")
        ).first()
        if not admin:
            admin = Usuario(
                email="admin_doc@ctcsalto.edu.uy",
                nombre="Admin",
                apellido="DocTest",
                rol=RolUsuario.ADMINISTRATIVO,
                activo=True,
            )
            session.add(admin)
            session.commit()
            session.refresh(admin)
        usuarios["admin"] = admin

        # Estudiante
        estudiante = session.exec(
            select(Usuario).where(Usuario.email == "estudiante_doc@ctcsalto.edu.uy")
        ).first()
        if not estudiante:
            estudiante = Usuario(
                email="estudiante_doc@ctcsalto.edu.uy",
                nombre="Juan",
                apellido="Perez",
                rol=RolUsuario.ESTUDIANTE,
                activo=True,
            )
            session.add(estudiante)
            session.commit()
            session.refresh(estudiante)

            # Crear perfil alumno
            alumno = Alumno(usuario_id=estudiante.id)
            session.add(alumno)
            session.commit()
        usuarios["estudiante"] = estudiante

        # Docente
        docente = session.exec(
            select(Usuario).where(Usuario.email == "docente_doc@ctcsalto.edu.uy")
        ).first()
        if not docente:
            docente = Usuario(
                email="docente_doc@ctcsalto.edu.uy",
                nombre="Maria",
                apellido="Gomez",
                rol=RolUsuario.DOCENTE,
                activo=True,
            )
            session.add(docente)
            session.commit()
            session.refresh(docente)

            # Crear perfil profesor
            profesor = Profesor(usuario_id=docente.id)
            session.add(profesor)
            session.commit()
        usuarios["docente"] = docente

    return usuarios


def get_headers(email, usuario_id, rol):
    token = create_v2_token(email=email, usuario_id=usuario_id, rol=rol)
    return {"Authorization": f"Bearer {token}"}


def create_test_pdf():
    """Crea un PDF minimo de prueba"""
    # PDF minimo valido
    content = b"""%PDF-1.0
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
190
%%EOF"""
    return content


def create_test_image():
    """Crea una imagen PNG minima de prueba (1x1 pixel rojo)"""
    import struct
    import zlib

    def create_png():
        signature = b'\x89PNG\r\n\x1a\n'

        # IHDR
        ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data)
        ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc & 0xFFFFFFFF)

        # IDAT
        raw_data = b'\x00\xff\x00\x00'  # filter byte + RGB
        compressed = zlib.compress(raw_data)
        idat_crc = zlib.crc32(b'IDAT' + compressed)
        idat = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc & 0xFFFFFFFF)

        # IEND
        iend_crc = zlib.crc32(b'IEND')
        iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc & 0xFFFFFFFF)

        return signature + ihdr + idat + iend

    return create_png()


# -- Tests -------------------------------------------------------------------

passed = 0
failed = 0
total = 0


def test(nombre, condicion, detalle=""):
    global passed, failed, total
    total += 1
    if condicion:
        passed += 1
        print(f"  [OK] {nombre}")
    else:
        failed += 1
        print(f"  [FAIL] {nombre} -- {detalle}")


def test_estudiante_upload_pdf(headers, usuario_id):
    """Test: estudiante sube un PDF"""
    print("\n-- Test: Estudiante sube PDF --")
    pdf_content = create_test_pdf()

    r = requests.post(
        f"{BASE}/v2/portal/estudiante/documentos",
        headers=headers,
        files={"archivo": ("formula_69a.pdf", pdf_content, "application/pdf")},
        data={"tipo": "formula_69a", "descripcion": "Formula 69A de prueba"},
    )
    test("Upload PDF - status 201", r.status_code == 201, f"status={r.status_code} body={r.text[:200]}")

    if r.status_code == 201:
        doc = r.json()
        test("Upload PDF - tiene id", "id" in doc)
        test("Upload PDF - usuario correcto", doc.get("usuario_id") == usuario_id)
        test("Upload PDF - tipo correcto", doc.get("tipo") == "formula_69a")
        test("Upload PDF - mime correcto", doc.get("mime_type") == "application/pdf")
        test("Upload PDF - tiene nombre_original", doc.get("nombre_original") == "formula_69a.pdf")
        return doc.get("id")
    return None


def test_estudiante_upload_imagen(headers):
    """Test: estudiante sube una imagen (se convierte a WebP)"""
    print("\n-- Test: Estudiante sube imagen --")
    img_content = create_test_image()

    r = requests.post(
        f"{BASE}/v2/portal/estudiante/documentos",
        headers=headers,
        files={"archivo": ("cedula_frente.png", img_content, "image/png")},
        data={"tipo": "cedula"},
    )
    test("Upload imagen - status 201", r.status_code == 201, f"status={r.status_code} body={r.text[:200]}")

    if r.status_code == 201:
        doc = r.json()
        test("Upload imagen - tipo cedula", doc.get("tipo") == "cedula")
        # Puede ser webp si Pillow esta instalado, o png si no
        mime = doc.get("mime_type")
        test("Upload imagen - mime valido", mime in ("image/webp", "image/png"), f"mime={mime}")
        return doc.get("id")
    return None


def test_estudiante_listar(headers):
    """Test: estudiante lista sus documentos"""
    print("\n-- Test: Estudiante lista documentos --")
    r = requests.get(f"{BASE}/v2/portal/estudiante/mis-documentos", headers=headers)
    test("Listar docs - status 200", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        docs = r.json()
        test("Listar docs - es lista", isinstance(docs, list))
        test("Listar docs - tiene documentos", len(docs) >= 1, f"len={len(docs)}")
        return docs
    return []


def test_estudiante_listar_filtrado(headers):
    """Test: estudiante filtra por tipo"""
    print("\n-- Test: Estudiante filtra documentos por tipo --")
    r = requests.get(
        f"{BASE}/v2/portal/estudiante/mis-documentos",
        headers=headers,
        params={"tipo": "formula_69a"},
    )
    test("Filtrar docs - status 200", r.status_code == 200)
    if r.status_code == 200:
        docs = r.json()
        test("Filtrar docs - todos son formula_69a",
             all(d["tipo"] == "formula_69a" for d in docs) if docs else True)


def test_estudiante_descargar(headers, documento_id):
    """Test: estudiante descarga su documento"""
    print("\n-- Test: Estudiante descarga documento --")
    r = requests.get(
        f"{BASE}/v2/portal/estudiante/documentos/{documento_id}",
        headers=headers,
    )
    test("Descargar - status 200", r.status_code == 200, f"status={r.status_code}")
    test("Descargar - tiene contenido", len(r.content) > 0)


def test_estudiante_no_accede_ajeno(headers_estudiante, doc_id_docente):
    """Test: estudiante no puede descargar doc de otro usuario"""
    print("\n-- Test: Estudiante no accede a doc ajeno --")
    if doc_id_docente is None:
        test("Permiso ajeno - skip (no hay doc docente)", True)
        return
    r = requests.get(
        f"{BASE}/v2/portal/estudiante/documentos/{doc_id_docente}",
        headers=headers_estudiante,
    )
    test("Permiso ajeno - status 403", r.status_code == 403, f"status={r.status_code}")


def test_docente_upload(headers):
    """Test: docente sube documento"""
    print("\n-- Test: Docente sube documento --")
    pdf_content = create_test_pdf()
    r = requests.post(
        f"{BASE}/v2/portal/docente/documentos",
        headers=headers,
        files={"archivo": ("titulo.pdf", pdf_content, "application/pdf")},
        data={"tipo": "titulo", "descripcion": "Titulo universitario"},
    )
    test("Docente upload - status 201", r.status_code == 201, f"status={r.status_code} body={r.text[:200]}")
    if r.status_code == 201:
        return r.json().get("id")
    return None


def test_admin_listar_usuario(headers_admin, usuario_id):
    """Test: admin lista documentos de un usuario"""
    print("\n-- Test: Admin lista documentos de usuario --")
    r = requests.get(
        f"{BASE}/v2/admin/documentos/{usuario_id}",
        headers=headers_admin,
    )
    test("Admin listar - status 200", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        docs = r.json()
        test("Admin listar - es lista", isinstance(docs, list))


def test_admin_subir_para_usuario(headers_admin, usuario_id):
    """Test: admin sube documento para un usuario"""
    print("\n-- Test: Admin sube documento para usuario --")
    pdf_content = create_test_pdf()
    r = requests.post(
        f"{BASE}/v2/admin/documentos/{usuario_id}",
        headers=headers_admin,
        files={"archivo": ("escolaridad.pdf", pdf_content, "application/pdf")},
        data={"tipo": "escolaridad", "descripcion": "Escolaridad subida por admin"},
    )
    test("Admin upload - status 201", r.status_code == 201, f"status={r.status_code} body={r.text[:200]}")
    if r.status_code == 201:
        doc = r.json()
        test("Admin upload - usuario correcto", doc.get("usuario_id") == usuario_id)
        return doc.get("id")
    return None


def test_admin_descargar(headers_admin, documento_id):
    """Test: admin descarga cualquier documento"""
    print("\n-- Test: Admin descarga documento --")
    r = requests.get(
        f"{BASE}/v2/admin/documentos/descargar/{documento_id}",
        headers=headers_admin,
    )
    test("Admin descargar - status 200", r.status_code == 200, f"status={r.status_code}")


def test_admin_eliminar(headers_admin, documento_id):
    """Test: admin elimina documento (soft delete)"""
    print("\n-- Test: Admin elimina documento --")
    r = requests.delete(
        f"{BASE}/v2/admin/documentos/{documento_id}",
        headers=headers_admin,
    )
    test("Admin eliminar - status 204", r.status_code == 204, f"status={r.status_code}")


def test_archivo_tipo_invalido(headers):
    """Test: rechazar tipo de archivo no permitido"""
    print("\n-- Test: Tipo de archivo invalido --")
    r = requests.post(
        f"{BASE}/v2/portal/estudiante/documentos",
        headers=headers,
        files={"archivo": ("virus.exe", b"malware content", "application/octet-stream")},
        data={"tipo": "otro"},
    )
    test("Tipo invalido - status 400", r.status_code == 400, f"status={r.status_code}")


def test_local_file_service_sanitize():
    """Test unitario: sanitize_name"""
    print("\n-- Test: sanitize_name --")
    from v2.services.local_file_service import LocalFileService
    svc = LocalFileService()
    test("sanitize 'González' -> 'gonzalez'", svc.sanitize_name("González") == "gonzalez")
    test("sanitize 'María José' -> 'maria_jose'", svc.sanitize_name("María José") == "maria_jose")
    test("sanitize 'O\\'Brien' -> 'o_brien'", svc.sanitize_name("O'Brien") == "o_brien")
    test("sanitize 'PÉREZ' -> 'perez'", svc.sanitize_name("PÉREZ") == "perez")


# -- Main --------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("TEST DOCUMENTOS - LocalFileService + Endpoints")
    print("=" * 60)

    # Setup
    usuarios = setup_usuarios()

    h_admin = get_headers(
        usuarios["admin"].email, usuarios["admin"].id, "administrativo"
    )
    h_estudiante = get_headers(
        usuarios["estudiante"].email, usuarios["estudiante"].id, "estudiante"
    )
    h_docente = get_headers(
        usuarios["docente"].email, usuarios["docente"].id, "docente"
    )

    # Tests unitarios
    test_local_file_service_sanitize()

    # Tests de endpoints - Estudiante
    doc_pdf_id = test_estudiante_upload_pdf(h_estudiante, usuarios["estudiante"].id)
    doc_img_id = test_estudiante_upload_imagen(h_estudiante)
    test_estudiante_listar(h_estudiante)
    test_estudiante_listar_filtrado(h_estudiante)
    if doc_pdf_id:
        test_estudiante_descargar(h_estudiante, doc_pdf_id)
    test_archivo_tipo_invalido(h_estudiante)

    # Tests de endpoints - Docente
    doc_docente_id = test_docente_upload(h_docente)

    # Tests de permisos cruzados
    test_estudiante_no_accede_ajeno(h_estudiante, doc_docente_id)

    # Tests de endpoints - Admin
    test_admin_listar_usuario(h_admin, usuarios["estudiante"].id)
    doc_admin_id = test_admin_subir_para_usuario(h_admin, usuarios["estudiante"].id)
    if doc_admin_id:
        test_admin_descargar(h_admin, doc_admin_id)
        test_admin_eliminar(h_admin, doc_admin_id)

    # Resumen
    print("\n" + "=" * 60)
    print(f"RESULTADO: {passed}/{total} tests pasaron")
    if failed > 0:
        print(f"  {failed} tests fallaron")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)
