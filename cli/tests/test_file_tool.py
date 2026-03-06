"""Tests for file_tool — read/write with path whitelist security."""
from __future__ import annotations
import os
import tempfile

from cli.tools.file_tool import make_file_read_tool, make_file_write_tool


def test_file_read_allowed_path():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "hello.txt")
        with open(p, "w") as f:
            f.write("Hallo Welt")
        tool = make_file_read_tool([td])
        result = tool.handler(path=p)
        assert result.success is True
        assert result.output == "Hallo Welt"


def test_file_read_blocked_path():
    tool = make_file_read_tool(["/tmp/safe"])
    result = tool.handler(path="/etc/passwd")
    assert result.success is False
    assert "nicht erlaubt" in result.output


def test_file_read_path_traversal():
    tool = make_file_read_tool(["/tmp/safe"])
    result = tool.handler(path="/tmp/safe/../../etc/passwd")
    assert result.success is False
    assert "nicht erlaubt" in result.output


def test_file_write_allowed():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "out.txt")
        tool = make_file_write_tool([td])
        result = tool.handler(path=p, content="Test123")
        assert result.success is True
        assert "Geschrieben" in result.output
        with open(p) as f:
            assert f.read() == "Test123"


def test_file_write_blocked():
    tool = make_file_write_tool(["/tmp/safe"])
    result = tool.handler(path="/etc/evil.txt", content="nope")
    assert result.success is False
    assert "nicht erlaubt" in result.output
