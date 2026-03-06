"""Tests for Way2AGI LLM Client."""
import pytest
from cli.llm_client import LLMClient


def test_build_headers_openrouter():
    client = LLMClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        provider="openrouter",
    )
    headers = client._build_headers()
    assert headers["Authorization"] == "Bearer test-key"
    assert "HTTP-Referer" in headers
    assert headers["X-Title"] == "Way2AGI"


def test_build_headers_anthropic():
    client = LLMClient(
        base_url="https://api.anthropic.com/v1",
        api_key="test-key",
        provider="anthropic",
    )
    headers = client._build_headers()
    assert headers["x-api-key"] == "test-key"
    assert "anthropic-version" in headers
    assert "Authorization" not in headers


def test_build_headers_generic():
    client = LLMClient(
        base_url="https://api.groq.com/openai/v1",
        api_key="groq-key",
        provider="groq",
    )
    headers = client._build_headers()
    assert headers["Authorization"] == "Bearer groq-key"
    assert "HTTP-Referer" not in headers


def test_build_payload():
    client = LLMClient(base_url="https://example.com/v1", api_key="", provider="openrouter")
    payload = client._build_payload(
        model="qwen/qwen3-coder",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
    )
    assert payload["model"] == "qwen/qwen3-coder"
    assert payload["stream"] is True
    assert payload["messages"][0]["content"] == "hi"
    assert payload["temperature"] == 0.7
    assert payload["max_tokens"] == 4096


def test_chat_endpoint_openai_compat():
    client = LLMClient(base_url="https://openrouter.ai/api/v1", api_key="", provider="openrouter")
    assert client._chat_endpoint() == "https://openrouter.ai/api/v1/chat/completions"


def test_chat_endpoint_anthropic():
    client = LLMClient(base_url="https://api.anthropic.com/v1", api_key="", provider="anthropic")
    assert client._chat_endpoint() == "https://api.anthropic.com/v1/messages"


def test_extract_text_openai_format():
    client = LLMClient(base_url="", api_key="", provider="openrouter")
    data = {"choices": [{"message": {"content": "Hello world"}}]}
    assert client._extract_text(data) == "Hello world"


def test_extract_text_anthropic_format():
    client = LLMClient(base_url="", api_key="", provider="anthropic")
    data = {"content": [{"type": "text", "text": "Hello"}, {"type": "text", "text": " world"}]}
    assert client._extract_text(data) == "Hello world"


def test_extract_text_empty():
    client = LLMClient(base_url="", api_key="", provider="openrouter")
    assert client._extract_text({}) == ""
    assert client._extract_text({"choices": []}) == ""


def test_extract_stream_chunk():
    client = LLMClient(base_url="", api_key="", provider="openrouter")
    data = {"choices": [{"delta": {"content": "chunk"}}]}
    assert client._extract_stream_chunk(data) == "chunk"


def test_extract_stream_chunk_empty():
    client = LLMClient(base_url="", api_key="", provider="openrouter")
    assert client._extract_stream_chunk({}) == ""
    assert client._extract_stream_chunk({"choices": [{"delta": {}}]}) == ""


def test_base_url_trailing_slash():
    client = LLMClient(base_url="https://example.com/v1/", api_key="", provider="openrouter")
    assert client.base_url == "https://example.com/v1"
