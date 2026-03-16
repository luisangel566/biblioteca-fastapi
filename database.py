"""
database.py

Centraliza toda la configuración de conexión a la base de datos.
Define el engine, la fábrica de sesiones, la clase Base para los modelos
y la dependencia get_db() para inyección en los endpoints de FastAPI.

Orden de carga:
    1. Lee credenciales desde .env (nunca hardcodeadas en el código).
    2. Construye y valida la URL de conexión.
    3. Crea el engine y la fábrica de sesiones.
    4. Expone get_db() como dependencia reutilizable en toda la API.
"""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, declarative_base

# ─────────────────────────────────────────────────────────────
# LOGGING
# Usamos el logger estándar en lugar de print() para que los
# mensajes respeten el nivel de log configurado en el proyecto.
# ─────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CARGA DE VARIABLES DE ENTORNO
# override=True garantiza que el .env tenga prioridad sobre
# cualquier variable definida previamente en el sistema.
# ─────────────────────────────────────────────────────────────
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

# ─────────────────────────────────────────────────────────────
# LECTURA Y VALIDACIÓN DE VARIABLES DE ENTORNO
# Si alguna variable crítica falta, el error se lanza al iniciar
# la aplicación — no en el primer request, lo cual facilita
# detectar configuraciones incorrectas desde el arranque.
# ─────────────────────────────────────────────────────────────
_env_vars = {
    "DB_USER"    : os.getenv("DB_USER"),
    "DB_PASSWORD": os.getenv("DB_PASSWORD"),
    "DB_HOST"    : os.getenv("DB_HOST"),
    "DB_PORT"    : os.getenv("DB_PORT"),
    "DB_NAME"    : os.getenv("DB_NAME"),
}

_missing = [key for key, value in _env_vars.items() if not value]
if _missing:
    raise RuntimeError(
        f"\n❌ Variables de entorno faltantes: {', '.join(_missing)}\n"
        f"   Verificá que el archivo .env exista en: {_ENV_PATH}\n"
        "   y que contenga todos los valores requeridos.\n"
        "   Ejemplo de contenido esperado:\n"
        "       DB_USER=root\n"
        "       DB_PASSWORD=admin\n"
        "       DB_HOST=localhost\n"
        "       DB_PORT=3306\n"
        "       DB_NAME=biblioteca_db"
    )

# ─────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DE LA URL DE CONEXIÓN
# Formato PyMySQL: mysql+pymysql://usuario:contraseña@host:puerto/bd
# PyMySQL es el conector puro Python para MySQL — no requiere
# instalar el cliente MySQL nativo en el sistema.
# ─────────────────────────────────────────────────────────────
DATABASE_URL = (
    f"mysql+pymysql://{_env_vars['DB_USER']}:{_env_vars['DB_PASSWORD']}"
    f"@{_env_vars['DB_HOST']}:{_env_vars['DB_PORT']}/{_env_vars['DB_NAME']}"
)

# ─────────────────────────────────────────────────────────────
# ENGINE DE SQLALCHEMY
# El engine es el punto de entrada a la base de datos.
# Gestiona el pool de conexiones y traduce las operaciones
# del ORM al dialecto SQL del motor (en este caso MySQL).
#
# echo=False en producción para no exponer las consultas SQL.
# Cambiá a echo=True solo durante desarrollo/depuración.
# ─────────────────────────────────────────────────────────────
_IS_DEV = os.getenv("APP_ENV", "development").lower() == "development"

engine = create_engine(
    DATABASE_URL,
    echo=_IS_DEV,           # True en desarrollo, False en producción
    pool_pre_ping=True,     # Verifica la conexión antes de cada uso (evita conexiones muertas)
    pool_recycle=3600,      # Recicla conexiones cada 1 hora (evita timeouts de MySQL)
    pool_size=5,            # Número de conexiones simultáneas en el pool
    max_overflow=10,        # Conexiones extra permitidas cuando el pool está lleno
)

# ─────────────────────────────────────────────────────────────
# FÁBRICA DE SESIONES
# SessionLocal crea instancias de Session bajo demanda.
# Cada request de FastAPI obtendrá su propia sesión aislada.
#
# autocommit=False → los cambios requieren un commit() explícito
# autoflush=False  → los cambios no se sincronizan automáticamente
#                    con la BD antes de cada query (más control)
# ─────────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# ─────────────────────────────────────────────────────────────
# CLASE BASE PARA MODELOS
# Todos los modelos SQLAlchemy del proyecto heredan de Base.
# Base.metadata contiene el mapa de tablas que Alembic usa
# para detectar cambios y generar migraciones automáticamente.
# ─────────────────────────────────────────────────────────────
Base = declarative_base()


# ─────────────────────────────────────────────────────────────
# DEPENDENCIA get_db()
# FastAPI la inyecta automáticamente en los endpoints que la
# declaren como parámetro con Depends(get_db).
#
# El patrón try/finally garantiza que la sesión se cierre
# siempre, incluso si ocurre una excepción durante el request.
# ─────────────────────────────────────────────────────────────
def get_db():
    """
    Generador que provee una sesión de base de datos por request.

    Uso en un endpoint:
        @router.get("/")
        def mi_endpoint(db: Session = Depends(get_db)):
            ...

    La sesión se abre al inicio del request y se cierra
    automáticamente al finalizar, sin importar si hubo errores.
    """
    db = SessionLocal()
    try:
        yield db        # FastAPI usa la sesión durante el request
    finally:
        db.close()      # Siempre se cierra, incluso si hay excepciones


# ─────────────────────────────────────────────────────────────
# PRUEBA DE CONEXIÓN
# Solo se ejecuta cuando se corre este archivo directamente:
#   python database.py
# Útil para verificar credenciales antes de arrancar la app.
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🔍 Verificando conexión a la base de datos...")
    print(f"   Host   : {_env_vars['DB_HOST']}:{_env_vars['DB_PORT']}")
    print(f"   Base   : {_env_vars['DB_NAME']}")
    print(f"   Usuario: {_env_vars['DB_USER']}")

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            print("\n✅ Conexión exitosa — la base de datos está disponible.\n")
    except OperationalError as e:
        print(
            f"\n❌ No se pudo conectar a la base de datos.\n"
            f"   Verificá que MySQL esté corriendo y que las credenciales sean correctas.\n"
            f"   Detalle del error: {e}\n"
        )