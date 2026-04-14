"""Custom SQLAlchemy column types."""

from __future__ import annotations

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    """Minimal pgvector column type — DDL-only.

    Avoids the optional `pgvector` Python package. Sufficient for migrations
    and DDL; reads/writes of embeddings are handled via raw SQL casts
    (e.g. ``::vector(1024)``) at call sites until week 2 when the embedding
    backend is chosen.
    """

    cache_ok = True

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def get_col_spec(self, **kw: object) -> str:  # noqa: ARG002
        return f"VECTOR({self.dim})"
