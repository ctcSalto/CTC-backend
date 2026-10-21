"""
Templates HTML para notificaciones por email del portal académico.
Cada template usa placeholders con str.format() — ej: {nombre}, {materia}, {nota}.

Todos los templates se envuelven en BASE_TEMPLATE para branding CTC.
Colores institucionales extraídos de ctcsalto.edu.uy:
  - Navy (primario):  #1c234c
  - Turquesa (acento): #31aab0
  - Gris texto:        #424242
  - Fondo claro:       #f5f5f5
"""


# ── Template base con branding CTC ──────────────────────────────────────────

BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f5f5f5; font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f5; padding:30px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 4px 16px rgba(28,35,76,0.10);">
          <!-- Header -->
          <tr>
            <td style="background-color:#1c234c; padding:28px 32px; text-align:center;">
              <img src="https://ctcsalto.edu.uy/branding/ctcLogoClaro.svg" alt="CTC" width="120" style="display:inline-block; margin-bottom:8px;" />
              <p style="margin:0; color:#31aab0; font-size:14px; font-weight:600; letter-spacing:1px;">PORTAL ACADEMICO</p>
            </td>
          </tr>
          <!-- Accent bar -->
          <tr>
            <td style="background-color:#31aab0; height:4px; font-size:0; line-height:0;">&nbsp;</td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:36px 32px 28px;">
              {contenido}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#1c234c; padding:20px 32px;">
              <p style="margin:0; color:#8b90a8; font-size:12px; text-align:center; line-height:1.6;">
                CTC Salto — Educacion Tecnica Profesional — Uruguay<br>
                Este es un email automatico del Portal Academico. No responder a este correo.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _wrap(contenido: str) -> str:
    """Envuelve contenido en el template base."""
    return BASE_TEMPLATE.format(contenido=contenido)


# ── Helpers de estilo ─────────────────────────────────────────────────────────

_TABLE_OPEN = '<table style="width:100%; border-collapse:collapse; margin:20px 0; border-radius:8px; overflow:hidden; border:1px solid #e8e8ec;">'
_TH_STYLE = 'padding:10px 16px; background:#1c234c; color:#ffffff; font-weight:600; width:40%; text-align:left; font-size:14px;'
_TD_STYLE = 'padding:10px 16px; background:#f8f9fb; color:#424242; font-size:14px;'
_TH_GREEN = 'padding:10px 16px; background:#0d9488; color:#ffffff; font-weight:600; width:40%; text-align:left; font-size:14px;'
_TD_GREEN = 'padding:10px 16px; background:#f0fdfa; color:#424242; font-size:14px;'

_H2_STYLE = 'margin:0 0 16px; color:#1c234c; font-size:20px; font-weight:700;'
_P_STYLE = 'color:#424242; line-height:1.7; font-size:15px;'
_BADGE_TEAL = 'display:inline-block; background:#31aab0; color:#fff; padding:4px 14px; border-radius:20px; font-size:13px; font-weight:600;'


def _row(label: str, value: str, th=_TH_STYLE, td=_TD_STYLE) -> str:
    return f'<tr><td style="{th}">{label}</td><td style="{td}">{value}</td></tr>'


# ── 1. Inscripción a materia confirmada ─────────────────────────────────────

INSCRIPCION_MATERIA = _wrap(f"""
<h2 style="{_H2_STYLE}">Inscripcion confirmada</h2>
<p style="{_P_STYLE}">
  Hola <strong>{{nombre}}</strong>,
</p>
<p style="{_P_STYLE}">
  Tu inscripcion a la materia <strong>{{materia}}</strong> ha sido confirmada
  para el anio lectivo <strong>{{anio_lectivo}}</strong>.
</p>
{_TABLE_OPEN}
  {_row("Programa", "{programa}")}
  {_row("Materia", "{materia}")}
  {_row("Anio lectivo", "{anio_lectivo}")}
</table>
""")


# ── 2. Inscripción a examen confirmada ──────────────────────────────────────

