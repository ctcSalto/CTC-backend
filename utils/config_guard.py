"""
Chequeo de configuracion critica al arrancar.

Existe por un patron que ya nos costo caro: un default silencioso tapando una
mala configuracion. `apscheduler` falto en requirements durante tres meses y la
app arrancaba igual, con todos los jobs muertos, porque el error se logueaba como
"no critico".

SECRET_KEY tiene el mismo riesgo pero peor: si la variable falta, el codigo cae a
un literal que esta publicado en el repo y la app arranca normal firmando los JWT
con una clave que cualquiera puede leer. Aca eso deja de ser silencioso.
"""
import os
from typing import List


# El literal que usan como fallback v1, v2 y el middleware de sesion de main.py
PLACEHOLDER_SECRET_KEY = "your-secret-key-change-in-production"


def es_produccion() -> bool:
    return os.getenv("ENVIRONMENT", "development").lower() == "production"


def revisar_configuracion_critica() -> List[str]:
    """
    Devuelve los problemas encontrados. Lista vacia = todo en orden.

    Solo mira lo que hace inseguro el despliegue, no lo que falta para que ande
    tal o cual funcionalidad: esto tiene que poder frenar el arranque sin
    discusion, asi que se queda corto a proposito.
    """
    problemas: List[str] = []

    if not es_produccion():
        return problemas

    secret = os.getenv("SECRET_KEY", "")
    if not secret:
        problemas.append(
            "SECRET_KEY no esta definida. Sin ella los JWT se firman con el "
            "literal de fallback del codigo, que esta publicado en el repositorio."
        )
    elif secret == PLACEHOLDER_SECRET_KEY:
        problemas.append(
            "SECRET_KEY es el placeholder del repositorio "
            f"('{PLACEHOLDER_SECRET_KEY}'). Cualquiera puede fabricar un token "
            "valido, incluido uno de administrativo."
        )

    return problemas


def exigir_configuracion_critica() -> None:
    """
    Corta el arranque si la configuracion critica no esta en orden.

    Solo aplica en produccion: en desarrollo los defaults son comodos y no hay
    nada que proteger.
    """
    problemas = revisar_configuracion_critica()
    if not problemas:
        return

    detalle = "\n".join(f"  - {p}" for p in problemas)
    raise RuntimeError(
        "Configuracion critica invalida en produccion. La aplicacion no arranca:\n"
        f"{detalle}\n"
        "Corregir las variables de entorno del despliegue y reintentar."
    )
