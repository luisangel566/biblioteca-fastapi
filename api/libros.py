"""
api/libros.py
=============
Router CRUD completo para el recurso **Libro**.

MEJORAS respecto a la versión anterior:
  - response_model tipado en todos los endpoints (ya no se usa dict)
  - ETag basado en campos reales del libro (id+titulo+autor+rating+updated_at)
  - Descripción del GET corregida (ya no menciona anio/disponible)
  - Soft delete: DELETE individual y bulk marcan activo=False
  - Bulk delete optimizado con una sola query IN(...)
"""

import hashlib
import logging
from typing import Annotated, List, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    LibroCreate,
    LibroUpdate,
    LibroPatch,
    LibroResponse,
    LibroListResponse,
    DeleteResponse,
    BulkDeleteResponse,
    BulkDeleteData,
    PaginaMeta,
)
from services.libro_service import (
    actualizar_libro,
    crear_libro,
    eliminar_libro,
    eliminar_libros_bulk,
    listar_libros,
    obtener_libro_por_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/libros",
    tags=["Libros"],
)

DbSession = Annotated[Session, Depends(get_db)]
IdLibro = Annotated[int, Path(..., gt=0, description="ID único del libro")]


# ──────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────

def _get_libro_or_404(db: Session, id_libro: int):
    """Devuelve el libro o lanza HTTP 404."""
    libro = obtener_libro_por_id(db, id_libro)
    if libro is None:
        logger.warning("Libro id=%s no encontrado.", id_libro)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "codigo": "LIBRO_NO_ENCONTRADO",
                "mensaje": f"No existe ningún libro con id {id_libro}.",
            },
        )
    return libro


def _calcular_etag(libro) -> str:
    """
    Genera un ETag basado en los campos reales del libro.

    MEJORA: ya no depende solo de updated_at (que antes podía ser None).
    Incluye id + titulo + autor + rating + updated_at para detectar
    cualquier cambio en el contenido.
    """
    updated = libro.updated_at.isoformat() if libro.updated_at else "none"
    contenido = f"{libro.id}-{libro.titulo}-{libro.autor}-{libro.rating}-{updated}"
    return hashlib.md5(contenido.encode()).hexdigest()


def _paginar(total: int, skip: int, limit: int) -> PaginaMeta:
    """Construye los metadatos de paginación tipados."""
    return PaginaMeta(
        total=total,
        skip=skip,
        limit=limit,
        pagina=(skip // limit) + 1 if limit else 1,
        paginas=-(-total // limit) if limit else 1,
        hay_mas=(skip + limit) < total,
    )


# ══════════════════════════════════════════════════════════════
# GET /api/libros
# ══════════════════════════════════════════════════════════════
@router.get(
    "/",
    response_model=LibroListResponse,
    summary="Listar libros",
    description=(
        "Retorna la lista paginada de libros activos. "
        "Acepta filtros opcionales por título, autor y rating. "
        "Los resultados se ordenan por `id` ascendente por defecto. "
        "Los libros eliminados lógicamente (activo=False) no aparecen."
    ),
    responses={
        200: {"description": "Lista de libros obtenida correctamente."},
        422: {"description": "Parámetros de consulta inválidos."},
        500: {"description": "Error interno del servidor."},
    },
)
def listar_libros_endpoint(
    db: DbSession,
    skip: int = Query(0, ge=0, description="Registros a saltar (offset)"),
    limit: int = Query(20, ge=1, le=100, description="Máximo de registros a devolver"),
    titulo: Optional[str] = Query(None, min_length=1, description="Filtro parcial por título"),
    autor: Optional[str] = Query(None, min_length=1, description="Filtro parcial por autor"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filtro exacto por calificación (1-5)"),
    orden: str = Query("id", pattern="^(id|titulo|autor|rating)$", description="Campo por el que ordenar"),
    direccion: str = Query("asc", pattern="^(asc|desc)$", description="Dirección del ordenamiento"),
):
    filtros = {
        "titulo": titulo,
        "autor": autor,
        "rating": rating,
        "orden": orden,
        "direccion": direccion,
    }

    libros, total = listar_libros(db, skip=skip, limit=limit, **filtros)

    logger.info(
        "GET /libros — skip=%s limit=%s filtros=%s → %s/%s.",
        skip, limit, filtros, len(libros), total,
    )

    return LibroListResponse(
        data=libros,
        meta=_paginar(total, skip, limit),
    )


# ══════════════════════════════════════════════════════════════
# POST /api/libros
# ══════════════════════════════════════════════════════════════
@router.post(
    "/",
    response_model=LibroResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear Libro Endpoint",
    description="Crea un nuevo libro con título, autor y rating.",
    responses={
        201: {"description": "Libro creado exitosamente."},
        422: {"description": "Cuerpo de la petición inválido."},
        500: {"description": "Error interno del servidor."},
    },
)
def crear_libro_endpoint(
    datos: Annotated[LibroCreate, Body(...)],
    db: DbSession,
):
    try:
        nuevo = crear_libro(db, datos)
    except IntegrityError:
        db.rollback()
        logger.warning("Error de integridad al crear libro: '%s'.", datos.titulo)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "codigo": "CONFLICTO_BD",
                "mensaje": "Ya existe un libro con los mismos datos.",
            },
        )

    logger.info("Libro creado — id=%s título='%s'.", nuevo.id, nuevo.titulo)
    return LibroResponse(data=nuevo)


# ══════════════════════════════════════════════════════════════
# GET /api/libros/{id_libro}
# ══════════════════════════════════════════════════════════════
@router.get(
    "/{id_libro}",
    response_model=LibroResponse,
    summary="Obtener Libro Endpoint",
    description=(
        "Retorna el detalle completo de un libro activo. "
        "Incluye soporte de caché mediante ETag."
    ),
    responses={
        200: {"description": "Libro encontrado."},
        304: {"description": "Recurso no modificado (ETag coincide)."},
        404: {"description": "Libro no encontrado."},
    },
)
def obtener_libro_endpoint(
    id_libro: IdLibro,
    db: DbSession,
    request: Request,
    response: Response,
):
    libro = _get_libro_or_404(db, id_libro)
    etag = f'"{_calcular_etag(libro)}"'

    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=60"

    logger.info("GET /libros/%s — encontrado.", id_libro)
    return LibroResponse(data=libro)


# ══════════════════════════════════════════════════════════════
# PUT /api/libros/{id_libro}
# ══════════════════════════════════════════════════════════════
@router.put(
    "/{id_libro}",
    response_model=LibroResponse,
    summary="Actualizar Libro Endpoint",
    description=(
        "Reemplaza **todos** los campos del libro con los valores enviados. "
        "Para actualizaciones parciales usa PATCH."
    ),
    responses={
        200: {"description": "Libro actualizado correctamente."},
        404: {"description": "Libro no encontrado."},
        422: {"description": "Cuerpo inválido."},
        500: {"description": "Error interno del servidor."},
    },
)
def actualizar_libro_endpoint(
    id_libro: IdLibro,
    datos: Annotated[LibroUpdate, Body(...)],
    db: DbSession,
):
    _get_libro_or_404(db, id_libro)

    try:
        actualizado = actualizar_libro(db, id_libro, datos)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "codigo": "CONFLICTO_BD",
                "mensaje": "Error de integridad al actualizar el libro.",
            },
        )

    logger.info("PUT /libros/%s — actualizado.", id_libro)
    return LibroResponse(data=actualizado)