INSCRIPCION_EXAMEN = _wrap(f"""
<h2 style="{_H2_STYLE}">Inscripcion a examen confirmada</h2>
<p style="{_P_STYLE}">
  Hola <strong>{{nombre}}</strong>,
</p>
<p style="{_P_STYLE}">
  Tu inscripcion al examen de <strong>{{materia}}</strong> ha sido confirmada.
</p>
{_TABLE_OPEN}
  {_row("Materia", "{materia}")}
  {_row("Fecha del examen", "{fecha_examen}")}
  {_row("Hora", "{hora}")}
  {_row("Salon", "{salon}")}
  {_row("Rendicion N.", "{numero_rendicion}")}
</table>
""")


# ── 3. Recordatorio de examen próximo ───────────────────────────────────────

RECORDATORIO_EXAMEN = _wrap(f"""
<h2 style="{_H2_STYLE}">Recordatorio: examen proximo</h2>
<p style="{_P_STYLE}">
  Hola <strong>{{nombre}}</strong>,
</p>
<p style="{_P_STYLE}">
  Te recordamos que tenes un examen de <strong>{{materia}}</strong>
  en <strong>{{dias_restantes}} dia(s)</strong>.
</p>
{_TABLE_OPEN}
  {_row("Materia", "{materia}")}
  {_row("Fecha", "{fecha_examen}")}
  {_row("Hora", "{hora}")}
  {_row("Salon", "{salon}")}
</table>
""")


# ── 4. Apertura de período de inscripción ───────────────────────────────────

APERTURA_INSCRIPCION = _wrap(f"""
<h2 style="{_H2_STYLE}">Periodo de inscripcion abierto</h2>
<p style="{_P_STYLE}">
  Hola <strong>{{nombre}}</strong>,
</p>
<p style="{_P_STYLE}">
  Se ha abierto el periodo de inscripcion a materias para el programa
  <strong>{{programa}}</strong>.
</p>
{_TABLE_OPEN}
  {_row("Programa", "{programa}")}
  {_row("Anio lectivo", "{anio_lectivo}")}
  {_row("Desde", "{fecha_inicio}")}
  {_row("Hasta", "{fecha_fin}")}
</table>
<p style="{_P_STYLE}">
  Ingresa al portal academico para inscribirte a las materias disponibles.
</p>
""")


# ── 5. Apertura de examen ───────────────────────────────────────────────────

APERTURA_EXAMEN = _wrap(f"""
<h2 style="{_H2_STYLE}">Examen disponible para inscripcion</h2>
<p style="{_P_STYLE}">
  Hola <strong>{{nombre}}</strong>,
</p>
<p style="{_P_STYLE}">
  Se ha habilitado una instancia de examen para la materia <strong>{{materia}}</strong>.
</p>
{_TABLE_OPEN}
  {_row("Materia", "{materia}")}
  {_row("Fecha del examen", "{fecha_examen}")}
  {_row("Inscripcion hasta", "{fecha_fin_inscripcion}")}
</table>
<p style="{_P_STYLE}">
  Ingresa al portal academico para inscribirte al examen.
</p>
""")


# ── 6. Cierre de inscripción próximo ────────────────────────────────────────

CIERRE_INSCRIPCION = _wrap(f"""
<h2 style="{_H2_STYLE}">Cierre de inscripcion proximo</h2>
<p style="{_P_STYLE}">
  Hola <strong>{{nombre}}</strong>,
</p>
<p style="{_P_STYLE}">
  El periodo de inscripcion a materias del programa <strong>{{programa}}</strong>
  cierra en <strong>{{dias_restantes}} dia(s)</strong> (el <strong>{{fecha_fin}}</strong>).
</p>
<p style="{_P_STYLE}">
  Si aun no te inscribiste, ingresa al portal academico para hacerlo antes del cierre.
</p>
""")


# ── 7. Calificación disponible ──────────────────────────────────────────────

