"""Integration tests for v1.1 tool-use + feedback features."""
import os
import tempfile
import pytest
from cli.tools.setup import create_default_registry
from cli.tools.parser import parse_tool_calls
from cli.feedback import FeedbackStore


def test_full_tool_registry():
    """All 6 tools are registered."""
    reg = create_default_registry()
    tools = reg.list_tools()
    assert "file_read" in tools
    assert "file_write" in tools
    assert "shell_exec" in tools
    assert "web_fetch" in tools
    assert "memory_query" in tools
    assert "python_eval" in tools
    assert len(tools) == 6


def test_tool_prompt_includes_all():
    """Tool prompt describes all tools for LLM."""
    reg = create_default_registry()
    prompt = reg.tool_prompt()
    assert "TOOL:" in prompt
    for name in reg.list_tools():
        assert name in prompt


def test_parse_and_dispatch():
    """Parse a tool call from text and dispatch it."""
    reg = create_default_registry()
    text = "Ich rechne das aus.\nTOOL: python_eval(code=2+3)"
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    result = reg.dispatch(calls[0].name, calls[0].args)
    assert result.success is True
    assert "5" in result.output


def test_feedback_roundtrip():
    """Store and retrieve feedback."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        store = FeedbackStore(f.name)
        store.record("test", "antwort", 1, model="qwen-coder")
        entries = store.load_all()
        assert len(entries) == 1
        assert entries[0]["model"] == "qwen-coder"
    os.unlink(f.name)
