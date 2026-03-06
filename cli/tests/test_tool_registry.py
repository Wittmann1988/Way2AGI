"""Tests for tool registry and dispatcher."""
import pytest
from cli.tools.registry import ToolRegistry, Tool, ToolResult


def test_register_and_list():
    reg = ToolRegistry()
    reg.register(Tool(
        name="test_tool",
        description="A test tool",
        parameters={"query": "str"},
        handler=lambda query: ToolResult(success=True, output=f"got {query}"),
    ))
    assert "test_tool" in reg.list_tools()
    assert len(reg.list_tools()) == 1


def test_dispatch_known_tool():
    reg = ToolRegistry()
    reg.register(Tool(
        name="echo",
        description="Echo input",
        parameters={"text": "str"},
        handler=lambda text: ToolResult(success=True, output=text),
    ))
    result = reg.dispatch("echo", {"text": "hello"})
    assert result.success is True
    assert result.output == "hello"


def test_dispatch_unknown_tool():
    reg = ToolRegistry()
    result = reg.dispatch("nonexistent", {})
    assert result.success is False
    assert "unbekannt" in result.output.lower()


def test_tool_descriptions_for_prompt():
    reg = ToolRegistry()
    reg.register(Tool(
        name="file_read",
        description="Datei lesen",
        parameters={"path": "str"},
        handler=lambda path: ToolResult(success=True, output=""),
    ))
    reg.register(Tool(
        name="shell",
        description="Shell-Befehl",
        parameters={"command": "str"},
        handler=lambda command: ToolResult(success=True, output=""),
    ))
    prompt = reg.tool_prompt()
    assert "file_read" in prompt
    assert "shell" in prompt
    assert "TOOL:" in prompt
