"""
Servicio de envío de emails vía webhook de n8n.
Responsable SOLO de la entrega. No sabe de lógica de negocio.

Contrato con n8n: POST al webhook con JSON:
  {"to": "email@ejemplo.com", "subject": "Asunto", "html_body": "<html>...</html>"}

A futuro: WhatsAppService seguiría la misma interfaz pero con otro canal.
"""
import os
import time
import requests
from typing import Optional

from utils.logger import ic


class EmailService:
    """Servicio de entrega de emails vía webhook n8n."""

    def __init__(self):
        self.webhook_url: Optional[str] = os.getenv("N8N_EMAIL_WEBHOOK_URL")
        self.api_token: str = os.getenv("N8N_API_TOKEN", "")
        self.header_name: str = os.getenv("N8N_HEADER_NAME", "Authorization")
        self.timeout: int = int(os.getenv("N8N_EMAIL_TIMEOUT", "30"))

    def _get_headers(self) -> dict:
        return {
            self.header_name: self.api_token,
            "Content-Type": "application/json",
        }

    def send_single(self, destinatario: str, asunto: str, html_body: str) -> dict:
        """
        Envía un email individual vía n8n webhook.

        Args:
            destinatario: Email del destinatario
            asunto: Asunto del email
            html_body: Cuerpo HTML del email

        Returns:
            {"ok": True} si se envió correctamente
            {"ok": False, "error": "detalle"} si falló
        """
        if not self.webhook_url:
            ic("N8N_EMAIL_WEBHOOK_URL no configurada, email no enviado")
            return {"ok": False, "error": "N8N_EMAIL_WEBHOOK_URL no configurada"}

        payload = {
            "to": destinatario,
            "subject": asunto,
            "html_body": html_body,
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if response.status_code >= 400:
                error = f"Webhook retornó {response.status_code}: {response.text[:200]}"
                ic(f"Error enviando email a {destinatario}: {error}")
                return {"ok": False, "error": error}

            return {"ok": True}

        except requests.exceptions.Timeout:
            error = f"Timeout ({self.timeout}s) al enviar email a {destinatario}"
            ic(error)
            return {"ok": False, "error": error}
        except requests.exceptions.ConnectionError:
            error = f"Error de conexión al webhook n8n para {destinatario}"
            ic(error)
            return {"ok": False, "error": error}
        except Exception as e:
            error = f"Error inesperado enviando email a {destinatario}: {str(e)}"
            ic(error)
            return {"ok": False, "error": error}

    def send_batch(
        self,
        destinatarios: list[dict],
        asunto: str,
        html_body_template: str,
    ) -> dict:
        """
        Envía emails masivos. Itera secuencialmente con pausa entre envíos.

        Args:
            destinatarios: Lista de dicts con {"email": str, "variables": dict}
                          Las variables se usan para renderizar el template per-recipient.
            asunto: Asunto del email (igual para todos)
            html_body_template: HTML con placeholders {nombre}, {apellido}, etc.

        Returns:
            {"enviados": N, "errores": [{"email": str, "error": str}]}
        """
        enviados = 0
        errores = []

        for i, dest in enumerate(destinatarios):
            email = dest.get("email", "")
            variables = dest.get("variables", {})

            # Renderizar template con variables del destinatario
            try:
                html = html_body_template.format(**variables)
            except KeyError as e:
                errores.append({"email": email, "error": f"Variable faltante en template: {e}"})
                continue

            resultado = self.send_single(email, asunto, html)

            if resultado["ok"]:
                enviados += 1
            else:
                errores.append({"email": email, "error": resultado["error"]})

            # Pausa entre envíos para no sobrecargar n8n (excepto el último)
            if i < len(destinatarios) - 1:
                time.sleep(0.1)

        return {"enviados": enviados, "errores": errores}
