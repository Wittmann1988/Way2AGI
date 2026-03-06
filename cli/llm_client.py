"""Unified LLM Client — OpenAI-kompatibles Interface fuer alle Provider."""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx


class LLMClient:
    """Async LLM client supporting OpenAI-compatible APIs."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        provider: str = "openrouter",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.provider = provider
        self.timeout = timeout

    def _build_headers(self) -> dict[str, str]:
        if self.provider == "anthropic":
            return {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/Wittmann1988/Way2AGI"
            headers["X-Title"] = "Way2AGI"
        return headers

    def _build_payload(
        self,
        model: str,
        messages: list[dict],
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        return {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

    def _chat_endpoint(self) -> str:
        if self.provider == "anthropic":
            return f"{self.base_url}/messages"
        return f"{self.base_url}/chat/completions"

    async def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Non-streaming chat completion. Returns full response text."""
        payload = self._build_payload(model, messages, stream=False,
                                      temperature=temperature, max_tokens=max_tokens)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self._chat_endpoint(),
                headers=self._build_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        return self._extract_text(data)

    async def stream(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Streaming chat completion. Yields text chunks."""
        payload = self._build_payload(model, messages, stream=True,
                                      temperature=temperature, max_tokens=max_tokens)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                self._chat_endpoint(),
                headers=self._build_headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:]
                    if chunk.strip() == "[DONE]":
                        break
                    try:
                        obj = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    text = self._extract_stream_chunk(obj)
                    if text:
                        yield text

    def _extract_text(self, data: dict) -> str:
        # Anthropic format
        if "content" in data and isinstance(data["content"], list):
            return "".join(
                block.get("text", "") for block in data["content"]
                if block.get("type") == "text"
            )
        # OpenAI format
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""

    def _extract_stream_chunk(self, data: dict) -> str:
        # OpenAI SSE format
        choices = data.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            return delta.get("content", "")
        return ""
