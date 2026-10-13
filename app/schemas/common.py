"""Common schemas for pagination, errors, etc."""

from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class FilterParams(BaseModel):
    """Common filter parameters for list endpoints."""
    
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    search: Optional[str] = Field(default=None, description="Search query")
    sort_by: Optional[str] = Field(default=None, description="Sort field")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def create(cls, items: list[T], total: int, page: int, page_size: int) -> "PaginatedResponse[T]":
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )


class ErrorResponse(BaseModel):
    """Standard error response."""
    
    error: str
    message: str
    details: Optional[dict] = None
    request_id: Optional[str] = None


class SuccessResponse(BaseModel):
    """Standard success response."""
    
    success: bool = True
    message: str
    data: Optional[Any] = None


class IDResponse(BaseModel):
    """Response with just an ID."""
    
    id: UUID


class BulkActionRequest(BaseModel):
    """Bulk action request."""
    
    ids: list[UUID]
    action: str
    parameters: Optional[dict] = None


class BulkActionResponse(BaseModel):
    """Bulk action response."""
    
    success_count: int
    failed_count: int
    errors: list[dict] = Field(default_factory=list)


class PaginationParams(BaseModel):
    """Common pagination parameters for list endpoints."""
    
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    search: Optional[str] = Field(default=None, description="Search query")
    sort_by: Optional[str] = Field(default=None, description="Sort field")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")