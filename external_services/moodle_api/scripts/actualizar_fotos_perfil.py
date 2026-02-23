"""
Script para actualizar fotos de perfil de usuarios en Moodle mediante Playwright.

Flujo:
1. Obtiene todos los usuarios via core_user_get_users
2. Por cada username, crea una copia de ctc.png con el nombre {username}.jpg
3. Empaqueta todas las imágenes en un ZIP: user_photos.zip
4. Usa Playwright para:
   - Login en Moodle
   - Navegar a Administración del Sitio → Usuarios → Subir imágenes de los usuarios
   - Subir el ZIP
   - Marcar "Sobrescribir=Sí"
   - Enviar el formulario
5. Borra el ZIP temporal y todas las imágenes temporales

Uso:
    python actualizar_fotos_perfil.py
"""

import sys
import os
import shutil
import zipfile
import tempfile
from pathlib import Path

# ── sys.path → raíz del proyecto ──────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from external_services.moodle_api.moodle_config import MoodleConfig
from external_services.moodle_api.controllers.moodle_base_controller import BaseMoodleController

# ─── CONFIG ───────────────────────────────────────────────────────────────────
MOODLE_URL = os.getenv("MOODLE_URL", "https://alumnos.ctcsalto.edu.uy")
MOODLE_ADMIN_USER = "arosa"
MOODLE_ADMIN_PASS = "SaltoCTC#2025"

# Ruta de la imagen base del logo CTC
BASE_IMAGE_PATH = os.path.join(PROJECT_ROOT, "external_services", "moodle_api", "image", "ctc.png")

# Nombres de archivos temporales
TEMP_DIR_PREFIX = "moodle_user_photos_"
ZIP_FILENAME = "user_photos.zip"


# ─── OBTENER USUARIOS DE MOODLE ──────────────────────────────────────────────

def get_all_moodle_users():
    """Obtiene todos los usuarios de Moodle via API core_user_get_users"""
    config = MoodleConfig.from_env()
    controller = BaseMoodleController(config)

    print("Obteniendo usuarios de Moodle...")

    # Usar core_user_get_users con criterio auth=manual (usuarios manuales)
    # Formato especial de Moodle para arrays: criteria[0][key], criteria[0][value]
    payload = {
        "criteria[0][key]": "auth",
        "criteria[0][value]": "manual"
    }

    response = controller._make_request("core_user_get_users", payload)
    users = response.get("users", [])

    print(f"Total de usuarios obtenidos: {len(users)}")
    return users


# ─── CREAR ZIP CON IMÁGENES ───────────────────────────────────────────────────

def create_user_photos_zip(users):
    """
    Crea un ZIP con copias de ctc.png nombradas por username.

    Returns:
        tuple: (zip_path, temp_dir) - Rutas al ZIP y al directorio temporal
    """
    if not os.path.exists(BASE_IMAGE_PATH):
        raise FileNotFoundError(f"Imagen base no encontrada: {BASE_IMAGE_PATH}")

    # Crear directorio temporal
    temp_dir = tempfile.mkdtemp(prefix=TEMP_DIR_PREFIX)
    print(f"Directorio temporal creado: {temp_dir}")

    # Copiar la imagen para cada usuario
    usernames = []
    for user in users:
        username = user.get("username")
        if not username or username == "guest":
            continue

        # Crear copia de la imagen con nombre {username}.jpg
        dest_path = os.path.join(temp_dir, f"{username}.jpg")
        shutil.copy2(BASE_IMAGE_PATH, dest_path)
        usernames.append(username)

    print(f"Imágenes creadas: {len(usernames)}")

    # Crear ZIP
    zip_path = os.path.join(temp_dir, ZIP_FILENAME)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for username in usernames:
            img_path = os.path.join(temp_dir, f"{username}.jpg")
            # Agregar al ZIP con solo el nombre del archivo (sin path)
            zipf.write(img_path, arcname=f"{username}.jpg")

    print(f"ZIP creado: {zip_path}")
    print(f"Tamaño del ZIP: {os.path.getsize(zip_path) / 1024:.2f} KB")

    return zip_path, temp_dir


# ─── SUBIR ZIP A MOODLE CON PLAYWRIGHT ────────────────────────────────────────

