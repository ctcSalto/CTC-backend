"""
Templates HTML para notificaciones por email del portal académico.
Cada template usa placeholders con str.format() — ej: {nombre}, {materia}, {nota}.

Todos los templates se envuelven en BASE_TEMPLATE para branding CTC.
"""


# ── Template base con branding CTC ──────────────────────────────────────────

BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f4f4f7; font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f7; padding:20px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
          <!-- Header -->
          <tr>
            <td style="background-color:#1a56db; padding:24px 32px; text-align:center;">
              <h1 style="margin:0; color:#ffffff; font-size:20px; font-weight:700;">
                Centro de Tecnologías de la Comunicación
              </h1>
              <p style="margin:4px 0 0; color:#bdd4ff; font-size:13px;">Portal Académico</p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              {contenido}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f9fafb; padding:16px 32px; border-top:1px solid #e5e7eb;">
              <p style="margin:0; color:#6b7280; font-size:12px; text-align:center;">
                CTC Salto — Uruguay<br>
                Este es un email automático del Portal Académico. No responder a este correo.
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


# ── 1. Inscripción a materia confirmada ─────────────────────────────────────

INSCRIPCION_MATERIA = _wrap("""
<h2 style="margin:0 0 16px; color:#111827; font-size:18px;">Inscripción confirmada</h2>
<p style="color:#374151; line-height:1.6;">
  Hola <strong>{nombre}</strong>,
</p>
<p style="color:#374151; line-height:1.6;">
  Tu inscripción a la materia <strong>{materia}</strong> ha sido confirmada
  para el año lectivo <strong>{anio_lectivo}</strong>.
</p>
<table style="width:100%; border-collapse:collapse; margin:16px 0;">
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600; width:40%;">Programa</td>
    <td style="padding:8px 12px;">{programa}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Materia</td>
    <td style="padding:8px 12px;">{materia}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Año lectivo</td>
    <td style="padding:8px 12px;">{anio_lectivo}</td>
  </tr>
</table>
""")


# ── 2. Inscripción a examen confirmada ──────────────────────────────────────

INSCRIPCION_EXAMEN = _wrap("""
<h2 style="margin:0 0 16px; color:#111827; font-size:18px;">Inscripción a examen confirmada</h2>
<p style="color:#374151; line-height:1.6;">
  Hola <strong>{nombre}</strong>,
</p>
<p style="color:#374151; line-height:1.6;">
  Tu inscripción al examen de <strong>{materia}</strong> ha sido confirmada.
</p>
<table style="width:100%; border-collapse:collapse; margin:16px 0;">
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600; width:40%;">Materia</td>
    <td style="padding:8px 12px;">{materia}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Fecha del examen</td>
    <td style="padding:8px 12px;">{fecha_examen}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Hora</td>
    <td style="padding:8px 12px;">{hora}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Salón</td>
    <td style="padding:8px 12px;">{salon}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Rendición N°</td>
    <td style="padding:8px 12px;">{numero_rendicion}</td>
  </tr>
</table>
""")


# ── 3. Recordatorio de examen próximo ───────────────────────────────────────

RECORDATORIO_EXAMEN = _wrap("""
<h2 style="margin:0 0 16px; color:#111827; font-size:18px;">Recordatorio: examen próximo</h2>
<p style="color:#374151; line-height:1.6;">
  Hola <strong>{nombre}</strong>,
</p>
<p style="color:#374151; line-height:1.6;">
  Te recordamos que tenés un examen de <strong>{materia}</strong>
  en <strong>{dias_restantes} día(s)</strong>.
</p>
<table style="width:100%; border-collapse:collapse; margin:16px 0;">
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600; width:40%;">Materia</td>
    <td style="padding:8px 12px;">{materia}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Fecha</td>
    <td style="padding:8px 12px;">{fecha_examen}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Hora</td>
    <td style="padding:8px 12px;">{hora}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Salón</td>
    <td style="padding:8px 12px;">{salon}</td>
  </tr>
</table>
""")


# ── 4. Apertura de período de inscripción ───────────────────────────────────

APERTURA_INSCRIPCION = _wrap("""
<h2 style="margin:0 0 16px; color:#111827; font-size:18px;">Período de inscripción abierto</h2>
<p style="color:#374151; line-height:1.6;">
  Hola <strong>{nombre}</strong>,
</p>
<p style="color:#374151; line-height:1.6;">
  Se ha abierto el período de inscripción a materias para el programa
  <strong>{programa}</strong>.
</p>
<table style="width:100%; border-collapse:collapse; margin:16px 0;">
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600; width:40%;">Programa</td>
    <td style="padding:8px 12px;">{programa}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Año lectivo</td>
    <td style="padding:8px 12px;">{anio_lectivo}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Desde</td>
    <td style="padding:8px 12px;">{fecha_inicio}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Hasta</td>
    <td style="padding:8px 12px;">{fecha_fin}</td>
  </tr>
</table>
<p style="color:#374151; line-height:1.6;">
  Ingresá al portal académico para inscribirte a las materias disponibles.
</p>
""")


# ── 5. Apertura de examen ───────────────────────────────────────────────────

