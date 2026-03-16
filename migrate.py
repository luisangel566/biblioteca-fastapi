# migrate.py
# Script de automatización de migraciones con Alembic.
#
# Responsabilidades:
#   1. Cargar las credenciales desde el archivo .env.
#   2. Validar que todas las variables de entorno estén presentes.
#   3. Verificar conectividad con la base de datos antes de migrar.
#   4. Limpiar la tabla alembic_version huérfana si existe.
#   5. Generar una nueva revisión autogenerada.
#   6. Aplicar la migración con upgrade head.
#
# Uso:
#   python migrate.py

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# ── Fix de encoding para Windows ──────────────────────────────
# Fuerza UTF-8 en stdout/stderr para que los emojis y caracteres
# especiales no causen errores en terminales Windows (charmap).
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pymysql
from pymysql.err import OperationalError as PyMySQLOperationalError
from dotenv import load_dotenv
from alembic.config import Config
from alembic import command

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5.5s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CARGA Y VALIDACIÓN DE VARIABLES DE ENTORNO
# ─────────────────────────────────────────────────────────────
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

_env_vars = {
    "DB_USER"    : os.getenv("DB_USER"),
    "DB_PASSWORD": os.getenv("DB_PASSWORD"),
    "DB_HOST"    : os.getenv("DB_HOST"),
    "DB_PORT"    : os.getenv("DB_PORT"),
    "DB_NAME"    : os.getenv("DB_NAME"),
}

_missing = [key for key, value in _env_vars.items() if not value]
if _missing:
    logger.error(
        "Variables de entorno faltantes: %s\n"
        "  Verificá que el archivo .env exista en: %s\n"
        "  y que contenga todos los valores requeridos.",
        ", ".join(_missing),
        _ENV_PATH,
    )
    sys.exit(1)

DB_USER     = _env_vars["DB_USER"]
DB_PASSWORD = _env_vars["DB_PASSWORD"]
DB_HOST     = _env_vars["DB_HOST"]
DB_PORT     = int(_env_vars["DB_PORT"])
DB_NAME     = _env_vars["DB_NAME"]


def _get_connection() -> pymysql.Connection:
    """
    Crea y retorna una conexión activa a MySQL.
    Lanza RuntimeError con mensaje claro si la conexión falla.
    """
    try:
        return pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            connect_timeout=5,
        )
    except PyMySQLOperationalError as e:
        raise RuntimeError(
            f"\n❌ No se pudo conectar a MySQL.\n"
            f"   Host   : {DB_HOST}:{DB_PORT}\n"
            f"   Base   : {DB_NAME}\n"
            f"   Usuario: {DB_USER}\n"
            f"   Error  : {e}\n"
            "   Verificá que MySQL esté corriendo y que las credenciales sean correctas."
        )


def verificar_conexion() -> None:
    """
    Verifica que la base de datos esté accesible antes de migrar.
    Si la conexión falla, el script se detiene con mensaje claro.
    """
    logger.info("🔍 Verificando conexión a la base de datos...")
    conn = _get_connection()
    conn.close()
    logger.info(
        "✅ Conexión verificada — Host: %s:%s | Base: %s",
        DB_HOST, DB_PORT, DB_NAME,
    )


def limpiar_alembic_version() -> None:
    """
    Verifica si existe la tabla alembic_version y la elimina si está presente.

    ¿Cuándo puede quedar huérfana?
        - Si se eliminó la carpeta alembic/versions manualmente.
        - Si se reseteó la BD sin limpiar el historial de Alembic.
        - Si hubo una migración fallida a mitad de camino.
    """
    logger.info("🔍 Verificando tabla alembic_version...")

    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'alembic_version';")
            existe = cursor.fetchone()

            if existe:
                logger.warning(
                    "⚠️  Tabla alembic_version encontrada — eliminando para reiniciar historial..."
                )
                cursor.execute("DROP TABLE alembic_version;")
                conn.commit()
                logger.info("✅ Tabla alembic_version eliminada correctamente.")
            else:
                logger.info("✅ Tabla alembic_version no encontrada — continuando sin cambios.")
    finally:
        conn.close()


def ejecutar_migracion() -> None:
    """
    Genera una nueva revisión autogenerada y la aplica con upgrade head.
    """
    alembic_cfg = Config("alembic.ini")

    mensaje_revision = f"migracion_auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    logger.info("🔄 Generando revisión autogenerada: '%s'...", mensaje_revision)
    try:
        command.revision(
            alembic_cfg,
            autogenerate=True,
            message=mensaje_revision,
        )
        logger.info("✅ Revisión generada correctamente.")
    except Exception as e:
        raise RuntimeError(f"❌ Error al generar la revisión: {e}")

    logger.info("🚀 Aplicando migración (upgrade head)...")
    try:
        command.upgrade(alembic_cfg, "head")
        logger.info("✅ Migración aplicada correctamente.")
    except Exception as e:
        raise RuntimeError(
            f"❌ Error al aplicar la migración: {e}\n"
            "   Revisá los archivos en alembic/versions/ para detectar conflictos."
        )


# ─────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 55)
    logger.info("  🗄️  INICIO DE MIGRACIÓN — Biblioteca Personal")
    logger.info("=" * 55)

    try:
        verificar_conexion()
        limpiar_alembic_version()
        ejecutar_migracion()

        logger.info("=" * 55)
        logger.info("  ✅  MIGRACIÓN COMPLETADA EXITOSAMENTE")
        logger.info("=" * 55)

    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.exception("❌ Error inesperado durante la migración: %s", e)
        sys.exit(1)
