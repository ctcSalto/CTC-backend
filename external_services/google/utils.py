"""
Utilidades para el servicio de Google Workspace
"""
import secrets
import string


def generate_secure_password(length: int = 12) -> str:
    """
    Genera una contraseña segura aleatoria que cumple con los requisitos:
    - Al menos una letra mayúscula
    - Al menos un número
    - Al menos un carácter especial (@.*$)
    - Longitud configurable (default: 12 caracteres)

    Args:
        length: Longitud de la contraseña (mínimo 8)

    Returns:
        str: Contraseña generada
    """
    if length < 8:
        length = 8

    # Caracteres permitidos según la validación del modelo User
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special_chars = '@.*$'

    # Asegurar que tiene al menos uno de cada tipo requerido
    password = [
        secrets.choice(uppercase),      # Al menos una mayúscula
        secrets.choice(digits),          # Al menos un número
        secrets.choice(special_chars),   # Al menos un carácter especial
    ]

    # Rellenar el resto con caracteres aleatorios de todos los tipos
    all_chars = uppercase + lowercase + digits + special_chars
    password += [secrets.choice(all_chars) for _ in range(length - 3)]

    # Mezclar la contraseña para que los caracteres requeridos no estén siempre al inicio
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)
