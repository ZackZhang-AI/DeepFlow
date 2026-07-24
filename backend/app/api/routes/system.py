"""System readiness API."""

from fastapi import APIRouter

from backend.app.core.readiness import get_readiness

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/readiness")
async def system_readiness():
    return await get_readiness()
