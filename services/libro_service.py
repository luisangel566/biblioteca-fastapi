# services/libro_service.py
# Capa de servicios encargada de la lógica de negocio relacionada con libros.
#
# MEJORAS respecto a la versión anterior:
#   - listar_libros    → filtra solo libros activos (soft delete)
#   - eliminar_libro   → soft delete (activo=False) en vez de borrado físico
#   - eliminar_libros_bulk → una sola query IN(...) en vez de N queries individuales
#   - actualizar_libro → acepta LibroUpdate y LibroPatch (Union)

import logging
from typing import List, Optional, Union

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from models.libro import Libro
from schemas import LibroCreate, LibroUpdate, LibroPatch

logger = logging.getLogger(__name__)

_COLUMNAS_ORDEN_VALIDAS = {"id", "titulo", "autor", "rating"}


# ─────────────────────────────────────────────────────────────
# listar_libros
# ─────────────────────────────────────────────────────────────
def listar_libros(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    titulo: Optional[str] = None,
    autor: Optional[str] = None,
    rating: Optional[int] = None,
    orden: str = "id",
    direccion: str = "asc",
) -> tuple:
    """
    Devuelve (lista_libros, total) con filtros, paginación y orden.

    MEJORA: solo retorna libros con activo=True (respeta el soft delete).
    """
    # Filtro base: solo libros activos
    query = db.query(Libro).filter(Libro.activo.is_(True))

    if titulo:
        query = query.filter(Libro.titulo.ilike(f"%{titulo}%"))
    if autor:
        query = query.filter(Libro.autor.ilike(f"%{autor}%"))
    if rating is not None:
        query = query.filter(Libro.rating == rating)

    total = query.count()

    if orden not in _COLUMNAS_ORDEN_VALIDAS:
        logger.warning("listar_libros → Columna '%s' no válida, usando 'id'.", orden)
        orden = "id"

    columna = getattr(Libro, orden)
    query = query.order_by(asc(columna) if direccion == "asc" else desc(columna))

    libros = query.offset(skip).limit(limit).all()

    logger.info(
        "listar_libros → %s/%s libro(s) (skip=%s limit=%s orden=%s %s).",
        len(libros), total, skip, limit, orden, direccion,
    )
    return libros, total


# ─────────────────────────────────────────────────────────────
# crear_libro
# ─────────────────────────────────────────────────────────────
def crear_libro(db: Session, datos: LibroCreate) -> Libro:
    """Crea un nuevo libro en la base de datos."""
    nuevo_libro = Libro(
        titulo=datos.titulo,
        autor=datos.autor,
        rating=datos.rating,
    )
    db.add(nuevo_libro)
    db.commit()
    db.refresh(nuevo_libro)

    logger.info("crear_libro → id=%s '%s'.", nuevo_libro.id, nuevo_libro.titulo)
    return nuevo_libro


# ─────────────────────────────────────────────────────────────
# obtener_libro_por_id
# ─────────────────────────────────────────────────────────────
def obtener_libro_por_id(db: Session, id_libro: int) -> Optional[Libro]:
    """
    Busca un libro por id.
    Solo retorna libros activos — los soft-deleted no son visibles.
    """
    libro = (
        db.query(Libro)
        .filter(Libro.id == id_libro, Libro.activo.is_(True))
        .first()
    )

    if libro is None:
        logger.warning("obtener_libro_por_id → id=%s no encontrado.", id_libro)
    else:
        logger.info("obtener_libro_por_id → id=%s '%s'.", libro.id, libro.titulo)

    return libro


# ─────────────────────────────────────────────────────────────
# actualizar_libro
# ─────────────────────────────────────────────────────────────
def actualizar_libro(
    db: Session,
    id_libro: int,
    datos: Union[LibroUpdate, LibroPatch],
) -> Optional[Libro]:
    """
    Actualiza parcialmente un libro existente.
    Acepta tanto LibroUpdate (PUT) como LibroPatch (PATCH).
    Solo actualiza campos distintos de None.
    """
    libro = obtener_libro_por_id(db, id_libro)
    if libro is None:
        return None

    if datos.titulo is not None:
        libro.titulo = datos.titulo
    if datos.autor is not None:
        libro.autor = datos.autor
    if datos.rating is not None:
        libro.rating = datos.rating

    db.commit()
    db.refresh(libro)

    logger.info("actualizar_libro → id=%s actualizado.", libro.id)
    return libro


# ─────────────────────────────────────────────────────────────
# eliminar_libro  —  soft delete individual
# ─────────────────────────────────────────────────────────────
def eliminar_libro(db: Session, id_libro: int) -> Optional[bool]:
    """
    Elimina lógicamente un libro (soft delete).

    MEJORA: en vez de DELETE físico, marca activo=False.
    El registro permanece en la BD para historial y auditoría.
    Se puede restaurar cambiando activo=True directamente en la BD.

    Retorna:
        True  → eliminado correctamente.
        None  → no existe el libro.
    """
    libro = obtener_libro_por_id(db, id_libro)
    if libro is None:
        return None

    libro.activo = False
    db.commit()

    logger.info("eliminar_libro → id=%s marcado como inactivo.", id_libro)
    return True


# ─────────────────────────────────────────────────────────────
# eliminar_libros_bulk  —  soft delete múltiple optimizado
# ─────────────────────────────────────────────────────────────
def eliminar_libros_bulk(
    db: Session,
    ids: List[int],
) -> tuple:
    """
    Elimina lógicamente varios libros en una sola operación.

    MEJORA: usa una sola query IN(...) para obtener todos los libros
    en vez de N queries individuales — mucho más eficiente con listas grandes.

    Retorna:
        tuple: (eliminados, no_encontrados)
            eliminados      → List[int] ids marcados como inactivos.
            no_encontrados  → List[int] ids que no existían o ya estaban inactivos.
    """
    # Una sola query para traer todos los libros activos de la lista
    libros_encontrados = (
        db.query(Libro)
        .filter(Libro.id.in_(ids), Libro.activo.is_(True))
        .all()
    )

    ids_encontrados = {libro.id for libro in libros_encontrados}
    ids_no_encontrados = [i for i in ids if i not in ids_encontrados]

    # Marcar todos como inactivos en memoria, un solo commit al final
    for libro in libros_encontrados:
        libro.activo = False

    db.commit()

    eliminados = list(ids_encontrados)

    logger.info(
        "eliminar_libros_bulk → eliminados=%s no_encontrados=%s.",
        eliminados, ids_no_encontrados,
    )
    return eliminados, ids_no_encontrados
