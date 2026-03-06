"""
Auto Registry — Loads ALL discovered models into the Capability Registry.

Reads the latest model scan report and registers every model so it's
instantly available for the Composer, MoA, and any pipeline that needs
model selection.

Usage:
    from orchestrator.src.auto_registry import build_full_registry
    registry = build_full_registry()  # 586+ models ready
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .registry import CapabilityRegistry, ModelSpec, Capability, Provider


# Map scanner provider names to our Provider enum
_PROVIDER_MAP = {
    "huggingface": Provider.HUGGINGFACE,
    "openrouter": Provider.OPENROUTER,
    "nvidia": Provider.NVIDIA,
    "groq": Provider.GROQ,
    "google": Provider.GOOGLE,
    "xai": Provider.XAI,
    "ollama": Provider.OLLAMA,
    "ollama-cloud": Provider.OLLAMA,
    "ollama-local": Provider.OLLAMA,
}

# Cost mapping to approximate $/1k tokens
_COST_MAP = {
    "free": (0.0, 0.0),
    "cheap": (0.0005, 0.002),
    "moderate": (0.003, 0.015),
    "expensive": (0.015, 0.060),
}

# Latency class by provider
_LATENCY_MAP = {
    "groq": "fast",
    "xai": "fast",
    "ollama-local": "fast",
    "openrouter": "medium",
    "huggingface": "medium",
    "google": "medium",
    "nvidia": "medium",
    "ollama-cloud": "medium",
    "ollama": "medium",
}


def _infer_capabilities(model: dict) -> list[Capability]:
    """Infer capabilities from scan data (reasons, capabilities list)."""
    caps: list[Capability] = []
    reasons = model.get("relevance_reasons", [])
    cap_list = model.get("capabilities", [])
    name = model.get("name", "").lower()
    desc = model.get("description", "").lower()
    score = model.get("relevance_score", 0.5)

    # Map capability strings to Capability objects
    for c in cap_list:
        cl = c.lower()
        if "code" in cl:
            caps.append(Capability("code", "general", min(score, 0.85)))
        if "embedding" in cl:
            caps.append(Capability("embedding", "text", min(score, 0.90)))
        if "vision" in cl or "multimodal" in cl:
            caps.append(Capability("vision", "general", min(score, 0.80)))
        if "audio" in cl or "speech" in cl:
            caps.append(Capability("audio", "general", min(score, 0.75)))
        if "reasoning" in cl or "thinking" in cl:
            caps.append(Capability("reasoning", "general", min(score, 0.85)))
        if "tool" in cl or "function" in cl:
            caps.append(Capability("agent", "tool_use", min(score, 0.80)))
        if "german" in cl or "multilingual" in cl:
            caps.append(Capability("multilingual", "de", min(score, 0.75)))
        if "planning" in cl:
            caps.append(Capability("reasoning", "planning", min(score, 0.80)))

    # Infer from model name
    if any(kw in name for kw in ("coder", "codestral", "codex", "starcoder", "code")):
        if not any(c.domain == "code" for c in caps):
            caps.append(Capability("code", "general", 0.80))
    if any(kw in name for kw in ("embed", "bge", "gte", "e5", "nomic")):
        if not any(c.domain == "embedding" for c in caps):
            caps.append(Capability("embedding", "text", 0.85))
    if any(kw in name for kw in ("vision", "vl", "imagine")):
        if not any(c.domain == "vision" for c in caps):
            caps.append(Capability("vision", "general", 0.75))
    if any(kw in name for kw in ("whisper", "speech", "tts")):
        if not any(c.domain == "audio" for c in caps):
            caps.append(Capability("audio", "general", 0.75))

    # Default: at least general reasoning
    if not caps:
        caps.append(Capability("reasoning", "general", max(score * 0.8, 0.3)))

    return caps


def _scan_model_to_spec(model: dict) -> ModelSpec:
    """Convert a scan report model entry to a ModelSpec."""
    provider_str = model.get("provider", "openrouter")
    provider = _PROVIDER_MAP.get(provider_str, Provider.OPENROUTER)

    cost_class = model.get("cost", "moderate")
    cost_in, cost_out = _COST_MAP.get(cost_class, (0.003, 0.015))

    latency = _LATENCY_MAP.get(provider_str, "medium")

    caps = _infer_capabilities(model)
    name = model.get("name", model.get("id", "unknown"))

    supports_vision = any(c.domain == "vision" for c in caps)
    supports_tools = any(
        kw in model.get("description", "").lower()
        for kw in ("tool", "function", "agentic")
    ) or any(c.domain == "agent" for c in caps)

    return ModelSpec(
        id=model.get("id", name),
        provider=provider,
        display_name=name,
        capabilities=caps,
        context_window=model.get("context_window") or 128_000,
        max_output=16_000,
        cost_per_1k_input=cost_in,
        cost_per_1k_output=cost_out,
        latency_class=latency,
        supports_vision=supports_vision,
        supports_tools=supports_tools,
        is_available=True,
        metadata={
            "source": "model_scanner",
            "relevance_score": model.get("relevance_score", 0),
            "recommendation": model.get("recommendation", "monitor"),
            "parameters": model.get("parameters", "unknown"),
            "url": model.get("url", ""),
        },
    )


def load_scan_report(report_path: str | Path | None = None) -> list[dict]:
    """Load the latest model scan report."""
    if report_path:
        path = Path(report_path)
    else:
        scan_dir = Path.home() / ".way2agi" / "research"
        reports = sorted(scan_dir.glob("models-*.json"), reverse=True)
        if not reports:
            return []
        path = reports[0]

    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("models", [])


def build_full_registry(
    report_path: str | Path | None = None,
    include_defaults: bool = True,
) -> CapabilityRegistry:
    """
    Build a registry with ALL discovered models.

    Loads hand-curated defaults first (high-quality capability scores),
    then adds all scan-discovered models (auto-inferred capabilities).
    Hand-curated entries take priority on ID conflicts.
    """
    from .registry import build_default_registry

    if include_defaults:
        reg = build_default_registry()
    else:
        reg = CapabilityRegistry()

    # Load scan report
    scan_models = load_scan_report(report_path)

    added = 0
    for model_data in scan_models:
        model_id = model_data.get("id", "")
        # Don't overwrite hand-curated entries
        if reg.get(model_id):
            continue

        spec = _scan_model_to_spec(model_data)
        reg.register(spec)
        added += 1

    print(f"[Auto Registry] {reg.model_count} models loaded "
          f"({added} from scan, {reg.model_count - added} hand-curated)")
    print(f"[Auto Registry] Providers: {reg.list_providers()}")

    return reg


# CLI
if __name__ == "__main__":
    reg = build_full_registry()
    print(f"\nTotal models: {reg.model_count}")
    print(f"Available: {reg.available_count}")
    print(f"Providers: {reg.list_providers()}")

    # Show capability coverage
    domains = set()
    for m in reg._models.values():
        for c in m.capabilities:
            domains.add(f"{c.domain}:{c.skill}")
    print(f"\nCapability coverage ({len(domains)} unique):")
    for d in sorted(domains):
        count = len(reg.find_by_capability(d.split(":")[0], d.split(":")[1], min_score=0.0))
        print(f"  {d:30s} {count} models")
