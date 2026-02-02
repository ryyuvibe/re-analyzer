"""Property routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/properties", tags=["properties"])


@router.get("/{property_id}")
async def get_property(property_id: UUID):
    """Get a saved property by ID."""
    raise HTTPException(status_code=501, detail="Requires database connection")


@router.get("/{property_id}/history")
async def get_property_history(property_id: UUID):
    """Get price history for a property."""
    raise HTTPException(status_code=501, detail="Requires database connection")
