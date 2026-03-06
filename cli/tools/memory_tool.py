from __future__ import annotations
from typing import Any
from cli.tools.registry import Tool, ToolResult

def _format_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "Keine Erinnerungen gefunden."
    lines = []
    for r in results:
        typ = r.get("type", "?")
        imp = r.get("importance", 0)
        content = r.get("content", "")[:200]
        lines.append(f"[{typ}|{imp:.1f}] {content}")
    return "\n".join(lines)

def make_memory_query_tool(base_url: str = "http://localhost:5000") -> Tool:
    def handler(query: str, memory_type: str = "all", top_k: str = "5") -> ToolResult:
        try:
            import httpx
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(f"{base_url}/memory/query", json={"query": query, "memory_type": memory_type, "top_k": int(top_k)})
                resp.raise_for_status()
                return ToolResult(success=True, output=_format_results(resp.json()))
        except Exception as e:
            return ToolResult(success=False, output=f"Memory-Fehler: {e}")
    return Tool(name="memory_query", description="Gedaechtnis durchsuchen (semantische Suche)", parameters={"query": "str", "memory_type": "str (default: all)", "top_k": "str (default: 5)"}, handler=handler)
