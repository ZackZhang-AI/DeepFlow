"""System readiness API."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.core.auth import get_current_user
from backend.app.core.rate_limit import check_rate_limit
from backend.app.core.readiness import get_readiness
from backend.app.core.runtime_config import readiness_probe_rate_limit

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/readiness")
async def system_readiness(
    probe: bool = Query(default=False),
    user: Annotated[Optional[dict], Depends(get_current_user)] = None,
):
    if probe:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for a live provider probe",
            )
        check_rate_limit("readiness.probe", user["user_id"], readiness_probe_rate_limit())
    return await get_readiness(probe=probe)
