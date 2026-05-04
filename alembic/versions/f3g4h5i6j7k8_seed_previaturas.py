"""seed_previaturas

Revision ID: f3g4h5i6j7k8
Revises: e2f3g4h5i6j7
Create Date: 2026-05-03 12:00:00.000000

Carga inicial de previaturas basada en moodle_materias_previaturas.xlsx.
Las previaturas se resuelven por nombre de materia dentro de cada programa.
El Integrador requiere TODAS las materias del programa Analista Programador.
"""
from alembic import op
import sqlalchemy as sa
from uuid import uuid4

# revision identifiers
revision = 'f3g4h5i6j7k8'
down_revision = 'e2f3g4h5i6j7'
branch_labels = None
depends_on = None


# Definición de previaturas por programa
# Formato: { "materia": ["previa1", "previa2", ...] }

ANALISTA_PROGRAMADOR = {
    "Programación 2": ["Programación 1"],
    "Programación 3": ["Programación 1", "Programación 2"],
    "Algoritmos y Estructura de Datos": ["Programación 2"],
    "Base de Datos 2": ["Base de Datos 1"],
    "Desarrollo para Dispositivos Móviles": ["Programación 1", "Programación 2"],
    "Diseño y Desarrollo de Aplicaciones": ["Programación 2", "Programación 3", "Base de Datos 1"],
    "Ingenieria de Software": ["Programación 2", "Base de Datos 1"],
    "Taller Seguridad Informatica": ["Taller de Usabilidad y Accesibilidad", "Programación 2", "Base de Datos 1", "Pensamiento Computacional"],
    "Taller de Genexus": ["Base de Datos 2", "Programación 3"],
}

# Integrador requiere TODAS las materias del programa (excepto sí mismo)
INTEGRADOR_MATERIA = "Integrador - Analista programador"

TECNICO_GESTION = {
    "Contabilidad y Costos": ["Contabilidad Básica"],
    "Estructuras y Procesos Administrativos": ["Principios de Administración"],
    "Gestión de Recursos Humanos": ["Principios de Administración"],
    "Gestión de Ventas": ["Principios de Marketing"],
    "Liquidación de Sueldos": ["Técnica Tributaria"],
    "Presupuesto Financiero": ["Contabilidad y Costos"],
    "Prácticas de Gestión": ["Presupuesto Financiero", "Técnica Tributaria", "Gestión de Recursos Humanos"],
    "Taller Cómo crear una Empresa": ["Principios de Marketing"],
    "Taller de Comercio Exterior": ["Prácticas de Gestión"],
    "Taller de Comunicación y Negociación": ["Principios de Marketing"],
    "Taller de Derecho": ["Gestión de Recursos Humanos", "Técnica Tributaria"],
    "Técnica Tributaria": ["Contabilidad y Costos"],
    # Materias nuevas (sin moodle_id aún)
    "Taller de Informática": ["Fundamentos del Marketing"],
    "Marketing online y de servicios": ["Fundamentos del Marketing"],
    "Taller de contabilidad informatizada": ["Contabilidad y Costos"],
    "Gestión de capital humano": ["Gestión y Administración de Empresas"],
    "Taller de liquidación de sueldos": ["Gestión de Recursos Humanos", "Técnica Tributaria"],
    "Gestión de Logística Operacional": ["Operaciones de Servicios"],
    "Práctica de Gestión Integral": ["Contabilidad y Costos", "Técnica Tributaria", "Gestión de Recursos Humanos"],
    "Derecho Laboral y Comercial": ["Técnica Tributaria"],
}


def upgrade() -> None:
    conn = op.get_bind()

    # Helper: buscar materia por nombre dentro de un programa
    def find_materia(nombre, programa_id):
        result = conn.execute(
            sa.text("SELECT id FROM materia WHERE nombre = :nombre AND programa_id = :pid"),
            {"nombre": nombre, "pid": programa_id}
        ).fetchone()
        return result[0] if result else None

    # Helper: insertar previatura
    def insert_previatura(materia_id, materia_previa_id):
        # Verificar que no exista ya
        existe = conn.execute(
            sa.text("SELECT id FROM previatura WHERE materia_id = :mid AND materia_previa_id = :pid"),
            {"mid": materia_id, "pid": materia_previa_id}
        ).fetchone()
        if not existe:
            conn.execute(
                sa.text(
                    "INSERT INTO previatura (materia_id, materia_previa_id, tipo_requerido, id_rastreo) "
                    "VALUES (:mid, :pid, 'APROBADA', :uuid)"
                ),
                {"mid": materia_id, "pid": materia_previa_id, "uuid": str(uuid4())}
            )

    # --- Analista Programador ---
    prog_ap = conn.execute(
        sa.text("SELECT id FROM programa WHERE nombre LIKE '%Analista Programador%' LIMIT 1")
    ).fetchone()

    if prog_ap:
        pid_ap = prog_ap[0]

        # Previaturas normales
        for materia_nombre, previas in ANALISTA_PROGRAMADOR.items():
            materia_id = find_materia(materia_nombre, pid_ap)
            if not materia_id:
                continue
            for previa_nombre in previas:
                previa_id = find_materia(previa_nombre, pid_ap)
                if previa_id:
                    insert_previatura(materia_id, previa_id)

        # Integrador: requiere TODAS las materias del programa
        integrador_id = find_materia(INTEGRADOR_MATERIA, pid_ap)
        if integrador_id:
            todas = conn.execute(
                sa.text("SELECT id FROM materia WHERE programa_id = :pid AND id != :iid AND activo = true"),
                {"pid": pid_ap, "iid": integrador_id}
            ).fetchall()
            for (mid,) in todas:
                insert_previatura(integrador_id, mid)

    # --- Técnico en Gestión y Dirección de Empresas ---
    prog_tg = conn.execute(
        sa.text("SELECT id FROM programa WHERE nombre LIKE '%Gesti_n%Direcci_n%Empresas%' LIMIT 1")
    ).fetchone()

    if prog_tg:
        pid_tg = prog_tg[0]
        for materia_nombre, previas in TECNICO_GESTION.items():
            materia_id = find_materia(materia_nombre, pid_tg)
            if not materia_id:
                continue
            for previa_nombre in previas:
                previa_id = find_materia(previa_nombre, pid_tg)
                if previa_id:
                    insert_previatura(materia_id, previa_id)


def downgrade() -> None:
    # Eliminar todas las previaturas (no hay otras fuentes en este punto)
    op.execute(sa.text("DELETE FROM previatura"))
