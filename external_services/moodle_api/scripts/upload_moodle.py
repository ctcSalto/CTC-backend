"""
Script de subida automática de archivos a Moodle usando Playwright + requests.

Flujo por curso:
1. Login en Moodle (una sola vez con Playwright)
2. Navegar al formulario de crear Carpeta: /course/mod.php?id={id}&add=folder&section=0
3. Rellenar nombre "Recursos del curso"
4. Obtener el draft itemid (#id_files), sesskey y ctx_id del formulario
5. Extraer cookies del browser de Playwright → sesión requests autenticada
6. Subir archivos vía POST a /repository/repository_ajax.php?action=upload
   con FormData: repo_upload_file, sesskey, repo_id=5, itemid, savepath, title, ctx_id
7. Guardar la carpeta (click #id_submitbutton2)

Uso:
    python external_services/moodle_api/scripts/upload_moodle.py
    python external_services/moodle_api/scripts/upload_moodle.py --curso AP1
    python external_services/moodle_api/scripts/upload_moodle.py --headless
"""

import sys, os, argparse, requests
from pathlib import Path
from playwright.sync_api import sync_playwright

# Apunta sys.path a la raíz del proyecto (3 niveles arriba de scripts/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
MOODLE_URL = os.getenv("MOODLE_URL", "https://alumnos.ctcsalto.edu.uy")
MOODLE_USER = "arosa"
MOODLE_PASS = "SaltoCTC#2025"

DRIVE_FILES_DIR = os.path.join(PROJECT_ROOT, "drive_files")

# Nombre de la carpeta que se crea en cada curso
FOLDER_NAME = "Recursos del curso"


# ─── OBTENER LISTA DE CURSOS DE MOODLE ───────────────────────────────────────
def get_moodle_courses():
    """Obtiene cursos vía API para tener shortname -> {id, fullname, ...}."""
    moodle_token = os.getenv("MOODLE_TOKEN")
    url = f"{MOODLE_URL}/webservice/rest/server.php?wstoken={moodle_token}&wsfunction=core_course_get_courses&moodlewsrestformat=json"
    resp = requests.post(url, timeout=30)
    cursos = resp.json()
    return {c["shortname"]: c for c in cursos}


