# models/libro.py
# Modelo SQLAlchemy que representa la tabla 'libros' en la base de datos.

from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from database import Base


class Libro(Base):
    """
    Modelo que representa un libro en la biblioteca personal.

    Tabla en la BD: libros

    Columnas:
        id         → Llave primaria autoincremental.
        titulo     → Título del libro, obligatorio, máximo 255 caracteres.
        autor      → Nombre del autor, obligatorio, máximo 255 caracteres.
        rating     → Calificación del libro, entero entre 1 y 5.
        activo     → Soft delete: False = eliminado lógicamente (no aparece en listados).
        created_at → Fecha de creación, asignada automáticamente por MySQL.
        updated_at → Fecha de última modificación, actualizada automáticamente por MySQL.

    MEJORAS respecto a la versión anterior:
        - Timestamps reales en BD (created_at / updated_at) para auditoría y ETag confiable.
        - Soft delete mediante columna `activo` — los registros nunca se borran físicamente,
          lo que permite recuperación y trazabilidad histórica.
    """

    __tablename__ = "libros"

    # ── Columnas ──────────────────────────────────────────────

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Identificador único del libro",
    )

    titulo = Column(
        String(255),
        nullable=False,
        comment="Título del libro",
    )

    autor = Column(
        String(255),
        nullable=False,
        comment="Nombre del autor del libro",
    )

    rating = Column(
        Integer,
        nullable=False,
        comment="Calificación del libro del 1 al 5",
    )

    # ── Soft delete ───────────────────────────────────────────
    # True  → libro visible y activo en el sistema.
    # False → libro "eliminado" lógicamente — no aparece en listados
    #         pero el registro permanece en la BD para historial.
    activo = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        comment="False indica que el libro fue eliminado lógicamente",
    )

    # ── Timestamps de auditoría ───────────────────────────────
    # MySQL los gestiona automáticamente — no hay que setearlos manualmente.
    # server_default y onupdate delegan la lógica al motor de BD,
    # lo que garantiza consistencia incluso en operaciones directas sobre la BD.

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="Fecha y hora de creación del registro (UTC)",
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Fecha y hora de la última actualización (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"<Libro(id={self.id}, "
            f"titulo='{self.titulo}', "
            f"autor='{self.autor}', "
            f"rating={self.rating}, "
            f"activo={self.activo})>"
        )