CALIFICACION_DISPONIBLE = _wrap(f"""
<h2 style="{_H2_STYLE}">Calificacion disponible</h2>
<p style="{_P_STYLE}">
  Hola <strong>{{nombre}}</strong>,
</p>
<p style="{_P_STYLE}">
  Tu calificacion en <strong>{{materia}}</strong> ya esta disponible.
</p>
{_TABLE_OPEN}
  {_row("Materia", "{materia}")}
  {_row("Nota del curso", "{nota}")}
  {_row("Estado", "{estado}")}
</table>
<p style="{_P_STYLE}">
  Podes consultar tu escolaridad completa en el portal academico.
</p>
""")


# ── 8. Exoneración lograda ──────────────────────────────────────────────────

EXONERACION = _wrap(f"""
<h2 style="margin:0 0 16px; color:#0d9488; font-size:20px; font-weight:700;">Exoneracion lograda</h2>
<p style="{_P_STYLE}">
  Hola <strong>{{nombre}}</strong>,
</p>
<p style="{_P_STYLE}">
  Te informamos que has <strong style="color:#0d9488;">exonerado</strong> la materia <strong>{{materia}}</strong>.
</p>
{_TABLE_OPEN.replace('#e8e8ec', '#99f6e4')}
  {_row("Materia", "{materia}", _TH_GREEN, _TD_GREEN)}
  {_row("Nota del curso", "{nota}", _TH_GREEN, _TD_GREEN)}
  {_row("Creditos obtenidos", "{creditos}", _TH_GREEN, _TD_GREEN)}
</table>
""")


# ── 9. Reprobado por rendiciones agotadas ───────────────────────────────────

REPROBADO_RENDICIONES = _wrap(f"""
<h2 style="margin:0 0 16px; color:#dc2626; font-size:20px; font-weight:700;">Rendiciones de examen agotadas</h2>
<p style="{_P_STYLE}">
  Hola <strong>{{nombre}}</strong>,
</p>
<p style="{_P_STYLE}">
  Te informamos que has agotado las oportunidades de examen para la materia
  <strong>{{materia}}</strong> ({{rendiciones_usadas}} de {{max_rendiciones}} rendiciones).
</p>
<p style="{_P_STYLE}">
  Para aprobar esta materia deberas volver a cursarla.
  Consulta en bedelia para mas informacion.
</p>
""")


# ── 10. Baja/abandono procesado ─────────────────────────────────────────────

BAJA_PROCESADA = _wrap(f"""
<h2 style="{_H2_STYLE}">Baja de programa procesada</h2>
<p style="{_P_STYLE}">
  Hola <strong>{{nombre}}</strong>,
</p>
<p style="{_P_STYLE}">
  Tu baja del programa <strong>{{programa}}</strong> ha sido procesada.
</p>
{_TABLE_OPEN}
  {_row("Programa", "{programa}")}
  {_row("Fecha de baja", "{fecha_baja}")}
  {_row("Motivo", "{motivo}")}
</table>
<p style="{_P_STYLE}">
  Si tenes consultas, comunicate con bedelia.
</p>
""")


# ── 11. Email manual individual (wrapper con branding) ──────────────────────

MANUAL_INDIVIDUAL = _wrap("""
{contenido_manual}
""")


# ── 12. Email manual masivo (wrapper con branding) ──────────────────────────

MANUAL_MASIVO = _wrap("""
{contenido_manual}
""")


# ── Mapa de templates por tipo ──────────────────────────────────────────────

TEMPLATES = {
    "inscripcion_materia": INSCRIPCION_MATERIA,
    "inscripcion_examen": INSCRIPCION_EXAMEN,
    "recordatorio_examen": RECORDATORIO_EXAMEN,
    "apertura_inscripcion": APERTURA_INSCRIPCION,
    "apertura_examen": APERTURA_EXAMEN,
    "cierre_inscripcion": CIERRE_INSCRIPCION,
    "calificacion_disponible": CALIFICACION_DISPONIBLE,
    "exoneracion": EXONERACION,
    "reprobado_rendiciones": REPROBADO_RENDICIONES,
    "baja_procesada": BAJA_PROCESADA,
    "manual_individual": MANUAL_INDIVIDUAL,
    "manual_masivo": MANUAL_MASIVO,
}