# ─── LOGIN ────────────────────────────────────────────────────────────────────
def login(page):
    """Hace login en Moodle usando los selectores correctos."""
    page.goto(f"{MOODLE_URL}/login/index.php")
    page.wait_for_load_state("networkidle")
    page.fill('#username', MOODLE_USER)
    page.fill('#password', MOODLE_PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    print("[OK] Login exitoso")


# ─── SUBIR ARCHIVOS VÍA repository_ajax.php ─────────────────────────────────
def upload_files_via_http(session, sesskey, itemid, ctx_id, files):
    """
    Sube archivos al draft area de Moodle usando /repository/repository_ajax.php?action=upload
    con una sesión HTTP que comparte las cookies del navegador Playwright.

    FormData requerido (según dndupload.js):
      - repo_upload_file: el archivo
      - sesskey: token de sesión
      - repo_id: 5 (repositorio tipo "upload")
      - itemid: draft itemid del formulario
      - savepath: /
      - title: nombre del archivo
      - ctx_id: context id del curso
    """
    upload_url = f"{MOODLE_URL}/repository/repository_ajax.php?action=upload"
    uploaded = 0
    for file_path in files:
        filename = file_path.name
        try:
            with open(file_path, 'rb') as f:
                files_param = {'repo_upload_file': (filename, f)}
                data = {
                    'sesskey': sesskey,
                    'repo_id': '5',          # repositorio "Subir un archivo" (type=upload)
                    'itemid': str(itemid),
                    'savepath': '/',
                    'title': filename,
                    'ctx_id': str(ctx_id),
                    # No se envía accepted_types[] → acepta cualquier tipo de archivo
                }
                resp = session.post(upload_url, files=files_param, data=data, timeout=120)
                if resp.status_code == 200:
                    try:
                        result = resp.json()
                    except Exception:
                        print(f"    [ERR] {filename}: respuesta no JSON: {resp.text[:200]}")
                        continue
                    if 'error' in result and result['error']:
                        print(f"    [ERR] {filename}: {result.get('error')}")
                    else:
                        print(f"    [UP] {filename}")
                        uploaded += 1
                else:
                    print(f"    [ERR] {filename}: HTTP {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            print(f"    [ERR] {filename}: {e}")
    return uploaded


# ─── CREAR CARPETA Y SUBIR ARCHIVOS VÍA PLAYWRIGHT ──────────────────────────
def upload_files_to_course(page, course_id, shortname, files):
    """
    Navega directamente al formulario de crear Carpeta, obtiene el draft itemid,
    sube los archivos vía repository_ajax.php usando las cookies del browser,
    y luego guarda la carpeta.
    """
    # 1. Navegar al formulario de crear carpeta directamente
    folder_url = f"{MOODLE_URL}/course/mod.php?id={course_id}&add=folder&section=0"
    page.goto(folder_url)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # Verificar que llegamos al formulario
    title = page.title()
    if "Error" in title or "error" in title:
        raise Exception(f"Error al abrir formulario de carpeta: {title}")

    # 2. Rellenar nombre de la carpeta
    name_input = page.locator('#id_name')
    name_input.fill(FOLDER_NAME)

    # 3. Obtener sesskey, draft itemid y ctx_id del formulario / M.cfg
    sesskey = page.evaluate('() => document.querySelector("input[name=\'sesskey\']").value')
    draft_itemid = page.evaluate('() => document.querySelector("#id_files").value')
    ctx_id = page.evaluate('() => window.M && window.M.cfg ? window.M.cfg.contextid : null')
    print(f"  Draft itemid: {draft_itemid}, sesskey: {sesskey}, ctx_id: {ctx_id}")

    # 4. Obtener cookies del navegador para hacer uploads vía HTTP
    cookies = page.context.cookies()
    cookie_jar = requests.cookies.RequestsCookieJar()
    for c in cookies:
        cookie_jar.set(c['name'], c['value'], domain=c.get('domain', ''), path=c.get('path', '/'))

    session = requests.Session()
    session.cookies = cookie_jar

    # 5. Subir archivos al draft area vía repository_ajax.php
    uploaded_count = upload_files_via_http(session, sesskey, draft_itemid, ctx_id, files)
    if uploaded_count == 0:
        raise Exception("No se subió ningún archivo al draft area")

    # 6. Guardar la carpeta (click "Guardar y regresar al curso")
    page.click('#id_submitbutton2')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Verificar que no hubo error
    title = page.title()
    if "Error" in title:
        raise Exception(f"Error al guardar carpeta: {title}")

    print(f"  [OK] Carpeta '{FOLDER_NAME}' con {uploaded_count} archivos guardada en {shortname}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Subir archivos de Drive a Moodle")
    parser.add_argument("--curso", help="Shortname del curso para testear (solo ese curso)", default=None)
    parser.add_argument("--headless", help="Ejecutar sin ventana visible", action="store_true", default=False)
    args = parser.parse_args()

    # Obtener info de cursos
    print("Obteniendo cursos de Moodle...")
    cursos_moodle = get_moodle_courses()

    # Listar carpetas locales de drive_files
    if not os.path.exists(DRIVE_FILES_DIR):
        print(f"[ERROR] No existe la carpeta {DRIVE_FILES_DIR}")
        sys.exit(1)

    curso_dirs = sorted([d for d in Path(DRIVE_FILES_DIR).iterdir() if d.is_dir()])
    print(f"Carpetas locales encontradas: {len(curso_dirs)}")

    # Si se especificó un curso, filtrar
    if args.curso:
        curso_dirs = [d for d in curso_dirs if d.name == args.curso]
        if not curso_dirs:
            print(f"[ERROR] No encontró carpeta para curso '{args.curso}'")
            sys.exit(1)

    # Mapear carpeta local -> curso Moodle
    plan = []
    for curso_dir in curso_dirs:
        shortname = curso_dir.name
        if shortname not in cursos_moodle:
            print(f"  [SKIP] '{shortname}' no encontrado en Moodle")
            continue
        files = sorted([f for f in curso_dir.iterdir() if f.is_file()])
        if not files:
            print(f"  [SKIP] '{shortname}' sin archivos locales")
            continue
        plan.append({
            "shortname": shortname,
            "course_id": cursos_moodle[shortname]["id"],
            "files": files
        })

    print(f"\nPlan: {len(plan)} cursos con archivos para subir")
    for p in plan:
        print(f"  {p['shortname']}: {len(p['files'])} archivos (id={p['course_id']})")

    if not plan:
        print("Nada que hacer.")
        sys.exit(0)

    # Ejecutar con Playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # Login una vez
        login(page)

        # Iterar cursos
        uploaded = 0
        failed = 0
        for curso in plan:
            shortname = curso["shortname"]
            course_id = curso["course_id"]
            files = curso["files"]
            print(f"\n[CURSO] {shortname} - {len(files)} archivos")

            try:
                upload_files_to_course(page, course_id, shortname, files)
                uploaded += 1
            except Exception as e:
                print(f"  [ERROR] {shortname}: {e}")
                failed += 1
                try:
                    page.goto(f"{MOODLE_URL}/")
                    page.wait_for_load_state("networkidle")
                except:
                    pass

        browser.close()

        # Reporte
        print("\n" + "=" * 60)
        print("REPORTE DE SUBIDA")
        print("=" * 60)
        print(f"Cursos procesados exitosamente: {uploaded}")
        print(f"Cursos con errores: {failed}")
        print("=" * 60)


if __name__ == "__main__":
    main()
