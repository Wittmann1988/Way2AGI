"""Tests for web_tool and memory_tool."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from cli.tools.web_tool import _is_url_safe, make_web_fetch_tool
from cli.tools.memory_tool import _format_results, make_memory_query_tool


def test_web_fetch_blocked_url():
    """Link-local IP 169.254.x.x must be blocked."""
    safe, reason = _is_url_safe("http://169.254.169.254/latest/meta-data/")
    assert not safe
    assert "blockiert" in reason.lower() or "blocked" in reason.lower()


def test_web_fetch_invalid_url():
    """A string without scheme must be rejected."""
    safe, reason = _is_url_safe("not-a-url")
    assert not safe


def test_web_fetch_blocked_scheme():
    """file:// scheme must be blocked."""
    safe, reason = _is_url_safe("file:///etc/passwd")
    assert not safe
    assert "schema" in reason.lower() or "scheme" in reason.lower()


def test_memory_query_no_server():
    """Querying a non-existent server should fail gracefully."""
    tool = make_memory_query_tool(base_url="http://localhost:59999")
    result = tool.handler("test query")
    assert not result.success
    assert "Memory-Fehler" in result.output


def test_memory_query_formats_results():
    """_format_results should produce the expected [type|importance] format."""
    mock_data = [
        {"type": "fact", "importance": 0.9, "content": "Python is great"},
        {"type": "event", "importance": 0.5, "content": "Session started"},
    ]
    output = _format_results(mock_data)
    assert "[fact|0.9]" in output
    assert "[event|0.5]" in output
    assert "Python is great" in output
    assert "Session started" in output
    # Empty list
    assert _format_results([]) == "Keine Erinnerungen gefunden."
