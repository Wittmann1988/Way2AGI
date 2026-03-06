"""
Model Scanner — Discovers useful AI models across providers.

Scans HuggingFace, Ollama, and OpenRouter for models that could
strengthen our Capability Registry. Evaluates each model against
capability gaps in our current setup.

Searches for:
- New/trending models on HuggingFace (text-generation, code, embedding)
- Available Ollama models (free, local-runnable)
- OpenRouter free-tier models
- Models with specific strengths we lack (vision, audio, tool-use, multilingual)
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx


# --- Types ---

@dataclass
class DiscoveredModel:
    """A model discovered during scanning."""
    id: str
    name: str
    provider: str  # huggingface | ollama | openrouter
    description: str
    parameters: str  # e.g. "7B", "70B", "unknown"
    capabilities: list[str]  # inferred from tags/description
    relevance_score: float  # 0.0-1.0 how useful for Way2AGI
    relevance_reasons: list[str]
    cost: str  # "free" | "cheap" | "moderate" | "expensive"
    context_window: int | None = None
    downloads: int | None = None
    likes: int | None = None
    url: str = ""
    recommendation: str = "monitor"  # integrate | test | monitor | skip


@dataclass
class ModelScanReport:
    """Result of a model scan."""
    date: str
    total_scanned: int
    relevant_models: int
    integrate_candidates: int
    test_candidates: int
    models: list[DiscoveredModel]
    capability_gaps: list[str]
    scan_duration_s: float = 0.0


# --- Capability Gap Detection ---

# What we currently have covered (from registry.py)
COVERED_CAPABILITIES = {
    "reasoning:general", "reasoning:math", "reasoning:logic",
    "code:python", "code:typescript", "code:rust", "code:debugging",
    "creative:writing", "analysis:research", "analysis:summarization",
    "analysis:classification",
}

# What we WANT but don't have well covered
DESIRED_CAPABILITIES = {
    "code:review": "Automated code review and security analysis",
    "vision:ocr": "Document/screenshot understanding",
    "vision:diagram": "Architecture diagram interpretation",
    "audio:transcription": "Speech-to-text (Whisper alternatives)",
    "audio:generation": "Text-to-speech alternatives",
    "embedding:text": "High-quality text embeddings for memory",
    "embedding:code": "Code embeddings for similarity search",
    "reasoning:planning": "Multi-step planning and task decomposition",
    "reasoning:reflection": "Self-critique and metacognition",
    "multilingual:de": "German language understanding/generation",
    "agent:tool_use": "Function calling and tool use",
    "agent:memory": "Long-context or memory-augmented models",
    "safety:alignment": "Alignment and safety evaluation",
}

# Keywords that signal relevance to our goals
RELEVANCE_KEYWORDS = {
    # G1: Autonomous Agency
    "agent", "autonomous", "planning", "tool-use", "function-calling",
    "agentic", "goal", "decision",
    # G2: Self-Improvement
    "self-improve", "reflection", "metacognition", "self-refine",
    "reward-model", "rlhf", "dpo", "grpo",
    # G3: Memory
    "embedding", "retrieval", "rag", "long-context", "memory",
    "knowledge-graph", "vector",
    # G4: Orchestration
    "mixture", "router", "ensemble", "multi-model", "orchestrat",
    "small-model", "distill",
    # G5: Research
    "research", "paper", "scientific", "analysis", "reasoning",
    # G6: Consciousness
    "cognitive", "attention", "consciousness", "theory-of-mind",
}


def _score_model_relevance(
    name: str,
    description: str,
    tags: list[str],
    parameters: str,
) -> tuple[float, list[str]]:
    """Score how relevant a model is for Way2AGI's goals."""
    score = 0.0
    reasons: list[str] = []
    text = f"{name} {description} {' '.join(tags)}".lower()

    # Check against relevance keywords
    matched_keywords = []
    for kw in RELEVANCE_KEYWORDS:
        if kw in text:
            matched_keywords.append(kw)
            score += 0.08

    if matched_keywords:
        reasons.append(f"Keywords: {', '.join(matched_keywords[:5])}")

    # Check against desired capabilities we lack
    for cap_key, cap_desc in DESIRED_CAPABILITIES.items():
        domain, skill = cap_key.split(":")
        if domain in text and skill in text:
            score += 0.15
            reasons.append(f"Fills gap: {cap_key}")

    # Embedding models are highly valuable
    if any(t in text for t in ("embed", "embedding", "sentence-transform")):
        score += 0.12
        reasons.append("Embedding model (valuable for memory)")

    # Small models that can run locally get a bonus
    param_lower = parameters.lower()
    if any(s in param_lower for s in ("1b", "2b", "3b", "4b", "7b", "8b")):
        score += 0.1
        reasons.append(f"Small enough for local deployment ({parameters})")

    # Tool-use/function-calling models
    if "tool" in text or "function" in text or "function-calling" in tags:
        score += 0.1
        reasons.append("Supports tool/function calling")

    # German language support
    if "german" in text or "deutsch" in text or "multilingual" in text:
        score += 0.08
        reasons.append("German/multilingual support")

    # Code models
    if "code" in text or "coder" in text or "starcoder" in text:
        score += 0.05
        reasons.append("Code-focused model")

    return min(score, 1.0), reasons


