# alembic/env.py
# Configuración principal de Alembic para la gestión de migraciones.
# Este archivo conecta Alembic con SQLAlchemy y con los modelos del proyecto.

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool, text
from alembic import context

# ─────────────────────────────────────────────────────────────
# Aseguramos que la raíz del proyecto esté en el PATH de Python
# para que los imports de database.py y models/ funcionen
# correctamente sin importar desde dónde se ejecute Alembic.
# ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

# ─────────────────────────────────────────────────────────────
# Carga de variables de entorno desde el archivo .env
# ubicado en la raíz del proyecto.
# override=True garantiza que las variables del .env
# tengan prioridad sobre las variables del sistema.
# ─────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

# ─────────────────────────────────────────────────────────────
# Importamos Base (con los metadatos de los modelos)
# y todos los modelos para que Alembic los detecte
# al momento de autogenerar migraciones.
# ─────────────────────────────────────────────────────────────
from database import Base       # noqa: E402
from models.libro import Libro  # noqa: E402  # Necesario para que Alembic detecte la tabla

# ─────────────────────────────────────────────────────────────
# Objeto de configuración de Alembic.
# Permite leer y modificar los valores de alembic.ini en runtime.
# ─────────────────────────────────────────────────────────────
config = context.config

# ─────────────────────────────────────────────────────────────
# Construcción dinámica de la URL de conexión a MySQL.
# Se leen las variables desde el .env en lugar de hardcodear
# las credenciales en alembic.ini, lo cual es más seguro.
# ─────────────────────────────────────────────────────────────
DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST     = os.getenv("DB_HOST")
DB_PORT     = os.getenv("DB_PORT")
DB_NAME     = os.getenv("DB_NAME")

# Validación mínima: advertir si falta alguna variable crítica
_missing = [k for k, v in {
    "DB_USER": DB_USER, "DB_PASSWORD": DB_PASSWORD,
    "DB_HOST": DB_HOST, "DB_PORT": DB_PORT, "DB_NAME": DB_NAME
}.items() if not v]

if _missing:
    raise RuntimeError(
        f"❌ Faltan variables de entorno para la conexión a la BD: {', '.join(_missing)}\n"
        "   Verificá que el archivo .env exista y tenga todos los valores."
    )

# Inyectamos la URL construida en la configuración de Alembic
config.set_main_option(
    "sqlalchemy.url",
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ─────────────────────────────────────────────────────────────
# Configuración del sistema de logging usando el archivo .ini.
# Permite ver en consola los pasos que ejecuta Alembic.
# ─────────────────────────────────────────────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ─────────────────────────────────────────────────────────────
# Metadata de los modelos SQLAlchemy.
# Alembic la usa para comparar el estado actual de la BD
# contra los modelos definidos en Python y generar migraciones.
# ─────────────────────────────────────────────────────────────
target_metadata = Base.metadata


# ─────────────────────────────────────────────────────────────
# MODO OFFLINE
# Genera el SQL de las migraciones sin conectarse a la BD.
# Útil para revisar qué cambios se aplicarán antes de ejecutarlos.
# ─────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,       # Detecta cambios en tipos de columna
        compare_server_default=True,  # Detecta cambios en valores por defecto
    )
    with context.begin_transaction():
        context.run_migrations()


# ─────────────────────────────────────────────────────────────
# MODO ONLINE
# Se conecta activamente a la BD y aplica las migraciones.
# Es el modo que se usa en el flujo normal de desarrollo.
# ─────────────────────────────────────────────────────────────
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Sin pool: cada migración abre y cierra su conexión
    )

    with connectable.connect() as connection:
        # Verificación rápida de conectividad antes de migrar
        try:
            connection.execute(text("SELECT 1"))
        except Exception as e:
            raise RuntimeError(f"❌ No se pudo conectar a la base de datos: {e}")

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,            # Detecta cambios en tipos de columna
            compare_server_default=True,  # Detecta cambios en valores por defecto
        )

        with context.begin_transaction():
            context.run_migrations()


# ─────────────────────────────────────────────────────────────
# Punto de entrada: Alembic decide el modo según el contexto.
# ─────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()