"""
schemas.py

Define los esquemas Pydantic para validación de datos de entrada y salida
relacionados con el modelo Libro.

Jerarquía de schemas:
    LibroBase        → Campos y validaciones comunes (titulo, autor, rating)
        ├── LibroCreate  → Creación: todos los campos son obligatorios
        ├── LibroUpdate  → Reemplazo completo (PUT): todos los campos son obligatorios
        └── LibroPatch   → Actualización parcial (PATCH): todos los campos son opcionales

    LibroRead        → Respuesta de la API: incluye id, timestamps y activo
    LibroResponse    → Envelope { data: LibroRead }
    LibroListResponse→ Envelope { data: [...], meta: PaginaMeta }
    BulkDeleteData   → Detalle del resultado bulk
    BulkDeleteResponse → Envelope { data: BulkDeleteData }
    DeleteResponse   → Envelope { data: { mensaje, id_eliminado } }

MEJORAS respecto a la versión anterior:
    - Response wrappers tipados (ya no se usa `dict` como response_model).
    - LibroRead incluye `activo` para reflejar el soft delete.
    - Timestamps ahora son obligatorios (la BD siempre los provee).
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ══════════════════════════════════════════════════════════════
# VALIDADORES REUTILIZABLES
# ══════════════════════════════════════════════════════════════

def _limpiar_texto(valor: Optional[str]) -> Optional[str]:
    """Elimina espacios extremos y valida que el string no esté vacío."""
    if valor is None:
        return valor
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(
            "El campo no puede estar vacío ni contener solo espacios en blanco."
        )
    return valor.strip()


# ══════════════════════════════════════════════════════════════
# BASE
# ══════════════════════════════════════════════════════════════
class LibroBase(BaseModel):
    """Schema base con campos y validaciones comunes."""

    titulo: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Título del libro. No puede estar vacío ni superar 255 caracteres.",
        examples=["Cien años de soledad"],
    )
    autor: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nombre del autor. No puede estar vacío ni superar 255 caracteres.",
        examples=["Gabriel García Márquez"],
    )
    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Calificación del libro entre 1 y 5 inclusive.",
        examples=[4],
    )

    @field_validator("titulo", "autor", mode="before")
    @classmethod
    def no_solo_espacios(cls, valor: str) -> str:
        return _limpiar_texto(valor)  # type: ignore[return-value]


# ══════════════════════════════════════════════════════════════
# CREACIÓN  —  POST /api/libros
# ══════════════════════════════════════════════════════════════
class LibroCreate(LibroBase):
    """
    Schema para crear un nuevo libro.
    Todos los campos (titulo, autor, rating) son obligatorios.
    """
    pass


# ══════════════════════════════════════════════════════════════
# REEMPLAZO COMPLETO  —  PUT /api/libros/{id}
# ══════════════════════════════════════════════════════════════
class LibroUpdate(LibroBase):
    """
    Schema para reemplazar un libro completo (PUT).
    Todos los campos son obligatorios.
    """
    pass


# ══════════════════════════════════════════════════════════════
# ACTUALIZACIÓN PARCIAL  —  PATCH /api/libros/{id}
# ══════════════════════════════════════════════════════════════
class LibroPatch(BaseModel):
    """
    Schema para actualización parcial de un libro (PATCH).
    Todos los campos son opcionales — solo se modifican los enviados.
    """

    titulo: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Nuevo título del libro. Opcional.",
        examples=["El otoño del patriarca"],
    )
    autor: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Nuevo nombre del autor. Opcional.",
        examples=["Gabriel García Márquez"],
    )
    rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Nueva calificación entre 1 y 5. Opcional.",
        examples=[3],
    )

    @field_validator("titulo", "autor", mode="before")
    @classmethod
    def no_solo_espacios(cls, valor: Optional[str]) -> Optional[str]:
        return _limpiar_texto(valor)

    @model_validator(mode="after")
    def al_menos_un_campo(self) -> "LibroPatch":
        """Garantiza que el body de PATCH no llegue completamente vacío."""
        if all(v is None for v in (self.titulo, self.autor, self.rating)):
            raise ValueError(
                "Debes enviar al menos un campo para actualizar (titulo, autor o rating)."
            )
        return self


# ══════════════════════════════════════════════════════════════
# LECTURA / RESPUESTA  —  GET, POST, PUT, PATCH
# ══════════════════════════════════════════════════════════════
class LibroRead(BaseModel):
    """
    Schema de respuesta para un libro individual.

    MEJORAS:
        - `activo` refleja si el libro fue eliminado lógicamente.
        - `created_at` y `updated_at` son reales (vienen de la BD).

    Ejemplo de respuesta JSON:
        {
            "id":         1,
            "titulo":     "Cien años de soledad",
            "autor":      "Gabriel García Márquez",
            "rating":     5,
            "activo":     true,
            "created_at": "2024-01-15T10:30:00",
            "updated_at": "2024-01-15T10:30:00"
        }
    """

    id: int = Field(description="Identificador único generado por la base de datos.")
    titulo: str = Field(description="Título del libro.")
    autor: str = Field(description="Nombre del autor del libro.")
    rating: int = Field(description="Calificación del libro entre 1 y 5.")
    activo: bool = Field(description="False si el libro fue eliminado lógicamente.")

    created_at: Optional[datetime] = Field(
        default=None,
        description="Fecha y hora de creación del registro (UTC).",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Fecha y hora de la última actualización (UTC).",
    )

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )


# ══════════════════════════════════════════════════════════════
# RESPONSE WRAPPERS TIPADOS
# MEJORA: reemplazan `response_model=dict` en todos los endpoints.
# El Swagger ahora muestra el schema exacto de cada respuesta.
# ══════════════════════════════════════════════════════════════

class LibroResponse(BaseModel):
    """Envelope para respuestas de un solo libro."""
    data: LibroRead


class DeleteData(BaseModel):
    """Datos de respuesta al eliminar un libro individual."""
    mensaje: str
    id_eliminado: int


class DeleteResponse(BaseModel):
    """Envelope para respuesta de DELETE individual."""
    data: DeleteData


# ══════════════════════════════════════════════════════════════
# RESPUESTA PAGINADA  —  GET /api/libros
# ══════════════════════════════════════════════════════════════
class PaginaMeta(BaseModel):
    """Metadatos de paginación incluidos en respuestas de listas."""

    total: int = Field(description="Total de registros que cumplen los filtros.")
    skip: int = Field(description="Registros saltados (offset).")
    limit: int = Field(description="Máximo de registros por página.")
    pagina: int = Field(description="Número de página actual (base 1).")
    paginas: int = Field(description="Total de páginas disponibles.")
    hay_mas: bool = Field(description="Indica si existe al menos una página siguiente.")


class LibroListResponse(BaseModel):
    """Envelope para respuesta paginada de lista de libros."""
    data: List[LibroRead]
    meta: PaginaMeta


# ══════════════════════════════════════════════════════════════
# RESULTADO BULK DELETE  —  DELETE /api/libros
# ══════════════════════════════════════════════════════════════
class BulkDeleteData(BaseModel):
    """Detalle del resultado de eliminación en lote."""

    eliminados: List[int] = Field(
        description="IDs que fueron eliminados correctamente.",
    )
    no_encontrados: List[int] = Field(
        description="IDs que no existían en la base de datos.",
    )
    total_enviados: int = Field(
        description="Total de IDs recibidos en la petición.",
    )


class BulkDeleteResponse(BaseModel):
    """Envelope para respuesta del bulk delete."""
    data: BulkDeleteData


# Alias de compatibilidad con código anterior
BulkDeleteResult = BulkDeleteData
LibroListRead = LibroListResponse