def _classify_recommendation(score: float, cost: str) -> str:
    """Classify model into action categories."""
    if score >= 0.5 and cost in ("free", "cheap"):
        return "integrate"
    if score >= 0.35:
        return "test"
    if score >= 0.2:
        return "monitor"
    return "skip"


# --- HuggingFace Scanner ---

async def scan_huggingface(max_models: int = 100) -> list[DiscoveredModel]:
    """Scan HuggingFace for trending/useful models."""
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    headers = {}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    models: list[DiscoveredModel] = []

    # Search categories relevant to us
    searches = [
        # Trending text generation
        {"search": "", "sort": "trending", "pipeline_tag": "text-generation", "limit": 30},
        # Embedding models
        {"search": "", "sort": "trending", "pipeline_tag": "sentence-similarity", "limit": 20},
        # Recently updated agent/tool models
        {"search": "agent tool function", "sort": "lastModified", "pipeline_tag": "text-generation", "limit": 20},
        # Small efficient models
        {"search": "small efficient 4b 7b 8b", "sort": "trending", "pipeline_tag": "text-generation", "limit": 15},
        # Code models
        {"search": "code programming", "sort": "trending", "pipeline_tag": "text-generation", "limit": 15},
    ]

    seen: set[str] = set()

    async with httpx.AsyncClient(timeout=30) as client:
        for search_params in searches:
            try:
                resp = await client.get(
                    "https://huggingface.co/api/models",
                    params=search_params,
                    headers=headers,
                )
                if resp.status_code != 200:
                    continue

                for item in resp.json():
                    model_id = item.get("modelId", item.get("id", ""))
                    if model_id in seen:
                        continue
                    seen.add(model_id)

                    tags = item.get("tags", [])
                    desc = item.get("description", "") or ""
                    # Extract parameter count from tags or id
                    params = "unknown"
                    for tag in tags:
                        if tag.endswith("B") and tag[:-1].replace(".", "").isdigit():
                            params = tag
                            break

                    score, reasons = _score_model_relevance(
                        model_id, desc, tags, params,
                    )

                    if score < 0.15:
                        continue

                    cost = "free" if item.get("gated") is not True else "moderate"

                    models.append(DiscoveredModel(
                        id=model_id,
                        name=model_id.split("/")[-1],
                        provider="huggingface",
                        description=desc[:200] if desc else f"Tags: {', '.join(tags[:8])}",
                        parameters=params,
                        capabilities=[r.split(": ")[-1] for r in reasons],
                        relevance_score=score,
                        relevance_reasons=reasons,
                        cost=cost,
                        downloads=item.get("downloads"),
                        likes=item.get("likes"),
                        url=f"https://huggingface.co/{model_id}",
                        recommendation=_classify_recommendation(score, cost),
                    ))

            except Exception as e:
                print(f"[Model Scanner] HuggingFace search failed: {e}")
                continue

            await asyncio.sleep(1)  # Rate limit

    return models


# --- Ollama Scanner ---

