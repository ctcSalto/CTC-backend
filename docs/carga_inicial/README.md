# Carga inicial — planillas

- `carga_inicial_portal_enviada_bedelia.xlsx` — la planilla que se le entregó a
  bedelía para completar (generada el 20/08/2026 con
  `v2/scripts/generar_planilla_migracion.py` y prellenada desde Google Workspace
  con `v2/scripts/traer_usuarios_google.py`). Se guarda como referencia del
  formato acordado. Bedelía empezó a completarla el 11/09/2026.

**La planilla completa NO se guarda acá ni en ningún lugar del repo**: tiene
cédulas y la situación académica de los alumnos. La versión que vale queda en
el Drive institucional; para validarla o importarla se descarga una copia a una
carpeta fuera del repo (o a `evidencia/`, que está en `.gitignore`) y se corre:

```bash
python -m v2.scripts.validar_planilla_migracion "C:/ruta/fuera/del/repo/carga_inicial_YYYYMMDD.xlsx"
```

El `.gitignore` solo deja versionar el archivo vacío de arriba, por nombre
exacto: cualquier otro `.xlsx` en esta carpeta queda afuera.

El importador se escribe contra esa planilla real (ver `docs/MIGRACION_DATOS.md`).
