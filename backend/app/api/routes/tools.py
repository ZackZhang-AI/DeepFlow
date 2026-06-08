"""Tool registry API routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.auth import require_login
from backend.app.services.tools import get_tool, list_tools, set_tool_enabled, test_tool

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolToggleRequest(BaseModel):
    enabled: bool


class ToolTestRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


@router.get("")
async def list_registered_tools(user: dict = Depends(require_login)):
    return list_tools()


@router.patch("/{tool_id}")
async def update_tool(tool_id: str, req: ToolToggleRequest, user: dict = Depends(require_login)):
    tool = set_tool_enabled(tool_id, req.enabled)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.post("/{tool_id}/test")
async def test_registered_tool(tool_id: str, req: ToolTestRequest, user: dict = Depends(require_login)):
    if get_tool(tool_id) is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return await test_tool(tool_id, req.input, user)
