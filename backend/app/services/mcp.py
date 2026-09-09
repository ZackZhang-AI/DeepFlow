"""Environment-configured MCP Streamable HTTP tool client."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class MCPToolConfig:
    tool_id: str
    name: str
    description: str
    url: str
    remote_name: str
    auth_env: str = ""


def configured_mcp_tools() -> list[MCPToolConfig]:
    raw = os.getenv("MCP_TOOLS_JSON", "[]").strip() or "[]"
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []
    result: list[MCPToolConfig] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        remote_name = str(item.get("tool_name") or "").strip()
        server = str(item.get("server") or "remote").strip().replace(":", "-")
        if urlparse(url).scheme not in {"http", "https"} or not remote_name:
            continue
        result.append(
            MCPToolConfig(
                tool_id=f"mcp:{server}:{remote_name}",
                name=str(item.get("name") or remote_name),
                description=str(item.get("description") or f"MCP tool {remote_name}"),
                url=url,
                remote_name=remote_name,
                auth_env=str(item.get("auth_env") or ""),
            )
        )
    return result


async def call_mcp_tool(config: MCPToolConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    token = os.getenv(config.auth_env, "").strip() if config.auth_env else ""
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        initialized = await client.post(
            config.url,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "DeepFlow", "version": "0.1.0"},
                },
            },
        )
        initialized.raise_for_status()
        init_payload = _response_payload(initialized)
        if init_payload.get("error"):
            raise RuntimeError(f"MCP initialize failed: {init_payload['error']}")
        session_id = initialized.headers.get("mcp-session-id", "")
        session_headers = {**headers, **({"mcp-session-id": session_id} if session_id else {})}
        await client.post(
            config.url,
            headers=session_headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        response = await client.post(
            config.url,
            headers=session_headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": config.remote_name, "arguments": arguments},
            },
        )
        response.raise_for_status()
    payload = _response_payload(response)
    if payload.get("error"):
        raise RuntimeError(f"MCP tool call failed: {payload['error']}")
    return payload.get("result") or {}


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    if "text/event-stream" not in response.headers.get("content-type", ""):
        return response.json() if response.content else {}
    for line in reversed(response.text.splitlines()):
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return {}