APERTURA_EXAMEN = _wrap("""
<h2 style="margin:0 0 16px; color:#111827; font-size:18px;">Examen disponible para inscripción</h2>
<p style="color:#374151; line-height:1.6;">
  Hola <strong>{nombre}</strong>,
</p>
<p style="color:#374151; line-height:1.6;">
  Se ha habilitado una instancia de examen para la materia <strong>{materia}</strong>.
</p>
<table style="width:100%; border-collapse:collapse; margin:16px 0;">
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600; width:40%;">Materia</td>
    <td style="padding:8px 12px;">{materia}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Fecha del examen</td>
    <td style="padding:8px 12px;">{fecha_examen}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Inscripción hasta</td>
    <td style="padding:8px 12px;">{fecha_fin_inscripcion}</td>
  </tr>
</table>
<p style="color:#374151; line-height:1.6;">
  Ingresá al portal académico para inscribirte al examen.
</p>
""")


# ── 6. Cierre de inscripción próximo ────────────────────────────────────────

CIERRE_INSCRIPCION = _wrap("""
<h2 style="margin:0 0 16px; color:#111827; font-size:18px;">Cierre de inscripción próximo</h2>
<p style="color:#374151; line-height:1.6;">
  Hola <strong>{nombre}</strong>,
</p>
<p style="color:#374151; line-height:1.6;">
  El período de inscripción a materias del programa <strong>{programa}</strong>
  cierra en <strong>{dias_restantes} día(s)</strong> (el <strong>{fecha_fin}</strong>).
</p>
<p style="color:#374151; line-height:1.6;">
  Si aún no te inscribiste, ingresá al portal académico para hacerlo antes del cierre.
</p>
""")


# ── 7. Calificación disponible ──────────────────────────────────────────────

CALIFICACION_DISPONIBLE = _wrap("""
<h2 style="margin:0 0 16px; color:#111827; font-size:18px;">Calificación disponible</h2>
<p style="color:#374151; line-height:1.6;">
  Hola <strong>{nombre}</strong>,
</p>
<p style="color:#374151; line-height:1.6;">
  Tu calificación en <strong>{materia}</strong> ya está disponible.
</p>
<table style="width:100%; border-collapse:collapse; margin:16px 0;">
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600; width:40%;">Materia</td>
    <td style="padding:8px 12px;">{materia}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Nota del curso</td>
    <td style="padding:8px 12px;">{nota}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Estado</td>
    <td style="padding:8px 12px;">{estado}</td>
  </tr>
</table>
<p style="color:#374151; line-height:1.6;">
  Podés consultar tu escolaridad completa en el portal académico.
</p>
""")


# ── 8. Exoneración lograda ──────────────────────────────────────────────────

EXONERACION = _wrap("""
<h2 style="margin:0 0 16px; color:#047857; font-size:18px;">Exoneración lograda</h2>
<p style="color:#374151; line-height:1.6;">
  Hola <strong>{nombre}</strong>,
</p>
<p style="color:#374151; line-height:1.6;">
  ¡Te informamos que has <strong>exonerado</strong> la materia <strong>{materia}</strong>!
</p>
<table style="width:100%; border-collapse:collapse; margin:16px 0;">
  <tr>
    <td style="padding:8px 12px; background:#ecfdf5; font-weight:600; width:40%;">Materia</td>
    <td style="padding:8px 12px;">{materia}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#ecfdf5; font-weight:600;">Nota del curso</td>
    <td style="padding:8px 12px;">{nota}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#ecfdf5; font-weight:600;">Créditos obtenidos</td>
    <td style="padding:8px 12px;">{creditos}</td>
  </tr>
</table>
""")


# ── 9. Reprobado por rendiciones agotadas ───────────────────────────────────

REPROBADO_RENDICIONES = _wrap("""
<h2 style="margin:0 0 16px; color:#dc2626; font-size:18px;">Rendiciones de examen agotadas</h2>
<p style="color:#374151; line-height:1.6;">
  Hola <strong>{nombre}</strong>,
</p>
<p style="color:#374151; line-height:1.6;">
  Te informamos que has agotado las oportunidades de examen para la materia
  <strong>{materia}</strong> ({rendiciones_usadas} de {max_rendiciones} rendiciones).
</p>
<p style="color:#374151; line-height:1.6;">
  Para aprobar esta materia deberás volver a cursarla.
  Consultá en bedelía para más información.
</p>
""")


# ── 10. Baja/abandono procesado ─────────────────────────────────────────────

BAJA_PROCESADA = _wrap("""
<h2 style="margin:0 0 16px; color:#111827; font-size:18px;">Baja de programa procesada</h2>
<p style="color:#374151; line-height:1.6;">
  Hola <strong>{nombre}</strong>,
</p>
<p style="color:#374151; line-height:1.6;">
  Tu baja del programa <strong>{programa}</strong> ha sido procesada.
</p>
<table style="width:100%; border-collapse:collapse; margin:16px 0;">
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600; width:40%;">Programa</td>
    <td style="padding:8px 12px;">{programa}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Fecha de baja</td>
    <td style="padding:8px 12px;">{fecha_baja}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px; background:#f3f4f6; font-weight:600;">Motivo</td>
    <td style="padding:8px 12px;">{motivo}</td>
  </tr>
</table>
<p style="color:#374151; line-height:1.6;">
  Si tenés consultas, comunicate con bedelía.
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
