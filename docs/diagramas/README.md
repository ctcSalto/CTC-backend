# Diagramas

Generados con [Archify](https://github.com/tt-a1i/archify): cada diagrama es un
JSON tipado que se compila a un HTML autocontenido e interactivo (temas claro y
oscuro, zoom, vistas guiadas, exportacion a PNG/SVG).

| Diagrama | Fuente | Salida |
|---|---|---|
| Cobro de un curso con Handy | `pago-handy.sequence.json` | `pago-handy.html` |
| Arquitectura del backend | `arquitectura.architecture.json` | `arquitectura.html` |
| Estados de una cursada | `estados-cursada.lifecycle.json` | `estados-cursada.html` |

**Para verlos:** abrir el `.html` en el navegador. No necesitan servidor.

## Regenerar

Archify esta instalado como skill de Claude Code en `~/.claude/skills/archify`.
Requiere Node 18 o superior, sin dependencias.

```bash
cd ~/.claude/skills/archify
node bin/archify.mjs deliver sequence     docs/diagramas/pago-handy.sequence.json       docs/diagramas/pago-handy.html       --quality standard
node bin/archify.mjs deliver architecture docs/diagramas/arquitectura.architecture.json docs/diagramas/arquitectura.html     --quality standard
node bin/archify.mjs deliver lifecycle    docs/diagramas/estados-cursada.lifecycle.json docs/diagramas/estados-cursada.html  --quality standard
```

`deliver` valida antes de escribir: si el layout tiene solapamientos o flechas
que cruzan nodos ajenos, falla con el diagnostico exacto y el fix sugerido
(`labelDy`, `via`, `fromSide`…). No escribe un HTML roto.

## Lo que conviene saber antes de editar

- **El validador es estricto a proposito.** Un diagrama nuevo suele necesitar
  dos o tres rondas de correccion. Los mensajes traen coordenadas y el ajuste
  concreto; aplicarlos tal cual funciona casi siempre.
- **`lifecycle`: los carriles secundarios comparten una sola banda.** Solo
  `main` y `terminal` tienen banda propia, y las secundarias tienen columnas
  `0..2`. Con mas de tres estados fuera del camino principal, se encima todo.
  Por eso `estados-cursada` resume los cierres administrativos en un nodo.
- **`sequence` es el mas docil:** las coordenadas `y` son explicitas y no hay
  ruteo automatico que pueda salir mal.
- Los `.html` pesan ~800 KB porque llevan el runtime del visor adentro. Es el
  precio de que sean autocontenidos.
