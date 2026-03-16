"""Crea tabla libros con campos id, titulo, autor y rating

Revision ID: 657e85c1ad17
Revises:
Create Date: 2026-03-11 14:13:30.179924

Descripcion:
    Migracion inicial del proyecto Biblioteca Personal.
    Crea la tabla 'libros' con los siguientes campos:
        - id     : Entero, llave primaria autoincremental.
        - titulo : Texto obligatorio, maximo 255 caracteres.
        - autor  : Texto obligatorio, maximo 255 caracteres.
        - rating : Entero obligatorio (valor esperado entre 1 y 5).

    Para aplicar esta migracion:
        alembic upgrade head

    Para revertirla:
        alembic downgrade base
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '657e85c1ad17'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on:   Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'libros',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='Identificador unico del libro'),
        sa.Column('titulo', sa.String(length=255), nullable=False, comment='Titulo del libro'),
        sa.Column('autor', sa.String(length=255), nullable=False, comment='Nombre del autor del libro'),
        sa.Column('rating', sa.Integer(), nullable=False, comment='Calificacion del libro del 1 al 5'),
        sa.PrimaryKeyConstraint('id'),
        comment='Catalogo de libros de la biblioteca personal'
    )
    op.create_index(op.f('ix_libros_id'), 'libros', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_libros_id'), table_name='libros')
    op.drop_table('libros')
