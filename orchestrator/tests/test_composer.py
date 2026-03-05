"""Tests for Way2AGI Model Composer."""

from __future__ import annotations

import pytest

from orchestrator.src.registry import (
    CapabilityRegistry,
    ModelSpec,
    Capability,
    Provider,
)
from orchestrator.src.composer import (
    ModelComposer,
    CompositionPlan,
    SubTask,
)


# --- Helpers ---


def _make_registry() -> CapabilityRegistry:
    """Create a small registry with 2 models for testing."""
    reg = CapabilityRegistry()
    reg.register(ModelSpec(
        id="model-code",
        provider=Provider.OLLAMA,
        display_name="Code Model",
        capabilities=[
            Capability("code", "python", 0.9),
            Capability("code", "typescript", 0.85),
        ],
        latency_class="fast",
    ))
    reg.register(ModelSpec(
        id="model-reasoning",
        provider=Provider.ANTHROPIC,
        display_name="Reasoning Model",
        capabilities=[
            Capability("reasoning", "general", 0.95),
            Capability("reasoning", "math", 0.90),
            Capability("analysis", "research", 0.88),
        ],
        latency_class="medium",
    ))
    return reg


def _make_mock_llm(responses: dict[str, str] | None = None):
    """Create a mock LLM call function that records calls."""
    calls: list[tuple[str, str, str]] = []
    default_responses = responses or {}

    async def mock_llm(model_id: str, system: str, prompt: str) -> str:
        calls.append((model_id, system, prompt))
        return default_responses.get(model_id, f"response from {model_id}")

    return mock_llm, calls


# --- execute_chain ---


@pytest.mark.anyio
async def test_chain_single_subtask():
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm({"model-code": "def hello(): pass"})
    composer = ModelComposer(reg, mock_llm)

    plan = CompositionPlan(
        task_description="Write a function",
        subtasks=[
            SubTask(id="s1", description="Write code", domain="code",
                    skill="python", input_data="Write hello world"),
        ],
        strategy="chain",
    )
    result = await composer.execute_chain(plan)
    assert result == "def hello(): pass"
    assert len(calls) == 1
    assert calls[0][0] == "model-code"
    assert plan.subtasks[0].status == "completed"


@pytest.mark.anyio
async def test_chain_pipes_output():
    """Second subtask receives first subtask's output as context."""
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm({
        "model-code": "code output",
        "model-reasoning": "analysis of code",
    })
    composer = ModelComposer(reg, mock_llm)

    plan = CompositionPlan(
        task_description="Code then analyze",
        subtasks=[
            SubTask(id="s1", description="Write code", domain="code",
                    skill="python", input_data="Write a function"),
            SubTask(id="s2", description="Analyze code", domain="reasoning",
                    input_data=""),
        ],
        strategy="chain",
    )
    result = await composer.execute_chain(plan)
    assert result == "analysis of code"
    # Second call should receive "code output" as the prompt (piped context)
    assert calls[1][2] == "code output"


@pytest.mark.anyio
async def test_chain_with_context_and_input():
    """When subtask has both input_data and prior context, both are included."""
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm({
        "model-code": "step1 result",
        "model-reasoning": "step2 result",
    })
    composer = ModelComposer(reg, mock_llm)

    plan = CompositionPlan(
        task_description="Multi-step",
        subtasks=[
            SubTask(id="s1", description="First", domain="code",
                    skill="python", input_data="initial input"),
            SubTask(id="s2", description="Second", domain="reasoning",
                    input_data="additional instructions"),
        ],
    )
    await composer.execute_chain(plan)
    # Second prompt should combine context and input_data
    assert "step1 result" in calls[1][2]
    assert "additional instructions" in calls[1][2]


@pytest.mark.anyio
async def test_chain_no_model_found():
    """Subtask with unmatched domain is marked failed and skipped."""
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm()
    composer = ModelComposer(reg, mock_llm)

    plan = CompositionPlan(
        task_description="Impossible",
        subtasks=[
            SubTask(id="s1", description="Fly", domain="aviation", input_data="fly"),
        ],
    )
    result = await composer.execute_chain(plan)
    assert result == ""
    assert plan.subtasks[0].status == "failed"
    assert len(calls) == 0


@pytest.mark.anyio
async def test_chain_preassigned_model():
    """If a subtask already has an assigned_model, use it."""
    reg = _make_registry()
    model = reg.get("model-reasoning")
    mock_llm, calls = _make_mock_llm({"model-reasoning": "preassigned response"})
    composer = ModelComposer(reg, mock_llm)

    plan = CompositionPlan(
        task_description="Pre-assigned",
        subtasks=[
            SubTask(id="s1", description="Think", domain="code",
                    input_data="think", assigned_model=model),
        ],
    )
    result = await composer.execute_chain(plan)
    assert result == "preassigned response"
    assert calls[0][0] == "model-reasoning"


