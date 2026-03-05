"""Tests for Way2AGI Capability Registry."""

from __future__ import annotations

import pytest

from orchestrator.src.registry import (
    CapabilityRegistry,
    ModelSpec,
    Capability,
    Provider,
    build_default_registry,
)


@pytest.fixture
def registry() -> CapabilityRegistry:
    return CapabilityRegistry()


@pytest.fixture
def sample_model() -> ModelSpec:
    return ModelSpec(
        id="test-model-1",
        provider=Provider.OLLAMA,
        display_name="Test Model 1",
        capabilities=[
            Capability("code", "python", 0.9),
            Capability("reasoning", "general", 0.7),
        ],
        cost_per_1k_output=0.01,
        latency_class="fast",
        supports_tools=True,
    )


# --- register / unregister ---


def test_register(registry, sample_model):
    registry.register(sample_model)
    assert registry.model_count == 1
    assert registry.get("test-model-1") is sample_model


def test_register_overwrites(registry, sample_model):
    registry.register(sample_model)
    updated = ModelSpec(
        id="test-model-1",
        provider=Provider.OLLAMA,
        display_name="Updated",
        capabilities=[],
    )
    registry.register(updated)
    assert registry.model_count == 1
    assert registry.get("test-model-1").display_name == "Updated"


def test_unregister(registry, sample_model):
    registry.register(sample_model)
    registry.unregister("test-model-1")
    assert registry.model_count == 0
    assert registry.get("test-model-1") is None


def test_unregister_nonexistent(registry):
    # Should not raise
    registry.unregister("does-not-exist")


def test_get_nonexistent(registry):
    assert registry.get("nope") is None


# --- find_by_capability ---


def test_find_by_capability_domain(registry, sample_model):
    registry.register(sample_model)
    results = registry.find_by_capability("code")
    assert len(results) == 1
    assert results[0].id == "test-model-1"


def test_find_by_capability_domain_and_skill(registry, sample_model):
    registry.register(sample_model)
    results = registry.find_by_capability("code", skill="python")
    assert len(results) == 1
    results = registry.find_by_capability("code", skill="rust")
    assert len(results) == 0


def test_find_by_capability_min_score(registry, sample_model):
    registry.register(sample_model)
    results = registry.find_by_capability("reasoning", min_score=0.8)
    assert len(results) == 0  # reasoning score is 0.7
    results = registry.find_by_capability("reasoning", min_score=0.5)
    assert len(results) == 1


def test_find_by_capability_max_cost(registry):
    cheap = ModelSpec(
        id="cheap", provider=Provider.OLLAMA, display_name="Cheap",
        capabilities=[Capability("code", "python", 0.8)],
        cost_per_1k_output=0.001,
    )
    expensive = ModelSpec(
        id="expensive", provider=Provider.ANTHROPIC, display_name="Expensive",
        capabilities=[Capability("code", "python", 0.95)],
        cost_per_1k_output=0.075,
    )
    registry.register(cheap)
    registry.register(expensive)
    results = registry.find_by_capability("code", max_cost=0.01)
    assert len(results) == 1
    assert results[0].id == "cheap"


def test_find_by_capability_latency(registry):
    fast = ModelSpec(
        id="fast", provider=Provider.GROQ, display_name="Fast",
        capabilities=[Capability("reasoning", "general", 0.8)],
        latency_class="fast",
    )
    slow = ModelSpec(
        id="slow", provider=Provider.ANTHROPIC, display_name="Slow",
        capabilities=[Capability("reasoning", "general", 0.95)],
        latency_class="slow",
    )
    registry.register(fast)
    registry.register(slow)
    results = registry.find_by_capability("reasoning", latency="fast")
    assert len(results) == 1
    assert results[0].id == "fast"


def test_find_by_capability_excludes_unavailable(registry):
    model = ModelSpec(
        id="offline", provider=Provider.OLLAMA, display_name="Offline",
        capabilities=[Capability("code", "python", 0.9)],
        is_available=False,
    )
    registry.register(model)
    results = registry.find_by_capability("code")
    assert len(results) == 0


def test_find_by_capability_sorted_by_score(registry):
    low = ModelSpec(
        id="low", provider=Provider.OLLAMA, display_name="Low",
        capabilities=[Capability("code", "python", 0.6)],
    )
    high = ModelSpec(
        id="high", provider=Provider.ANTHROPIC, display_name="High",
        capabilities=[Capability("code", "python", 0.95)],
    )
    registry.register(low)
    registry.register(high)
    results = registry.find_by_capability("code")
    assert results[0].id == "high"
    assert results[1].id == "low"


# --- find_cheapest ---