# ══════════════════════════════════════════════════════════════
# PATCH /api/libros/{id_libro}
# ══════════════════════════════════════════════════════════════
@router.patch(
    "/{id_libro}",
    response_model=LibroResponse,
    summary="Actualizar libro parcialmente",
    description=(
        "Modifica **solo** los campos enviados en el cuerpo. "
        "Los campos ausentes conservan su valor actual."
    ),
    responses={
        200: {"description": "Libro actualizado parcialmente."},
        404: {"description": "Libro no encontrado."},
        422: {"description": "Cuerpo inválido o vacío."},
    },
)
def parchear_libro_endpoint(
    id_libro: IdLibro,
    datos: Annotated[LibroPatch, Body(...)],
    db: DbSession,
):
    _get_libro_or_404(db, id_libro)

    cambios = datos.model_dump(exclude_unset=True)
    if not cambios:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "codigo": "CUERPO_VACIO",
                "mensaje": "Debes enviar al menos un campo para actualizar.",
            },
        )

    try:
        actualizado = actualizar_libro(db, id_libro, datos)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "codigo": "CONFLICTO_BD",
                "mensaje": "Error de integridad al actualizar el libro.",
            },
        )

    logger.info("PATCH /libros/%s — campos: %s.", id_libro, list(cambios.keys()))
    return LibroResponse(data=actualizado)


# ══════════════════════════════════════════════════════════════
# DELETE /api/libros/{id_libro}  — soft delete individual
# ══════════════════════════════════════════════════════════════
@router.delete(
    "/{id_libro}",
    response_model=DeleteResponse,
    summary="Eliminar libro",
    description=(
        "Elimina lógicamente un libro (soft delete). "
        "El registro permanece en la BD con activo=False — "
        "no aparece en listados pero puede recuperarse."
    ),
    responses={
        200: {"description": "Libro eliminado."},
        404: {"description": "Libro no encontrado."},
    },
)
def eliminar_libro_endpoint(
    id_libro: IdLibro,
    db: DbSession,
):
    _get_libro_or_404(db, id_libro)
    eliminar_libro(db, id_libro)

    logger.info("DELETE /libros/%s — soft deleted.", id_libro)

    return DeleteResponse(data={
        "mensaje": f"El libro con id {id_libro} fue eliminado correctamente.",
        "id_eliminado": id_libro,
    })


# ══════════════════════════════════════════════════════════════
# DELETE /api/libros  — soft delete en lote
# ══════════════════════════════════════════════════════════════
@router.delete(
    "/",
    response_model=BulkDeleteResponse,
    summary="Eliminar múltiples libros (bulk)",
    description=(
        "Elimina lógicamente una lista de libros en una sola operación. "
        "Usa una única query optimizada (WHERE id IN ...). "
        "Si algún id no existe o ya estaba inactivo, se reporta en `no_encontrados`."
    ),
    responses={
        200: {"description": "Operación bulk completada."},
        422: {"description": "Lista de ids inválida o vacía."},
    },
)
def eliminar_libros_bulk_endpoint(
    ids: Annotated[
        List[int],
        Body(
            ...,
            min_length=1,
            examples=[[1, 2, 3]],
            description="Lista de ids de libros a eliminar.",
        ),
    ],
    db: DbSession,
):
    if not ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "codigo": "LISTA_VACIA",
                "mensaje": "Debes enviar al menos un id.",
            },
        )

    if len(ids) != len(set(ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "codigo": "IDS_DUPLICADOS",
                "mensaje": "La lista de ids contiene duplicados.",
            },
        )

    eliminados, no_encontrados = eliminar_libros_bulk(db, ids)

    logger.info(
        "DELETE /libros (bulk) — eliminados=%s no_encontrados=%s.",
        eliminados, no_encontrados,
    )

    return BulkDeleteResponse(data=BulkDeleteData(
        eliminados=eliminados,
        no_encontrados=no_encontrados,
        total_enviados=len(ids),
    ))
