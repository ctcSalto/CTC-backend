"""
Compara el esquema real de la base contra lo que declaran los modelos.

POR QUE ESTE CHEQUEO Y NO "correr las migraciones sobre una base limpia"
-----------------------------------------------------------------------
Lo segundo no se puede hoy: la migracion inicial
(`a736aaa18a0f_initial_migration_with_all_models`) tiene `upgrade(): pass`, o sea
que no crea nada. Las tablas de v1 (career, user, testimony, news) no las crea
ninguna migracion, asi que `alembic upgrade head` sobre una base vacia falla en
`ALTER TABLE career` con "relation career does not exist".

Esas tablas existen porque `create_db_and_tables()` corre en el arranque
(main.py) y llama a `SQLModel.metadata.create_all`. Sin guard de entorno: corre
tambien en produccion.

EL MODO DE FALLA REAL
---------------------
`create_all` **solo crea tablas que no existen**. Nunca hace ALTER: no agrega una
columna a una tabla que ya existe, no cambia un tipo, no borra nada.

Entonces:
  - una TABLA nueva sin migracion aparece igual en todos los entornos (la crea
    create_all), y el problema es que la base y las migraciones divergen;
  - una COLUMNA nueva sin migracion NO aparece en ningun entorno, y en silencio.
    El modelo la declara, el codigo la usa, y la consulta explota en runtime.

Lo segundo es lo que este script encuentra.

    python -m v2.scripts.verificar_esquema

Solo lee. Sale con codigo 1 si hay diferencias.
"""
import sys
from typing import List

from sqlalchemy import inspect
from sqlmodel import SQLModel

from database.database import engine

# Registrar todos los modelos en SQLModel.metadata, igual que alembic/env.py
from database.models.user import User                    # noqa: F401
from database.models.career import Career                # noqa: F401
from database.models.testimony import Testimony          # noqa: F401
from database.models.news import News                    # noqa: F401
import v2.models                                          # noqa: F401


def revisar() -> List[str]:
    inspector = inspect(engine)
    problemas: List[str] = []

    tablas_modelos = set(SQLModel.metadata.tables)
    tablas_base = {t for t in inspector.get_table_names() if t != "alembic_version"}

    print(f"Tablas declaradas por los modelos: {len(tablas_modelos)}")
    print(f"Tablas en la base:                 {len(tablas_base)}")
    print()

    for tabla in sorted(tablas_modelos - tablas_base):
        problemas.append(
            f"[TABLA FALTANTE] '{tabla}' la declaran los modelos y no esta en la "
            f"base. Si el modelo ya no se usa, borralo; si se usa, falta migracion."
        )

    for tabla in sorted(tablas_base - tablas_modelos):
        problemas.append(
            f"[TABLA HUERFANA] '{tabla}' esta en la base y ningun modelo la "
            f"declara. Suele ser resto de un refactor o de una migracion revertida."
        )

    for tabla in sorted(tablas_modelos & tablas_base):
        declaradas = {c.name: c for c in SQLModel.metadata.tables[tabla].columns}
        reales = {c["name"]: c for c in inspector.get_columns(tabla)}

        for nombre in sorted(set(declaradas) - set(reales)):
            problemas.append(
                f"[COLUMNA FALTANTE] {tabla}.{nombre} esta en el modelo y no en la "
                f"base. create_all NO la va a crear: hace falta una migracion, o "
                f"el codigo que la use va a fallar en runtime."
            )

        for nombre in sorted(set(reales) - set(declaradas)):
            problemas.append(
                f"[COLUMNA HUERFANA] {tabla}.{nombre} esta en la base y ningun "
                f"modelo la declara."
            )

        for nombre in sorted(set(declaradas) & set(reales)):
            declarada, real = declaradas[nombre], reales[nombre]
            # La PK en SQLModel se declara Optional pero en la base es NOT NULL:
            # no es drift, es como SQLModel expresa el autoincremental.
            if declarada.primary_key:
                continue
            if bool(declarada.nullable) != bool(real["nullable"]):
                aviso = ""
                if not real["nullable"] and declarada.nullable:
                    aviso = ("   <-- el modelo cree que acepta NULL y la base lo "
                             "rechaza: puede tirar error al guardar")
                problemas.append(
                    f"[NULLABLE DISTINTO] {tabla}.{nombre} "
                    f"modelo={bool(declarada.nullable)} "
                    f"base={bool(real['nullable'])}{aviso}"
                )

    return problemas


def main() -> int:
    problemas = revisar()

    if not problemas:
        print("SIN DRIFT. La base coincide con lo que declaran los modelos.")
        return 0

    print(f"{len(problemas)} DIFERENCIA(S):\n")
    for problema in problemas:
        print(f"  {problema}")
    print()
    print("Ninguna es necesariamente un bug: pueden ser restos conocidos. Lo que "
          "importa\nes que la lista no CREZCA sin que alguien lo decida.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
