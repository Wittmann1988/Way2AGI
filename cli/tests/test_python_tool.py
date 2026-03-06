"""Tests for the sandboxed Python eval tool."""
from cli.tools.python_tool import make_python_eval_tool


tool = make_python_eval_tool()


def test_eval_simple_math():
    result = tool.handler(code="2 + 3 * 4")
    assert result.success is True
    assert result.output == "14"


def test_eval_string_ops():
    result = tool.handler(code="'hello'.upper()")
    assert result.success is True
    assert result.output == "'HELLO'"


def test_eval_block_import():
    result = tool.handler(code="import os; os.system('rm -rf /')")
    assert result.success is False
    assert "Blockiert" in result.output


def test_eval_block_exec():
    result = tool.handler(code="exec('print(1)')")
    assert result.success is False
    assert "Blockiert" in result.output


def test_eval_block_open():
    result = tool.handler(code="open('/etc/passwd').read()")
    assert result.success is False
    assert "Blockiert" in result.output


def test_eval_block_dunder():
    result = tool.handler(code="''.__class__.__mro__[1].__subclasses__()")
    assert result.success is False
    assert "Blockiert" in result.output


def test_eval_multiline():
    result = tool.handler(code="x = 5\ny = 10\nprint(x + y)")
    assert result.success is True
    assert result.output == "15"
