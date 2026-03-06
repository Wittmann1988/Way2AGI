"""Tool Registry — registers tools and dispatches calls."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolResult:
    success: bool
    output: str


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, str]  # name -> type hint
    handler: Callable[..., ToolResult]


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def dispatch(self, name: str, args: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(success=False, output=f"Tool unbekannt: {name}")
        try:
            return tool.handler(**args)
        except Exception as e:
            return ToolResult(success=False, output=f"Fehler: {e}")

    def tool_prompt(self) -> str:
        """Generate tool description block for LLM system prompt."""
        lines = [
            "Du hast folgende Tools zur Verfuegung.",
            "Nutze sie mit: TOOL: name(arg1=wert1, arg2=wert2)",
            "Warte auf das Ergebnis bevor du antwortest.",
            "",
        ]
        for tool in self._tools.values():
            params = ", ".join(f"{k}: {v}" for k, v in tool.parameters.items())
            lines.append(f"- {tool.name}({params}): {tool.description}")
        return "\n".join(lines)