def test_find_cheapest(registry):
    cheap = ModelSpec(
        id="cheap", provider=Provider.OLLAMA, display_name="Cheap",
        capabilities=[Capability("code", "python", 0.8)],
        cost_per_1k_output=0.0,
    )
    pricey = ModelSpec(
        id="pricey", provider=Provider.ANTHROPIC, display_name="Pricey",
        capabilities=[Capability("code", "python", 0.95)],
        cost_per_1k_output=0.075,
    )
    registry.register(cheap)
    registry.register(pricey)
    result = registry.find_cheapest("code")
    assert result is not None
    assert result.id == "cheap"


def test_find_cheapest_no_match(registry):
    assert registry.find_cheapest("nonexistent") is None


# --- find_fastest ---


def test_find_fastest(registry):
    fast = ModelSpec(
        id="fast", provider=Provider.GROQ, display_name="Fast",
        capabilities=[Capability("code", "python", 0.8)],
        latency_class="fast",
    )
    medium = ModelSpec(
        id="medium", provider=Provider.ANTHROPIC, display_name="Medium",
        capabilities=[Capability("code", "python", 0.95)],
        latency_class="medium",
    )
    registry.register(fast)
    registry.register(medium)
    result = registry.find_fastest("code")
    assert result is not None
    assert result.id == "fast"


def test_find_fastest_no_fast_model(registry):
    slow = ModelSpec(
        id="slow", provider=Provider.ANTHROPIC, display_name="Slow",
        capabilities=[Capability("code", "python", 0.9)],
        latency_class="slow",
    )
    registry.register(slow)
    assert registry.find_fastest("code") is None


# --- find_best ---


def test_find_best(registry):
    ok = ModelSpec(
        id="ok", provider=Provider.OLLAMA, display_name="OK",
        capabilities=[Capability("code", "python", 0.7)],
    )
    best = ModelSpec(
        id="best", provider=Provider.ANTHROPIC, display_name="Best",
        capabilities=[Capability("code", "python", 0.98)],
    )
    registry.register(ok)
    registry.register(best)
    result = registry.find_best("code", skill="python")
    assert result is not None
    assert result.id == "best"


def test_find_best_no_match(registry):
    assert registry.find_best("unknown_domain") is None


# --- properties ---


def test_available_count(registry):
    avail = ModelSpec(
        id="a", provider=Provider.OLLAMA, display_name="A",
        capabilities=[], is_available=True,
    )
    unavail = ModelSpec(
        id="b", provider=Provider.OLLAMA, display_name="B",
        capabilities=[], is_available=False,
    )
    registry.register(avail)
    registry.register(unavail)
    assert registry.model_count == 2
    assert registry.available_count == 1


def test_list_providers(registry):
    registry.register(ModelSpec(
        id="a", provider=Provider.OLLAMA, display_name="A", capabilities=[],
    ))
    registry.register(ModelSpec(
        id="b", provider=Provider.ANTHROPIC, display_name="B", capabilities=[],
    ))
    registry.register(ModelSpec(
        id="c", provider=Provider.OLLAMA, display_name="C", capabilities=[],
    ))
    providers = registry.list_providers()
    assert providers["ollama"] == 2
    assert providers["anthropic"] == 1


# --- build_default_registry ---


def test_default_registry_has_7_models():
    reg = build_default_registry()
    assert reg.model_count == 7


def test_default_registry_model_ids():
    reg = build_default_registry()
    expected_ids = {
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
        "kimi-k2-groq",
        "step-flash-openrouter",
        "qwen-coder-openrouter",
        "nemotron-ollama",
    }
    for model_id in expected_ids:
        assert reg.get(model_id) is not None, f"Missing model: {model_id}"


def test_default_registry_providers():
    reg = build_default_registry()
    providers = reg.list_providers()
    assert "anthropic" in providers
    assert providers["anthropic"] == 3
    assert "groq" in providers
    assert "openrouter" in providers
    assert "ollama" in providers


def test_default_registry_opus_capabilities():
    reg = build_default_registry()
    opus = reg.get("claude-opus-4-6")
    assert opus is not None
    assert opus.supports_vision is True
    assert opus.supports_tools is True
    assert opus.context_window == 200_000
    domains = {c.domain for c in opus.capabilities}
    assert "reasoning" in domains
    assert "code" in domains
    assert "creative" in domains


def test_default_registry_find_best_code():
    reg = build_default_registry()
    best = reg.find_best("code", skill="python")
    assert best is not None
    # Opus has 0.95, Sonnet 0.92, Qwen-Coder 0.90
    assert best.id == "claude-opus-4-6"


def test_default_registry_find_fastest_reasoning():
    reg = build_default_registry()
    fastest = reg.find_fastest("reasoning")
    assert fastest is not None
    # Haiku and Kimi-K2 are "fast"; Kimi has 0.82, Haiku 0.75
    assert fastest.id == "kimi-k2-groq"
