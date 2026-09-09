from __future__ import annotations

import asyncio

from backend.app.services import tools


def test_configured_mcp_tool_is_listed_and_called(monkeypatch):
    monkeypatch.setenv(
        "MCP_TOOLS_JSON",
        '[{"server":"crm","url":"https://mcp.example/rpc","tool_name":"company_lookup","name":"Company Lookup"}]',
    )
    registered = tools.list_tools("local_default_user")
    assert any(item["tool_id"] == "mcp:crm:company_lookup" for item in registered)

    async def fake_call(config, arguments):
        assert config.remote_name == "company_lookup"
        assert arguments == {"company": "DeepFlow"}
        return {"content": [{"type": "text", "text": "matched"}]}

    monkeypatch.setattr(tools, "call_mcp_tool", fake_call)
    result = asyncio.run(
        tools.test_tool(
            "mcp:crm:company_lookup",
            {"arguments": {"company": "DeepFlow"}},
            {"user_id": "local_default_user"},
        )
    )
    assert result["success"] is True
    assert "matched" in result["output_summary"]
