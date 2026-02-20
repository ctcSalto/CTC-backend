"""
Script de migración de cursos desde el Excel 'Moodle 2025.xlsx' a Moodle.

Flujo:
1. Lee la hoja 'Cursos' del xlsx (columnas: id, shortname, fullname, displayname, Categoria, Carrera, Migrado)
2. Para cada curso no migrado:
   a. Obtiene o crea la categoría padre según la columna 'Categoria' del xlsx
   b. Dentro de esa categoría crea una subcategoría según la columna 'Carrera'
      (si no tiene Carrera, usa "Cursos Independientes" como subcategoría)
   c. Crea el curso en Moodle vía core_course_create_courses con categoryid de la subcategoría
3. Reporta los cursos creados, los que ya existían y los errores

Uso:
    python external_services/moodle_api/scripts/migrate_cursos.py
    python external_services/moodle_api/scripts/migrate_cursos.py --dry-run      # solo muestra el plan
    python external_services/moodle_api/scripts/migrate_cursos.py --curso AP1    # solo ese curso
"""

import sys, os, argparse
from pathlib import Path

# Apunta sys.path a la raíz del proyecto (3 niveles arriba de scripts/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

import openpyxl
from external_services.moodle_api.moodle_config import MoodleConfig
from external_services.moodle_api.controllers.moodle_category_controller import CategoryController
from external_services.moodle_api.controllers.moodle_course_controller import CourseController
from external_services.moodle_api.payloads.moodle_course import Course

# ─── CONFIG ───────────────────────────────────────────────────────────────────
XLSX_PATH = os.path.join(PROJECT_ROOT, "Moodle 2025.xlsx")
SHEET_NAME = "Cursos"

# Columnas del xlsx (0-indexed)
COL_ID         = 0  # A - id
COL_SHORTNAME  = 1  # B - shortname
COL_FULLNAME   = 2  # C - fullname
COL_CATEGORY   = 4  # E - Categoria (padre)
COL_CARRERA    = 5  # F - Carrera   (subcategoría)
COL_MIGRADO    = 6  # G - Migrado

# Subcategoría por defecto cuando no hay Carrera
DEFAULT_SUBCATEGORY = "Cursos Independientes"


# ─── LEER XLSX ────────────────────────────────────────────────────────────────
def read_cursos_from_xlsx(shortname_filter=None):
    """
    Lee la hoja 'Cursos' y retorna lista de dicts.
    Skipa la fila 1 (header) y los cursos sin shortname o sin Categoria.
    """
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb[SHEET_NAME]

    cursos = []
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        shortname = row[COL_SHORTNAME]
        if not shortname:
            continue

        shortname = str(shortname).strip()
        fullname  = str(row[COL_FULLNAME]).strip() if row[COL_FULLNAME] else shortname
        category  = str(row[COL_CATEGORY]).strip()  if row[COL_CATEGORY] else None
        carrera   = str(row[COL_CARRERA]).strip()   if row[COL_CARRERA]  else None
        migrado   = str(row[COL_MIGRADO]).strip().lower() if row[COL_MIGRADO] else "no"

        # Filtro por curso específico si se indicó
        if shortname_filter and shortname != shortname_filter:
            continue

        cursos.append({
            "row":        i,
            "shortname":  shortname,
            "fullname":   fullname,
            "category":   category,   # nombre de la categoría padre (ej "Informática")
            "carrera":    carrera,    # nombre de la subcategoría  (ej "Analista")
            "migrado":    migrado,
        })

    wb.close()
    return cursos


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Migrar cursos del xlsx a Moodle")
    parser.add_argument("--curso",   help="Shortname del curso a migrar (solo ese)", default=None)
    parser.add_argument("--dry-run", help="Solo muestra el plan, no crea nada",      action="store_true")
    args = parser.parse_args()

    # Inicializar controladores
    config            = MoodleConfig.from_env()
    category_ctrl     = CategoryController(config)
    course_ctrl       = CourseController(config)

    # Obtener cursos que ya existen en Moodle (por shortname)
    print("Obteniendo cursos existentes de Moodle...")
    existing_courses = course_ctrl.get_courses()
    existing_by_shortname = {c["shortname"]: c for c in existing_courses}

    # Leer xlsx
    print(f"Leyendo {XLSX_PATH} → hoja '{SHEET_NAME}'...")
    cursos_xlsx = read_cursos_from_xlsx(shortname_filter=args.curso)
    print(f"Cursos leídos del xlsx: {len(cursos_xlsx)}")

    # Filtrar: solo los que no existen aún en Moodle y tienen categoría
    to_create = []
    skipped   = []
    for c in cursos_xlsx:
        if c["shortname"] in existing_by_shortname:
            skipped.append((c["shortname"], "ya existe en Moodle"))
            continue
        if not c["category"]:
            skipped.append((c["shortname"], "sin Categoria en xlsx"))
            continue
        to_create.append(c)

    # ── Mostrar plan ──
    print(f"\n{'=' * 60}")
    print(f"PLAN DE MIGRACIÓN")
    print(f"{'=' * 60}")
    print(f"  A crear:  {len(to_create)}")
    print(f"  Skip:     {len(skipped)}")
    for name, reason in skipped:
        print(f"    [SKIP] {name}: {reason}")
    print()
    for c in to_create:
        subcat = c["carrera"] if c["carrera"] else DEFAULT_SUBCATEGORY
        print(f"    [NEW]  {c['shortname']:30s} → {c['fullname']}")
        print(f"           Categoría: {c['category']} / {subcat}")

    if args.dry_run or not to_create:
        print("\n[DRY-RUN] No se creó nada." if args.dry_run else "\nNada que crear.")
        return

    # ── Crear cursos ──
    print(f"\n{'=' * 60}")
    print("CREANDO CURSOS")
    print(f"{'=' * 60}\n")

    created = 0
    errors  = 0

    for curso in to_create:
        shortname = curso["shortname"]
        fullname  = curso["fullname"]
        cat_name  = curso["category"]
        subcat_name = curso["carrera"] if curso["carrera"] else DEFAULT_SUBCATEGORY

        try:
            # 1. Obtener o crear categoría padre
            cat_padre = category_ctrl.get_or_create_category(
                name=cat_name,
                parent_id=0,
                description=f"Categoría principal: {cat_name}"
            )
            cat_padre_id = cat_padre["id"]

            # 2. Obtener o crear subcategoría dentro de la padre
            subcat = category_ctrl.get_or_create_category(
                name=subcat_name,
                parent_id=cat_padre_id,
                description=f"Subcategoría {subcat_name} bajo {cat_name}"
            )
            subcat_id = subcat["id"]

            # 3. Crear el curso
            new_course = Course(
                fullname=fullname,
                shortname=shortname,
                categoryid=subcat_id,
                summary="",
                format="topics",
                numsections=10,
                visible=1,
            )
            result = course_ctrl.create_course(new_course)

            # result es una lista con el curso creado
            if result and len(result) > 0:
                new_id = result[0].get("id", "?")
                print(f"  [OK] {shortname} (id={new_id}) → {cat_name}/{subcat_name}")
                created += 1
            else:
                print(f"  [ERR] {shortname}: respuesta inesperada: {result}")
                errors += 1

        except Exception as e:
            print(f"  [ERR] {shortname}: {e}")
            errors += 1

    # ── Reporte final ──
    print(f"\n{'=' * 60}")
    print("REPORTE DE MIGRACIÓN")
    print(f"{'=' * 60}")
    print(f"  Cursos creados:  {created}")
    print(f"  Errores:         {errors}")
    print(f"  Skipeados:       {len(skipped)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
