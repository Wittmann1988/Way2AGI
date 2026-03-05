"""
Cost/Performance/Latency Optimizer.

Selects the minimal sufficient model configuration for a task.
Tracks usage, estimates costs, and enforces budgets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .registry import CapabilityRegistry, ModelSpec


@dataclass
class UsageRecord:
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = True


@dataclass
class Budget:
    daily_limit_usd: float = 5.0
    monthly_limit_usd: float = 50.0
    prefer_free: bool = True


class CostOptimizer:
    """Tracks costs and selects cost-efficient models."""

    def __init__(self, registry: CapabilityRegistry, budget: Budget | None = None) -> None:
        self.registry = registry
        self.budget = budget or Budget()
        self.usage: list[UsageRecord] = []

    def record_usage(self, record: UsageRecord) -> None:
        self.usage.append(record)

    def daily_spend(self) -> float:
        today = datetime.now().date().isoformat()
        return sum(
            r.cost_usd for r in self.usage
            if r.timestamp.startswith(today)
        )

    def monthly_spend(self) -> float:
        month = datetime.now().strftime("%Y-%m")
        return sum(
            r.cost_usd for r in self.usage
            if r.timestamp.startswith(month)
        )

    def within_budget(self) -> bool:
        return (
            self.daily_spend() < self.budget.daily_limit_usd
            and self.monthly_spend() < self.budget.monthly_limit_usd
        )

    def select_optimal(
        self,
        domain: str,
        skill: str | None = None,
        min_score: float = 0.5,
        prefer: str = "cost",  # cost | speed | quality
    ) -> ModelSpec | None:
        """Select the optimal model balancing cost, speed, and quality."""
        candidates = self.registry.find_by_capability(domain, skill, min_score)
        if not candidates:
            return None

        # If over budget, only use free models
        if not self.within_budget() or self.budget.prefer_free:
            free = [m for m in candidates if m.cost_per_1k_output == 0.0]
            if free:
                candidates = free

        match prefer:
            case "cost":
                return min(candidates, key=lambda m: m.cost_per_1k_output)
            case "speed":
                speed_order = {"fast": 0, "medium": 1, "slow": 2}
                return min(candidates, key=lambda m: speed_order.get(m.latency_class, 1))
            case "quality":
                return candidates[0]  # Already sorted by score
            case _:
                return candidates[0]

    def get_stats(self) -> dict:
        return {
            "total_requests": len(self.usage),
            "daily_spend_usd": round(self.daily_spend(), 4),
            "monthly_spend_usd": round(self.monthly_spend(), 4),
            "budget_remaining_daily": round(
                self.budget.daily_limit_usd - self.daily_spend(), 4
            ),
            "success_rate": (
                sum(1 for r in self.usage if r.success) / len(self.usage)
                if self.usage else 1.0
            ),
        }
