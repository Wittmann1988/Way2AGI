"""
Capability Registry — Maps models to fine-grained capabilities.

Unlike OpenClaw's flat model list, Way2AGI treats models as a capability graph.
Each model is tagged with what it can do, how well, and at what cost.
The Composer queries this registry to build optimal model chains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    GROQ = "groq"
    NVIDIA = "nvidia"
    HUGGINGFACE = "huggingface"
    XAI = "xai"


@dataclass
class Capability:
    domain: str  # e.g. "code", "reasoning", "creative", "analysis"
    skill: str  # e.g. "python", "math", "writing", "summarization"
    score: float  # 0.0-1.0 proficiency
    tags: list[str] = field(default_factory=list)


@dataclass
class ModelSpec:
    id: str  # e.g. "claude-opus-4-6"
    provider: Provider
    display_name: str
    capabilities: list[Capability] = field(default_factory=list)
    context_window: int = 128_000
    max_output: int = 16_000
    cost_per_1k_input: float = 0.0  # USD
    cost_per_1k_output: float = 0.0
    latency_class: str = "medium"  # fast | medium | slow
    supports_vision: bool = False
    supports_tools: bool = False
    is_available: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class CapabilityRegistry:
    """Central registry of all available models and their capabilities."""

    def __init__(self) -> None:
        self._models: dict[str, ModelSpec] = {}

    def register(self, model: ModelSpec) -> None:
        self._models[model.id] = model

    def unregister(self, model_id: str) -> None:
        self._models.pop(model_id, None)

    def get(self, model_id: str) -> ModelSpec | None:
        return self._models.get(model_id)

    def find_by_capability(
        self,
        domain: str,
        skill: str | None = None,
        min_score: float = 0.5,
        max_cost: float | None = None,
        latency: str | None = None,
    ) -> list[ModelSpec]:
        """Find models that match capability requirements."""
        results = []
        for model in self._models.values():
            if not model.is_available:
                continue
            for cap in model.capabilities:
                if cap.domain != domain:
                    continue
                if skill and cap.skill != skill:
                    continue
                if cap.score < min_score:
                    continue
                if max_cost and model.cost_per_1k_output > max_cost:
                    continue
                if latency and model.latency_class != latency:
                    continue
                results.append(model)
                break
        return sorted(results, key=lambda m: max(
            (c.score for c in m.capabilities if c.domain == domain), default=0
        ), reverse=True)

    def find_cheapest(self, domain: str, min_score: float = 0.3) -> ModelSpec | None:
        """Find the cheapest model that meets minimum capability."""
        matches = self.find_by_capability(domain, min_score=min_score)
        if not matches:
            return None
        return min(matches, key=lambda m: m.cost_per_1k_output)

    def find_fastest(self, domain: str, min_score: float = 0.3) -> ModelSpec | None:
        """Find the fastest model that meets minimum capability."""
        matches = self.find_by_capability(domain, min_score=min_score, latency="fast")
        return matches[0] if matches else None

    def find_best(self, domain: str, skill: str | None = None) -> ModelSpec | None:
        """Find the highest-scoring model for a domain/skill."""
        matches = self.find_by_capability(domain, skill=skill)
        return matches[0] if matches else None

    @property
    def model_count(self) -> int:
        return len(self._models)

    @property
    def available_count(self) -> int:
        return sum(1 for m in self._models.values() if m.is_available)

    def list_providers(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for m in self._models.values():
            counts[m.provider.value] = counts.get(m.provider.value, 0) + 1
        return counts


def build_default_registry() -> CapabilityRegistry:
    """Pre-populate registry with known models from our 9 providers."""
    reg = CapabilityRegistry()

    # Anthropic
    reg.register(ModelSpec(
        id="claude-opus-4-6", provider=Provider.ANTHROPIC,
        display_name="Claude Opus 4.6",
        capabilities=[
            Capability("reasoning", "general", 0.98),
            Capability("code", "python", 0.95),
            Capability("code", "typescript", 0.95),
            Capability("creative", "writing", 0.95),
            Capability("analysis", "research", 0.97),
        ],
        context_window=200_000, max_output=32_000,
        cost_per_1k_input=0.015, cost_per_1k_output=0.075,
        latency_class="slow", supports_vision=True, supports_tools=True,
    ))
    reg.register(ModelSpec(
        id="claude-sonnet-4-6", provider=Provider.ANTHROPIC,
        display_name="Claude Sonnet 4.6",
        capabilities=[
            Capability("reasoning", "general", 0.90),
            Capability("code", "python", 0.92),
            Capability("code", "typescript", 0.92),
            Capability("analysis", "summarization", 0.88),
        ],
        context_window=200_000, max_output=16_000,
        cost_per_1k_input=0.003, cost_per_1k_output=0.015,
        latency_class="medium", supports_vision=True, supports_tools=True,
    ))
    reg.register(ModelSpec(
        id="claude-haiku-4-5", provider=Provider.ANTHROPIC,
        display_name="Claude Haiku 4.5",
        capabilities=[
            Capability("reasoning", "general", 0.75),
            Capability("code", "python", 0.78),
            Capability("analysis", "classification", 0.80),
        ],
        context_window=200_000, max_output=8_000,
        cost_per_1k_input=0.0008, cost_per_1k_output=0.004,
        latency_class="fast", supports_vision=True, supports_tools=True,
    ))

    # Groq (ultra-fast)
    reg.register(ModelSpec(
        id="kimi-k2-groq", provider=Provider.GROQ,
        display_name="Kimi-K2 (Groq)",
        capabilities=[
            Capability("reasoning", "general", 0.82),
            Capability("code", "python", 0.80),
        ],
        context_window=128_000, max_output=8_000,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        latency_class="fast", supports_tools=True,
    ))

    # OpenRouter (free tier)
    reg.register(ModelSpec(
        id="step-flash-openrouter", provider=Provider.OPENROUTER,
        display_name="Step-3.5-Flash (Reasoning)",
        capabilities=[
            Capability("reasoning", "math", 0.88),
            Capability("reasoning", "logic", 0.90),
            Capability("analysis", "research", 0.85),
        ],
        context_window=64_000, max_output=16_000,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        latency_class="medium", supports_tools=False,
    ))
    reg.register(ModelSpec(
        id="qwen-coder-openrouter", provider=Provider.OPENROUTER,
        display_name="Qwen-Coder (Code Specialist)",
        capabilities=[
            Capability("code", "python", 0.90),
            Capability("code", "typescript", 0.88),
            Capability("code", "rust", 0.82),
            Capability("code", "debugging", 0.87),
        ],
        context_window=128_000, max_output=16_000,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        latency_class="medium", supports_tools=True,
    ))

    # Ollama Cloud
    reg.register(ModelSpec(
        id="nemotron-ollama", provider=Provider.OLLAMA,
        display_name="Nemotron-3-Nano 30B",
        capabilities=[
            Capability("reasoning", "general", 0.75),
            Capability("creative", "writing", 0.70),
            Capability("analysis", "summarization", 0.72),
        ],
        context_window=128_000, max_output=8_000,
        cost_per_1k_input=0.0, cost_per_1k_output=0.0,
        latency_class="medium",
    ))

    return reg