# --- execute_parallel ---


@pytest.mark.anyio
async def test_parallel_execution():
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm({
        "model-code": "code result",
        "model-reasoning": "reasoning result",
    })
    composer = ModelComposer(reg, mock_llm)

    plan = CompositionPlan(
        task_description="Parallel tasks",
        subtasks=[
            SubTask(id="s1", description="Code", domain="code",
                    skill="python", input_data="write code"),
            SubTask(id="s2", description="Reason", domain="reasoning",
                    input_data="analyze"),
        ],
        strategy="parallel",
    )
    results = await composer.execute_parallel(plan)
    assert len(results) == 2
    assert "code result" in results
    assert "reasoning result" in results
    assert all(st.status == "completed" for st in plan.subtasks)


@pytest.mark.anyio
async def test_parallel_no_model_returns_empty():
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm()
    composer = ModelComposer(reg, mock_llm)

    plan = CompositionPlan(
        task_description="No match",
        subtasks=[
            SubTask(id="s1", description="Fly", domain="aviation", input_data="fly"),
        ],
    )
    results = await composer.execute_parallel(plan)
    assert results == [""]
    assert len(calls) == 0


# --- execute_moa ---


@pytest.mark.anyio
async def test_moa_basic():
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm({
        "model-reasoning": "expert answer + synthesis",
    })
    composer = ModelComposer(reg, mock_llm)

    result = await composer.execute_moa(
        prompt="What is 2+2?",
        domain="reasoning",
        n_experts=2,
    )
    # Should have expert calls + aggregator call
    assert len(calls) >= 2
    # The final result is the aggregator's output
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.anyio
async def test_moa_no_experts_falls_back():
    """When no experts found for domain, fall back to find_best."""
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm({
        "model-reasoning": "fallback answer",
    })
    composer = ModelComposer(reg, mock_llm)

    # "creative" domain has no models in our test registry
    result = await composer.execute_moa(
        prompt="Write a poem",
        domain="creative",
        n_experts=3,
    )
    # Should have tried find_best as fallback — no creative models exist
    # so returns "No models available" message
    assert isinstance(result, str)


@pytest.mark.anyio
async def test_moa_with_explicit_aggregator():
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm({
        "model-reasoning": "expert response",
        "model-code": "aggregated",
    })
    composer = ModelComposer(reg, mock_llm)

    result = await composer.execute_moa(
        prompt="Analyze this",
        domain="reasoning",
        n_experts=1,
        aggregator_model="model-code",
    )
    # Last call should be to the explicit aggregator
    assert calls[-1][0] == "model-code"


# --- execute (dispatch) ---


@pytest.mark.anyio
async def test_execute_dispatches_chain():
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm({"model-code": "chain result"})
    composer = ModelComposer(reg, mock_llm)

    plan = CompositionPlan(
        task_description="Chain",
        subtasks=[
            SubTask(id="s1", description="Code", domain="code",
                    skill="python", input_data="test"),
        ],
        strategy="chain",
    )
    result = await composer.execute(plan)
    assert result == "chain result"


@pytest.mark.anyio
async def test_execute_dispatches_parallel():
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm({"model-code": "par result"})
    composer = ModelComposer(reg, mock_llm)

    plan = CompositionPlan(
        task_description="Parallel",
        subtasks=[
            SubTask(id="s1", description="Code", domain="code",
                    skill="python", input_data="test"),
        ],
        strategy="parallel",
    )
    result = await composer.execute(plan)
    assert isinstance(result, list)


@pytest.mark.anyio
async def test_execute_dispatches_moa():
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm({"model-reasoning": "moa result"})
    composer = ModelComposer(reg, mock_llm)

    plan = CompositionPlan(
        task_description="MoA",
        subtasks=[
            SubTask(id="s1", description="Reason", domain="reasoning",
                    input_data="question"),
        ],
        strategy="moa",
    )
    result = await composer.execute(plan)
    assert isinstance(result, str)


@pytest.mark.anyio
async def test_execute_unknown_strategy_defaults_to_chain():
    reg = _make_registry()
    mock_llm, calls = _make_mock_llm({"model-code": "default result"})
    composer = ModelComposer(reg, mock_llm)

    plan = CompositionPlan(
        task_description="Unknown",
        subtasks=[
            SubTask(id="s1", description="Code", domain="code",
                    skill="python", input_data="test"),
        ],
        strategy="unknown_strategy",
    )
    result = await composer.execute(plan)
    assert result == "default result"