async def scan_ollama() -> list[DiscoveredModel]:
    """Scan Ollama library for available models."""
    models: list[DiscoveredModel] = []

    # Ollama Cloud API - list available models
    ollama_key = os.environ.get("OLLAMA_API_KEY")
    if not ollama_key:
        print("[Model Scanner] No OLLAMA_API_KEY, skipping Ollama Cloud scan")
        return models

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://ollama.com/api/tags",
                headers={"Authorization": f"Bearer {ollama_key}"},
            )
            if resp.status_code != 200:
                # Try local Ollama
                resp = await client.get("http://localhost:11434/api/tags")
                if resp.status_code != 200:
                    return models

            data = resp.json()
            for item in data.get("models", []):
                name = item.get("name", "")
                desc = item.get("description", "") or name
                size = item.get("size", 0)
                params = f"{size // 1_000_000_000}B" if size > 1_000_000 else "unknown"

                score, reasons = _score_model_relevance(
                    name, desc, [], params,
                )

                models.append(DiscoveredModel(
                    id=f"ollama:{name}",
                    name=name,
                    provider="ollama",
                    description=desc[:200],
                    parameters=params,
                    capabilities=[r.split(": ")[-1] for r in reasons],
                    relevance_score=score,
                    relevance_reasons=reasons,
                    cost="free",
                    url=f"https://ollama.com/library/{name.split(':')[0]}",
                    recommendation=_classify_recommendation(score, "free"),
                ))

    except Exception as e:
        print(f"[Model Scanner] Ollama scan failed: {e}")

    return models


# --- OpenRouter Scanner ---

async def scan_openrouter() -> list[DiscoveredModel]:
    """Scan OpenRouter for free/cheap models."""
    models: list[DiscoveredModel] = []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models")
            if resp.status_code != 200:
                return models

            data = resp.json()
            for item in data.get("data", []):
                model_id = item.get("id", "")
                name = item.get("name", model_id)
                desc = item.get("description", "") or ""
                ctx = item.get("context_length", 0)

                # Determine cost
                prompt_price = float(item.get("pricing", {}).get("prompt", "1") or "1")
                completion_price = float(item.get("pricing", {}).get("completion", "1") or "1")

                if prompt_price == 0 and completion_price == 0:
                    cost = "free"
                elif completion_price < 0.001:
                    cost = "cheap"
                elif completion_price < 0.01:
                    cost = "moderate"
                else:
                    cost = "expensive"

                # Extract params from name
                params = "unknown"
                for token in name.split():
                    t = token.upper().rstrip(")")
                    if t.endswith("B") and t[:-1].replace(".", "").isdigit():
                        params = t
                        break

                score, reasons = _score_model_relevance(
                    model_id, desc, [], params,
                )

                # Boost free models
                if cost == "free":
                    score = min(score + 0.1, 1.0)
                    reasons.append("Free tier on OpenRouter")

                if score < 0.15:
                    continue

                models.append(DiscoveredModel(
                    id=f"openrouter:{model_id}",
                    name=name,
                    provider="openrouter",
                    description=desc[:200],
                    parameters=params,
                    capabilities=[r.split(": ")[-1] for r in reasons],
                    relevance_score=score,
                    relevance_reasons=reasons,
                    cost=cost,
                    context_window=ctx,
                    url=f"https://openrouter.ai/models/{model_id}",
                    recommendation=_classify_recommendation(score, cost),
                ))

    except Exception as e:
        print(f"[Model Scanner] OpenRouter scan failed: {e}")

    return models


# --- Main Scanner ---

