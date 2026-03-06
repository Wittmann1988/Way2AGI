"""Tests for cli.tools.parser."""

from cli.tools.parser import parse_tool_calls


def test_parse_single_tool_call():
    text = "TOOL: file_read(path=/tmp/test.txt)"
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "file_read"
    assert calls[0].args == {"path": "/tmp/test.txt"}


def test_parse_multiple_args():
    text = "TOOL: web_fetch(url=https://example.com, timeout=10)"
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].args == {"url": "https://example.com", "timeout": "10"}


def test_parse_no_tool_call():
    text = "This is just normal text with no tool calls."
    calls = parse_tool_calls(text)
    assert len(calls) == 0


def test_parse_quoted_args():
    text = 'TOOL: shell_exec(command="ls -la /tmp")'
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].args["command"] == "ls -la /tmp"


def test_parse_multiple_tool_calls():
    text = "TOOL: file_read(path=/a.txt)\nTOOL: file_write(path=/b.txt, content=hello)"
    calls = parse_tool_calls(text)
    assert len(calls) == 2
    assert calls[0].name == "file_read"
    assert calls[1].name == "file_write"


def test_extract_text_before_tool():
    text = "Let me read that file for you.\nTOOL: file_read(path=/tmp/test.txt)"
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].prefix == "Let me read that file for you."
