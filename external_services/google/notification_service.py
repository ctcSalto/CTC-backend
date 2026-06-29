"""
Servicio reutilizable para enviar credenciales de Google Workspace via n8n webhook.
"""
import os
import requests


def send_credentials_notification(
    nuevo_correo: str,
    nueva_contrasena: str,
    firstname: str,
    lastname: str,
    email_original: str,
) -> bool:
    """
    POST al webhook de n8n para enviar las credenciales al email personal del usuario.
    Raises ValueError si el webhook no está configurado o retorna error.
    """
    webhook_url = os.getenv("N8N_NOTIFICATION_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("N8N_NOTIFICATION_WEBHOOK_URL no está definida en .env")

    api_token   = os.getenv("N8N_API_TOKEN", "")
    header_name = os.getenv("N8N_HEADER_NAME", "Authorization")
    timeout     = int(os.getenv("N8N_TIMEOUT", "30"))

    headers = {
        header_name:    api_token,
        "Content-Type": "application/json",
    }
    payload = {
        "firstname":        firstname,
        "lastname":         lastname,
        "nuevo_correo":     nuevo_correo,
        "nueva_contrasena": nueva_contrasena,
        "email_original":   email_original,
    }

    response = requests.post(webhook_url, json=payload, headers=headers, timeout=timeout)
    if response.status_code >= 400:
        raise ValueError(f"Webhook retornó {response.status_code}: {response.text}")
    return True