async def scan_all_providers(
    verbose: bool = True,
) -> ModelScanReport:
    """Scan all providers and generate a unified report."""
    start = datetime.now()

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"  Way2AGI Model Scanner")
        print(f"  {start.isoformat()}")
        print(f"{'=' * 60}\n")

    # Detect capability gaps
    all_desired = set(DESIRED_CAPABILITIES.keys())
    gaps = sorted(all_desired - COVERED_CAPABILITIES)

    if verbose:
        print(f"  Capability gaps to fill: {len(gaps)}")
        for g in gaps:
            print(f"    - {g}: {DESIRED_CAPABILITIES.get(g, '')}")
        print()

    # Scan all providers in parallel
    if verbose:
        print("  [1/3] Scanning HuggingFace...")
    hf_task = asyncio.create_task(scan_huggingface())

    if verbose:
        print("  [2/3] Scanning Ollama...")
    ollama_task = asyncio.create_task(scan_ollama())

    if verbose:
        print("  [3/3] Scanning OpenRouter...")
    or_task = asyncio.create_task(scan_openrouter())

    hf_models = await hf_task
    ollama_models = await ollama_task
    or_models = await or_task

    all_models = hf_models + ollama_models + or_models

    # Sort by relevance
    all_models.sort(key=lambda m: m.relevance_score, reverse=True)

    # Deduplicate by base model name
    seen_bases: set[str] = set()
    unique_models: list[DiscoveredModel] = []
    for m in all_models:
        base = m.name.lower().split(":")[0].split("-")[0]
        key = f"{base}_{m.provider}"
        if key not in seen_bases:
            seen_bases.add(key)
            unique_models.append(m)

    duration = (datetime.now() - start).total_seconds()

    report = ModelScanReport(
        date=date.today().isoformat(),
        total_scanned=len(all_models),
        relevant_models=sum(1 for m in unique_models if m.relevance_score >= 0.2),
        integrate_candidates=sum(1 for m in unique_models if m.recommendation == "integrate"),
        test_candidates=sum(1 for m in unique_models if m.recommendation == "test"),
        models=unique_models,
        capability_gaps=gaps,
        scan_duration_s=duration,
    )

    if verbose:
        print_model_report(report)

    return report


def print_model_report(report: ModelScanReport) -> None:
    """Print human-readable model scan report."""
    print(f"\n{'=' * 60}")
    print(f"  Model Scan Results - {report.date}")
    print(f"{'=' * 60}")
    print(f"  Total scanned:         {report.total_scanned}")
    print(f"  Relevant:              {report.relevant_models}")
    print(f"  INTEGRATE candidates:  {report.integrate_candidates}")
    print(f"  TEST candidates:       {report.test_candidates}")
    print(f"  Scan duration:         {report.scan_duration_s:.1f}s")
    print(f"{'=' * 60}\n")

    # Show top models by category
    for rec_type in ("integrate", "test", "monitor"):
        models = [m for m in report.models if m.recommendation == rec_type]
        if not models:
            continue

        label = {"integrate": "INTEGRATE", "test": "TEST", "monitor": "MONITOR"}[rec_type]
        print(f"  --- {label} ({len(models)}) ---")
        for m in models[:10]:
            print(f"  [{m.provider:12s}] {m.relevance_score:.2f} | {m.name[:40]:40s} | {m.parameters:6s} | {m.cost}")
            for r in m.relevance_reasons[:2]:
                print(f"                          -> {r}")
            print(f"                          {m.url}")
        print()


def save_model_report(report: ModelScanReport, output_dir: str | Path) -> Path:
    """Save model scan report as JSON."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    filepath = out / f"models-{report.date}.json"
    data = {
        "date": report.date,
        "total_scanned": report.total_scanned,
        "relevant_models": report.relevant_models,
        "integrate_candidates": report.integrate_candidates,
        "test_candidates": report.test_candidates,
        "capability_gaps": report.capability_gaps,
        "scan_duration_s": report.scan_duration_s,
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "provider": m.provider,
                "description": m.description,
                "parameters": m.parameters,
                "capabilities": m.capabilities,
                "relevance_score": m.relevance_score,
                "relevance_reasons": m.relevance_reasons,
                "cost": m.cost,
                "context_window": m.context_window,
                "downloads": m.downloads,
                "likes": m.likes,
                "url": m.url,
                "recommendation": m.recommendation,
            }
            for m in report.models
            if m.recommendation != "skip"
        ],
    }

    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return filepath


# --- CLI Entry Point ---

async def main() -> None:
    report = await scan_all_providers(verbose=True)

    out = Path.home() / ".way2agi" / "research"
    path = save_model_report(report, out)
    print(f"\nReport saved: {path}")


if __name__ == "__main__":
    asyncio.run(main())