def upload_photos_to_moodle(zip_path):
    """
    Usa Playwright para subir el ZIP a Moodle.
    """
    print("\nIniciando Playwright...")

    with sync_playwright() as p:
        # Lanzar navegador
        browser = p.chromium.launch(headless=False)  # headless=False para debug, cambiar a True en producción
        context = browser.new_context()
        page = context.new_page()

        try:
            # ── 1. Login ───────────────────────────────────────────────────
            print(f"Navegando a {MOODLE_URL}/login/index.php...")
            page.goto(f"{MOODLE_URL}/login/index.php", wait_until="networkidle")

            print("Expandiendo formulario de login...")
            # Click en el texto colapsado para expandir el formulario manual
            page.click("text=¿Desea acceder ahora con una cuenta de usuario completa?")
            page.wait_for_selector("#username", state="visible", timeout=5000)

            print("Haciendo login...")
            page.fill("#username", MOODLE_ADMIN_USER)
            page.fill("#password", MOODLE_ADMIN_PASS)
            page.click("#login button[type='submit']")

            # Esperar a que cargue el dashboard
            page.wait_for_selector("text=Administración del Sitio", timeout=10000)
            print("Login exitoso")

            # ── 2. Navegar a Subir imágenes ─────────────────────────────────
            print("Navegando a 'Subir imágenes de los usuarios'...")
            page.goto(f"{MOODLE_URL}/admin/tool/uploaduser/picture.php", wait_until="networkidle")

            # Esperar a que cargue el formulario
            page.wait_for_selector("text=Subir imágenes de los usuarios", timeout=10000)
            print("Página de subida cargada")

            # ── 3. Subir el archivo ZIP primero ──────────────────────────────
            print(f"Subiendo archivo ZIP: {zip_path}...")

            # Moodle usa un modal file picker que se abre al hacer click
            # 1. Hacer click en "Seleccione un archivo..." (usar texto parcial)
            page.click("text=Seleccione un archivo")
            page.wait_for_timeout(1000)

            # 2. Hacer click en el tab "Subir un archivo"
            page.click("text=Subir un archivo")
            page.wait_for_timeout(500)

            # 3. Ahora el input file está disponible con name="repo_upload_file"
            file_input = page.locator("input[type='file'][name='repo_upload_file']")
            file_input.set_input_files(zip_path)

            print("Archivo seleccionado, esperando a subirlo...")
            page.wait_for_timeout(1000)

            # 4. Click en "Subir este archivo" dentro del modal
            page.click("button:has-text('Subir este archivo')")

            print("Archivo subido, esperando confirmación del modal...")
            # Esperar a que el modal se cierre y el archivo aparezca en la UI
            page.wait_for_timeout(2000)

            # ── 4. Configurar formulario (después de subir archivo) ──────────
            # Hacer scroll hacia abajo para ver los demás campos
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)

            # Cambiar "¿Sobrescribir las imágenes del usuario?" a "Sí"
            print("Configurando 'Sobrescribir=Sí'...")
            page.select_option("select[name='overwritepicture']", "1")  # 1 = Sí

            # ── 5. Enviar formulario ─────────────────────────────────────────
            print("Enviando formulario...")
            # Usar un selector más específico: buscar el botón submit del formulario
            submit_button = page.locator("input[type='submit'], button[type='submit']").filter(has_text="Subir imágenes")
            submit_button.click()

            # Esperar a que se procese (puede tardar varios segundos)
            print("Esperando confirmación de Moodle...")
            try:
                # Esperar mensaje de éxito o la página de resultados
                page.wait_for_selector("text=imágenes fueron", timeout=60000)
                print("✓ Proceso completado exitosamente")

                # Capturar el mensaje de resultado
                result_text = page.locator("div.alert, div.notifysuccess, div.box").first.inner_text()
                print(f"\nResultado de Moodle:\n{result_text}")

            except PlaywrightTimeout:
                print("⚠ Timeout esperando confirmación, pero el proceso puede haber sido exitoso")

            # Tomar screenshot para debug
            screenshot_path = os.path.join(PROJECT_ROOT, "moodle_upload_result.png")
            page.screenshot(path=screenshot_path)
            print(f"Screenshot guardado en: {screenshot_path}")

        except Exception as e:
            print(f"✗ Error durante el proceso: {e}")
            # Tomar screenshot del error
            error_screenshot = os.path.join(PROJECT_ROOT, "moodle_upload_error.png")
            page.screenshot(path=error_screenshot)
            print(f"Screenshot de error guardado en: {error_screenshot}")
            raise

        finally:
            browser.close()
            print("Navegador cerrado")


# ─── LIMPIAR ARCHIVOS TEMPORALES ──────────────────────────────────────────────

def cleanup_temp_files(temp_dir):
    """Elimina el directorio temporal con todas las imágenes y el ZIP"""
    if os.path.exists(temp_dir):
        print(f"\nLimpiando archivos temporales en: {temp_dir}")
        shutil.rmtree(temp_dir)
        print("✓ Archivos temporales eliminados")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("ACTUALIZACIÓN MASIVA DE FOTOS DE PERFIL EN MOODLE")
    print("=" * 70)
    print()

    temp_dir = None

    try:
        # 1. Obtener usuarios de Moodle
        users = get_all_moodle_users()

        if not users:
            print("No se encontraron usuarios para procesar")
            return

        # 2. Crear ZIP con imágenes
        zip_path, temp_dir = create_user_photos_zip(users)

        # 3. Subir a Moodle con Playwright
        upload_photos_to_moodle(zip_path)

        print("\n" + "=" * 70)
        print("PROCESO COMPLETADO")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ Error fatal: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 4. Limpiar archivos temporales
        if temp_dir:
            cleanup_temp_files(temp_dir)


if __name__ == "__main__":
    main()
