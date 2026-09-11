# Carga inicial — planillas

- `carga_inicial_portal_enviada_bedelia.xlsx` — la planilla que se le entregó a
  bedelía para completar (generada el 20/08/2026 con
  `v2/scripts/generar_planilla_migracion.py` y prellenada desde Google Workspace
  con `v2/scripts/traer_usuarios_google.py`). Se guarda como referencia del
  formato acordado. Bedelía empezó a completarla el 11/09/2026.

Cuando bedelía devuelva la planilla completa, guardarla acá con fecha
(`carga_inicial_portal_YYYYMMDD.xlsx`) y validarla con:

```bash
python -m v2.scripts.validar_planilla_migracion docs/carga_inicial/carga_inicial_portal_YYYYMMDD.xlsx
```

El importador se escribe contra esa planilla real (ver `docs/MIGRACION_DATOS.md`).
