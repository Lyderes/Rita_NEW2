from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T] = Field(description="Current page items.")
    total: int = Field(description="Total number of records for the applied filters.", examples=[125])
    limit: int = Field(description="Requested page size.", examples=[50])
    offset: int = Field(description="Pagination offset.", examples=[0])
