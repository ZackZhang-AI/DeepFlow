"""System readiness API."""

from fastapi import APIRouter, Query

from backend.app.core.readiness import get_readiness

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/readiness")
async def system_readiness(probe: bool = Query(default=False)):
    return await get_readiness(probe=probe)
