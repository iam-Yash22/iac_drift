import math
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class PageParams(BaseModel):
    """Request parameters for paginated queries."""

    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)

    @field_validator("page", "per_page")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be greater than 0")
        return value

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        return self.per_page


class PaginatedResult(BaseModel, Generic[T]):
    """Container for a paginated response."""

    items: list[T]
    page: int
    per_page: int
    total: int
    pages: int

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


def paginate(query: Any, params: PageParams | None = None) -> tuple[Any, PageParams]:
    """Apply LIMIT/OFFSET pagination to a query object.

    This helper is intentionally framework-agnostic; callers are expected to
    pass a query-like object that supports slicing with offset/limit.
    """
    resolved_params = params or PageParams()
    offset = resolved_params.offset
    limit = resolved_params.limit

    if hasattr(query, "offset") and hasattr(query, "limit"):
        return query.offset(offset).limit(limit), resolved_params

    if hasattr(query, "slice"):
        return query.slice(offset, offset + limit), resolved_params

    if hasattr(query, "__getitem__"):
        return query[offset : offset + limit], resolved_params

    raise TypeError("query does not support pagination via offset/limit or slicing")


def paginate_items(items: list[T], params: PageParams | None = None) -> PaginatedResult[T]:
    """Return paginated items with metadata for a list-like collection."""
    resolved_params = params or PageParams()
    total = len(items)
    pages = max(1, math.ceil(total / resolved_params.per_page)) if total else 1

    start = resolved_params.offset
    end = start + resolved_params.per_page
    page_items = items[start:end]

    return PaginatedResult(
        items=page_items,
        page=resolved_params.page,
        per_page=resolved_params.per_page,
        total=total,
        pages=pages,
    )


__all__ = ["PageParams", "PaginatedResult", "paginate", "paginate_items"]
