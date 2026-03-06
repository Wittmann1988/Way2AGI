"""
Dynamic Model Composer — Chains and composes models for complex tasks.

Instead of sending one request to one model, the Composer:
1. Decomposes tasks into sub-tasks
2. Selects optimal model per sub-task from Capability Registry
3. Chains outputs through the pipeline
4. Optionally uses Mixture-of-Agents for consensus

Based on "Mixture of Agents" (arXiv:2406.02428) and
"Chameleon: Plug-and-Play Compositional Reasoning" (Lu et al., 2024).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from .registry import CapabilityRegistry, ModelSpec
import httpx
from .cache import LLMCache
from .resilience import CircuitBreaker, retry_with_backoff

logger = logging.getLogger(__name__)


@dataclass
class SubTask:
    id: str
    description: str
    domain: str
    skill: str | None = None
    input_data: str = ""
    depends_on: list[str] = field(default_factory=list)
    assigned_model: ModelSpec | None = None
    result: str | None = None
    status: str = "pending"  # pending | running | completed | failed


@dataclass
class CompositionPlan:
    task_description: str
    subtasks: list[SubTask]
    strategy: str = "chain"  # chain | parallel | moa


# Type for the actual LLM call function
LLMCallFn = Callable[[str, str, str], Awaitable[str]]  # (model_id, system, prompt) -> response


class ModelComposer:
    """Orchestrates multi-model task execution."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        llm_call: LLMCallFn,
        cache: LLMCache | None = None,
    ) -> None:
        self.registry = registry
        self.llm_call = llm_call
        self.cache = cache
        self._circuit = CircuitBreaker(
            "llm-composer",
            failure_threshold=5,
            recovery_timeout=60.0,
            half_open_max=2,
        )

    @property
    def _call(self) -> LLMCallFn:
        """Return resilient LLM call: cache -> retry -> circuit breaker."""
        base_fn = self.llm_call
        if self.cache is not None:
            base_fn = self.cache.wrap(base_fn)

        @retry_with_backoff(
            max_retries=2,
            base_delay=1.0,
            max_delay=15.0,
            retryable_exceptions=(
                httpx.HTTPStatusError,
                httpx.ConnectError,
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
                TimeoutError,
                ConnectionError,
            ),
        )
        async def resilient_call(model_id: str, system: str, prompt: str) -> str:
            return await self._circuit.call(base_fn, model_id, system, prompt)

        return resilient_call

    async def execute_chain(self, plan: CompositionPlan) -> str:
        """Execute subtasks sequentially, piping output to next input."""
        llm_fn = self._call
        context = ""
        for subtask in plan.subtasks:
            if not subtask.assigned_model:
                subtask.assigned_model = self.registry.find_best(
                    subtask.domain, subtask.skill
                )
            if not subtask.assigned_model:
                subtask.status = "failed"
                continue

            subtask.status = "running"
            prompt = subtask.input_data or context
            if context and subtask.input_data:
                prompt = f"Previous context:\n{context}\n\nTask:\n{subtask.input_data}"

            subtask.result = await llm_fn(
                subtask.assigned_model.id,
                f"You are performing subtask: {subtask.description}",
                prompt,
            )
            subtask.status = "completed"
            context = subtask.result

        return context

    async def execute_parallel(self, plan: CompositionPlan) -> list[str]:
        """Execute independent subtasks in parallel."""
        llm_fn = self._call

        async def run_subtask(subtask: SubTask) -> str:
            if not subtask.assigned_model:
                subtask.assigned_model = self.registry.find_best(
                    subtask.domain, subtask.skill
                )
            if not subtask.assigned_model:
                return ""

            subtask.status = "running"
            subtask.result = await llm_fn(
                subtask.assigned_model.id,
                f"You are performing subtask: {subtask.description}",
                subtask.input_data,
            )
            subtask.status = "completed"
            return subtask.result or ""

        results = await asyncio.gather(
            *(run_subtask(st) for st in plan.subtasks),
            return_exceptions=True,
        )
        return [r if isinstance(r, str) else str(r) for r in results]

    async def execute_moa(
        self,
        prompt: str,
        domain: str,
        n_experts: int = 3,
        aggregator_model: str | None = None,
    ) -> str:
        """
        Mixture-of-Agents: multiple models answer independently,
        then an aggregator synthesizes the best response.
        """
        llm_fn = self._call

        # Select diverse experts
        candidates = self.registry.find_by_capability(domain, min_score=0.6)
        experts = candidates[:n_experts]

        if not experts:
            best = self.registry.find_best(domain)
            if not best:
                return "No models available for this domain."
            return await llm_fn(best.id, "Answer concisely.", prompt)

        # Phase 1: All experts answer independently (tolerate individual failures)
        raw_results = await asyncio.gather(
            *(llm_fn(
                expert.id,
                f"You are an expert in {domain}. Answer thoroughly.",
                prompt,
            ) for expert in experts),
            return_exceptions=True,
        )
        # Filter out failed experts
        expert_responses = []
        valid_experts = []
        for expert, result in zip(experts, raw_results):
            if isinstance(result, str):
                expert_responses.append(result)
                valid_experts.append(expert)
            else:
                logger.warning("MoA expert %s failed: %s", expert.id, result)
        experts = valid_experts

        if not expert_responses:
            return "All expert models failed."

        # Phase 2: Aggregator synthesizes
        agg_model = aggregator_model or (
            self.registry.find_best("reasoning")
        )
        if not agg_model:
            # No aggregator available, return best single response
            return expert_responses[0] if expert_responses else ""

        agg_id = agg_model if isinstance(agg_model, str) else agg_model.id

        synthesis_prompt = f"""Task: {prompt}

Expert responses:
{chr(10).join(f'--- Expert {i+1} ({experts[i].display_name}) ---{chr(10)}{resp}' for i, resp in enumerate(expert_responses))}

Synthesize the best answer from these expert responses. Keep the strongest insights, resolve contradictions, and produce a superior unified response."""

        return await llm_fn(
            agg_id,
            "You are a synthesis expert. Combine multiple expert opinions into one superior answer.",
            synthesis_prompt,
        )

    async def execute(self, plan: CompositionPlan) -> str | list[str]:
        """Execute a composition plan using the specified strategy."""
        match plan.strategy:
            case "chain":
                return await self.execute_chain(plan)
            case "parallel":
                return await self.execute_parallel(plan)
            case "moa":
                # MoA uses the first subtask's input
                return await self.execute_moa(
                    plan.subtasks[0].input_data if plan.subtasks else "",
                    plan.subtasks[0].domain if plan.subtasks else "reasoning",
                )
            case _:
                return await self.execute_chain(plan)
