"""
Unified API response schemas for OpenAPI documentation.

All endpoints should use these models via `response_model` to ensure
consistent and well-documented API responses.
"""

from typing import Any, Optional, TypeVar, Generic
from pydantic import BaseModel, Field
from datetime import datetime


class ErrorDetail(BaseModel):
    """Single validation error detail."""
    loc: list[str] = Field(
        default_factory=list,
        description="Location of the error (field path).",
        examples=[["body", "username"]],
    )
    msg: str = Field(
        description="Human-readable error message.",
        examples=["field required"],
    )
    type: str = Field(
        description="Error type code.",
        examples=["value_error.missing"],
    )


class HTTPError(BaseModel):
    """Standard HTTP error response (non-validation errors)."""
    detail: str = Field(
        description="Human-readable error description.",
        examples=["Invalid credentials"],
    )


class ValidationError(BaseModel):
    """Pydantic validation error response (422)."""
    detail: list[ErrorDetail] = Field(
        description="List of validation errors.",
    )


class MessageResponse(BaseModel):
    """Simple success message response."""
    message: str = Field(
        description="Success message.",
        examples=["Operation completed successfully"],
    )


class DeleteResponse(BaseModel):
    """Response for delete operations."""
    message: str = Field(
        default="Deleted successfully",
        examples=["Deleted successfully"],
    )
    deleted_id: Optional[str] = Field(
        default=None,
        description="ID of the deleted resource.",
        examples=["srv1"],
    )
    deleted_count: Optional[int] = Field(
        default=None,
        description="Number of deleted items (for batch operations).",
        examples=[3],
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(
        description="Overall health status.",
        examples=["ok", "degraded"],
    )
    database: str = Field(
        description="Database connectivity status.",
        examples=["ok", "error"],
    )
    version: str = Field(
        default="0.0.0",
        description="Application version (read from VERSION file at runtime).",
    )


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    items: list[T] = Field(
        description="List of items for the current page.",
    )
    total: int = Field(
        description="Total number of items.",
        examples=[42],
    )
    page: int = Field(
        default=1,
        description="Current page number (1-based).",
        ge=1,
    )
    page_size: int = Field(
        default=20,
        description="Number of items per page.",
        ge=1,
        le=100,
    )
    total_pages: int = Field(
        default=1,
        description="Total number of pages.",
        ge=0,
    )


# ---- Common HTTP status code descriptions for OpenAPI `responses` parameter ----

# Reusable response definitions
RESPONSE_401: dict = {
    401: {
        "description": "Authentication required — token missing, invalid, or expired.",
        "model": HTTPError,
    }
}

RESPONSE_403: dict = {
    403: {
        "description": "Permission denied — insufficient role or resource access.",
        "model": HTTPError,
    }
}

RESPONSE_404: dict = {
    404: {
        "description": "Resource not found.",
        "model": HTTPError,
    }
}

RESPONSE_422: dict = {
    422: {
        "description": "Validation error — request body or parameters invalid.",
        "model": ValidationError,
    }
}

RESPONSE_500: dict = {
    500: {
        "description": "Internal server error.",
        "model": HTTPError,
    }
}

# Combined: auth errors (401 + 403)
RESPONSE_AUTH: dict = {**RESPONSE_401, **RESPONSE_403}

# Combined: standard CRUD errors (401 + 403 + 404 + 422 + 500)
RESPONSE_STANDARD: dict = {**RESPONSE_401, **RESPONSE_403, **RESPONSE_404, **RESPONSE_422, **RESPONSE_500}
