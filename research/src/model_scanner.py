"""
Model Scanner — Discovers useful AI models across ALL 9 providers.

Comprehensive scan of:
- HuggingFace: Trending, text-gen, embeddings, code, vision, audio, agents (~15 searches)
- Ollama Cloud: All available models (via /v1/models)
- OpenRouter: All models with pricing info
- Groq: All available fast-inference models
- Google: Gemini model family
- NVIDIA: NIM catalog models

Evaluates each model against our 13 capability gaps and 6 AGI goals.
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
    provider: str
    description: str
    parameters: str  # e.g. "7B", "70B", "unknown"
    capabilities: list[str]
    relevance_score: float  # 0.0-1.0
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
    providers_scanned: dict[str, int] = field(default_factory=dict)
    scan_duration_s: float = 0.0


# --- Capability Gap Detection ---

COVERED_CAPABILITIES = {
    "reasoning:general", "reasoning:math", "reasoning:logic",
    "code:python", "code:typescript", "code:rust", "code:debugging",
    "creative:writing", "analysis:research", "analysis:summarization",
    "analysis:classification",
}

DESIRED_CAPABILITIES = {
    "code:review": "Automated code review and security analysis",
    "vision:ocr": "Document/screenshot understanding",
    "vision:diagram": "Architecture diagram interpretation",
    "vision:general": "General image understanding",
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

RELEVANCE_KEYWORDS = {
    # G1: Autonomous Agency
    "agent", "autonomous", "planning", "tool-use", "function-calling",
    "agentic", "goal", "decision", "tool_use", "function_call",
    # G2: Self-Improvement
    "self-improve", "reflection", "metacognition", "self-refine",
    "reward-model", "rlhf", "dpo", "grpo", "self-play",
    # G3: Memory
    "embedding", "retrieval", "rag", "long-context", "memory",
    "knowledge-graph", "vector", "1m-context", "million-context",
    # G4: Orchestration
    "mixture", "router", "ensemble", "multi-model", "orchestrat",
    "small-model", "distill", "speculative", "moe",
    # G5: Research
    "research", "paper", "scientific", "analysis", "reasoning",
    "thinking", "chain-of-thought", "cot",
    # G6: Consciousness
    "cognitive", "attention", "consciousness", "theory-of-mind",
}


def _extract_params(name: str, tags: list[str] = None, extra: str = "") -> str:
    """Extract parameter count from model name/tags."""
    text = f"{name} {extra} {' '.join(tags or [])}".upper()
    import re
    # Match patterns like "70B", "7B", "3.5B", "1.5B", "405B"
    m = re.search(r'(\d+\.?\d*)\s*B(?:\b|_)', text)
    if m:
        return f"{m.group(1)}B"
    return "unknown"


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

    matched_keywords = []
    for kw in RELEVANCE_KEYWORDS:
        if kw in text:
            matched_keywords.append(kw)
            score += 0.06

    if matched_keywords:
        reasons.append(f"Keywords: {', '.join(matched_keywords[:6])}")

    for cap_key, cap_desc in DESIRED_CAPABILITIES.items():
        domain, skill = cap_key.split(":")
        if domain in text and skill in text:
            score += 0.15
            reasons.append(f"Fills gap: {cap_key}")

    if any(t in text for t in ("embed", "embedding", "sentence-transform", "bge", "e5", "gte")):
        score += 0.15
        reasons.append("Embedding model (valuable for memory)")

    param_lower = parameters.lower()
    if any(s in param_lower for s in ("1b", "1.5b", "2b", "3b", "3.5b", "4b", "7b", "8b")):
        score += 0.08
        reasons.append(f"Small/local-runnable ({parameters})")

    if "tool" in text or "function" in text or "function-calling" in tags:
        score += 0.1
        reasons.append("Tool/function calling")

    if "german" in text or "deutsch" in text or "multilingual" in text or "multi-language" in text:
        score += 0.08
        reasons.append("German/multilingual")

    if any(t in text for t in ("code", "coder", "starcoder", "deepseek-coder", "codestral")):
        score += 0.06
        reasons.append("Code-focused")

    if any(t in text for t in ("vision", "vl", "multimodal", "image", "ocr")):
        score += 0.08
        reasons.append("Vision/multimodal")

    if any(t in text for t in ("whisper", "speech", "tts", "audio", "voice")):
        score += 0.08
        reasons.append("Audio/speech")

    if any(t in text for t in ("thinking", "reasoning", "r1", "o1", "o3", "cot")):
        score += 0.08
        reasons.append("Advanced reasoning/thinking")

    return min(score, 1.0), reasons


def _classify_recommendation(score: float, cost: str) -> str:
    if score >= 0.45 and cost in ("free", "cheap"):
        return "integrate"
    if score >= 0.30:
        return "test"
    if score >= 0.15:
        return "monitor"
    return "skip"


def _make_model(
    id: str, name: str, provider: str, desc: str, params: str,
    tags: list[str], cost: str, url: str = "",
    ctx: int | None = None, downloads: int | None = None, likes: int | None = None,
) -> DiscoveredModel | None:
    """Score and create a DiscoveredModel, or None if irrelevant."""
    score, reasons = _score_model_relevance(name, desc, tags, params)
    if score < 0.10:
        return None
    return DiscoveredModel(
        id=id, name=name, provider=provider, description=desc[:250],
        parameters=params, capabilities=[r.split(": ")[-1] for r in reasons],
        relevance_score=score, relevance_reasons=reasons,
        cost=cost, context_window=ctx, downloads=downloads, likes=likes,
        url=url, recommendation=_classify_recommendation(score, cost),
    )


# === HuggingFace ===

async def scan_huggingface() -> list[DiscoveredModel]:
    """Comprehensive HuggingFace scan — 15+ search categories."""
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    headers = {"Authorization": f"Bearer {hf_token}"} if hf_token else {}

    searches = [
        # Text Generation — trending, most downloaded, recently updated
        {"sort": "trending", "pipeline_tag": "text-generation", "limit": 50},
        {"sort": "downloads", "pipeline_tag": "text-generation", "limit": 50, "direction": -1},
        {"sort": "lastModified", "pipeline_tag": "text-generation", "limit": 50},
        # Embeddings
        {"sort": "trending", "pipeline_tag": "sentence-similarity", "limit": 50},
        {"sort": "downloads", "pipeline_tag": "sentence-similarity", "limit": 30, "direction": -1},
        {"sort": "trending", "pipeline_tag": "feature-extraction", "limit": 30},
        # Code
        {"search": "code coder programming", "sort": "trending", "pipeline_tag": "text-generation", "limit": 40},
        # Vision/Multimodal
        {"sort": "trending", "pipeline_tag": "image-text-to-text", "limit": 40},
        {"sort": "trending", "pipeline_tag": "visual-question-answering", "limit": 20},
        # Audio
        {"sort": "trending", "pipeline_tag": "automatic-speech-recognition", "limit": 30},
        {"sort": "trending", "pipeline_tag": "text-to-speech", "limit": 20},
        # Agent/Tool
        {"search": "agent tool function calling agentic", "sort": "trending", "pipeline_tag": "text-generation", "limit": 40},
        # Reasoning/Thinking
        {"search": "thinking reasoning chain-of-thought", "sort": "trending", "pipeline_tag": "text-generation", "limit": 30},
        # Small/Efficient
        {"search": "small efficient 1b 3b 4b 7b 8b", "sort": "trending", "pipeline_tag": "text-generation", "limit": 30},
        # German/Multilingual
        {"search": "german deutsch multilingual", "sort": "trending", "pipeline_tag": "text-generation", "limit": 20},
    ]

    models: list[DiscoveredModel] = []
    seen: set[str] = set()

    async with httpx.AsyncClient(timeout=30) as client:
        for params in searches:
            try:
                resp = await client.get("https://huggingface.co/api/models", params=params, headers=headers)
                if resp.status_code != 200:
                    continue
                for item in resp.json():
                    model_id = item.get("modelId", item.get("id", ""))
                    if model_id in seen:
                        continue
                    seen.add(model_id)

                    tags = item.get("tags", [])
                    desc = item.get("description", "") or ""
                    p = _extract_params(model_id, tags)

                    m = _make_model(
                        id=model_id, name=model_id.split("/")[-1],
                        provider="huggingface", desc=desc if desc else f"Tags: {', '.join(tags[:8])}",
                        params=p, tags=tags,
                        cost="free" if not item.get("gated") else "moderate",
                        url=f"https://huggingface.co/{model_id}",
                        downloads=item.get("downloads"), likes=item.get("likes"),
                    )
                    if m:
                        models.append(m)

            except Exception as e:
                print(f"  [HuggingFace] Search failed: {e}")
            await asyncio.sleep(0.5)

    return models


# === Ollama Cloud ===

async def scan_ollama() -> list[DiscoveredModel]:
    """Scan Ollama Cloud API (v1/models) and local instance."""
    models: list[DiscoveredModel] = []
    ollama_key = os.environ.get("OLLAMA_API_KEY")

    endpoints = []
    if ollama_key:
        endpoints.append(("https://ollama.com/v1/models", {"Authorization": f"Bearer {ollama_key}"}))
    # Also try local Ollama
    endpoints.append(("http://localhost:11434/api/tags", {}))

    async with httpx.AsyncClient(timeout=15) as client:
        for url, headers in endpoints:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                items = data.get("models", data.get("data", []))

                for item in items:
                    if isinstance(item, dict):
                        name = item.get("name", item.get("id", ""))
                        desc = item.get("description", "") or name
                        size = item.get("size", 0)
                        details = item.get("details", {})
                        params_str = details.get("parameter_size", "")
                    else:
                        continue

                    p = _extract_params(name, extra=params_str or str(size))
                    source = "ollama-cloud" if "ollama.com" in url else "ollama-local"

                    m = _make_model(
                        id=f"ollama:{name}", name=name, provider=source,
                        desc=desc[:250], params=p, tags=[],
                        cost="free",
                        url=f"https://ollama.com/library/{name.split(':')[0]}",
                    )
                    if m:
                        models.append(m)

            except Exception as e:
                print(f"  [Ollama] {url} failed: {e}")

    return models


# === OpenRouter ===

async def scan_openrouter() -> list[DiscoveredModel]:
    """Scan ALL OpenRouter models with pricing."""
    models: list[DiscoveredModel] = []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models")
            if resp.status_code != 200:
                return models

            for item in resp.json().get("data", []):
                model_id = item.get("id", "")
                name = item.get("name", model_id)
                desc = item.get("description", "") or ""
                ctx = item.get("context_length", 0)

                prompt_price = float(item.get("pricing", {}).get("prompt", "1") or "1")
                compl_price = float(item.get("pricing", {}).get("completion", "1") or "1")

                if prompt_price == 0 and compl_price == 0:
                    cost = "free"
                elif compl_price < 0.001:
                    cost = "cheap"
                elif compl_price < 0.01:
                    cost = "moderate"
                else:
                    cost = "expensive"

                p = _extract_params(name, extra=model_id)

                m = _make_model(
                    id=f"openrouter:{model_id}", name=name, provider="openrouter",
                    desc=desc, params=p, tags=[],
                    cost=cost, url=f"https://openrouter.ai/models/{model_id}", ctx=ctx,
                )
                if m:
                    # Boost free models slightly
                    if cost == "free":
                        m.relevance_score = min(m.relevance_score + 0.08, 1.0)
                        m.relevance_reasons.append("Free on OpenRouter")
                        m.recommendation = _classify_recommendation(m.relevance_score, cost)
                    models.append(m)

    except Exception as e:
        print(f"  [OpenRouter] Scan failed: {e}")

    return models


# === Groq ===

async def scan_groq() -> list[DiscoveredModel]:
    """Scan Groq fast-inference models."""
    models: list[DiscoveredModel] = []
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        print("  [Groq] No GROQ_API_KEY, skipping")
        return models

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {groq_key}"},
            )
            if resp.status_code != 200:
                return models

            for item in resp.json().get("data", []):
                model_id = item.get("id", "")
                ctx = item.get("context_window", 0)
                p = _extract_params(model_id)

                # All Groq models are valuable (free + ultra-fast)
                score, reasons = _score_model_relevance(model_id, f"Groq fast-inference {model_id}", [], p)
                score = max(score, 0.3)  # Minimum score for Groq (free + fast)
                score = min(score + 0.15, 1.0)
                reasons.append("Ultra-fast Groq inference (free)")

                models.append(DiscoveredModel(
                    id=f"groq:{model_id}", name=model_id, provider="groq",
                    description=f"Groq: {model_id} (ctx: {ctx:,})",
                    parameters=p, capabilities=[r.split(": ")[-1] for r in reasons],
                    relevance_score=score, relevance_reasons=reasons,
                    cost="free", context_window=ctx,
                    url="https://console.groq.com/docs/models",
                    recommendation=_classify_recommendation(score, "free"),
                ))

    except Exception as e:
        print(f"  [Groq] Scan failed: {e}")

    return models


# === Google Gemini ===

async def scan_google() -> list[DiscoveredModel]:
    """Scan Google Gemini models."""
    models: list[DiscoveredModel] = []
    google_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not google_key:
        print("  [Google] No GEMINI_API_KEY, skipping")
        return models

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={google_key}",
            )
            if resp.status_code != 200:
                return models

            for item in resp.json().get("models", []):
                model_id = item.get("name", "").replace("models/", "")
                name = item.get("displayName", model_id)
                desc = item.get("description", "") or ""
                ctx = item.get("inputTokenLimit", 0)
                out_tokens = item.get("outputTokenLimit", 0)

                p = _extract_params(name)

                m = _make_model(
                    id=f"google:{model_id}", name=name, provider="google",
                    desc=desc, params=p, tags=item.get("supportedGenerationMethods", []),
                    cost="cheap", ctx=ctx,
                )
                if m:
                    models.append(m)

    except Exception as e:
        print(f"  [Google] Scan failed: {e}")

    return models


# === NVIDIA NIM ===

async def scan_nvidia() -> list[DiscoveredModel]:
    """Scan NVIDIA NIM catalog."""
    models: list[DiscoveredModel] = []
    nvidia_key = os.environ.get("NVIDIA_API_KEY")
    if not nvidia_key:
        print("  [NVIDIA] No NVIDIA_API_KEY, skipping")
        return models

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://integrate.api.nvidia.com/v1/models",
                headers={"Authorization": f"Bearer {nvidia_key}"},
            )
            if resp.status_code != 200:
                return models

            for item in resp.json().get("data", []):
                model_id = item.get("id", "")
                p = _extract_params(model_id)

                # NVIDIA NIM models are all API-accessible
                score, reasons = _score_model_relevance(model_id, f"NVIDIA NIM {model_id}", [], p)
                if score < 0.05:
                    score = 0.15  # Minimum for NVIDIA models
                    reasons.append("NVIDIA NIM API model")

                models.append(DiscoveredModel(
                    id=f"nvidia:{model_id}", name=model_id, provider="nvidia",
                    description=f"NVIDIA NIM: {model_id}",
                    parameters=p, capabilities=[r.split(": ")[-1] for r in reasons],
                    relevance_score=score, relevance_reasons=reasons,
                    cost="cheap", url="https://build.nvidia.com/explore",
                    recommendation=_classify_recommendation(score, "cheap"),
                ))

    except Exception as e:
        print(f"  [NVIDIA] Scan failed: {e}")

    return models


# === xAI / Grok ===

async def scan_xai() -> list[DiscoveredModel]:
    """Scan xAI Grok models."""
    models: list[DiscoveredModel] = []
    xai_key = os.environ.get("XAI_API_KEY")
    if not xai_key:
        print("  [xAI] No XAI_API_KEY, skipping")
        return models

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.x.ai/v1/models",
                headers={"Authorization": f"Bearer {xai_key}"},
            )
            if resp.status_code != 200:
                return models

            for item in resp.json().get("data", []):
                model_id = item.get("id", "")
                ctx = item.get("context_length", 0) or item.get("context_window", 0)
                p = _extract_params(model_id)

                score, reasons = _score_model_relevance(
                    model_id, f"xAI Grok {model_id} reasoning thinking agentic", [], p,
                )
                score = max(score, 0.3)  # Grok models are competitive
                reasons.append("xAI Grok (fast reasoning)")

                models.append(DiscoveredModel(
                    id=f"xai:{model_id}", name=model_id, provider="xai",
                    description=f"xAI Grok: {model_id}" + (f" (ctx: {ctx:,})" if ctx else ""),
                    parameters=p, capabilities=[r.split(": ")[-1] for r in reasons],
                    relevance_score=score, relevance_reasons=reasons,
                    cost="cheap", context_window=ctx or None,
                    url="https://console.x.ai",
                    recommendation=_classify_recommendation(score, "cheap"),
                ))

    except Exception as e:
        print(f"  [xAI] Scan failed: {e}")

    return models


# === Main Scanner ===

async def scan_all_providers(verbose: bool = True) -> ModelScanReport:
    """Scan ALL providers in parallel and generate unified report."""
    start = datetime.now()

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"  Way2AGI Model Scanner — Full Provider Scan")
        print(f"  {start.isoformat()}")
        print(f"{'=' * 60}\n")

    gaps = sorted(set(DESIRED_CAPABILITIES.keys()) - COVERED_CAPABILITIES)

    if verbose:
        print(f"  Capability gaps to fill: {len(gaps)}")
        for g in gaps:
            print(f"    - {g}: {DESIRED_CAPABILITIES.get(g, '')}")
        print()

    # Launch ALL provider scans in parallel
    providers = {
        "HuggingFace": scan_huggingface,
        "Ollama": scan_ollama,
        "OpenRouter": scan_openrouter,
        "Groq": scan_groq,
        "Google": scan_google,
        "NVIDIA": scan_nvidia,
        "xAI": scan_xai,
    }

    if verbose:
        for i, name in enumerate(providers, 1):
            print(f"  [{i}/{len(providers)}] Scanning {name}...")

    tasks = {name: asyncio.create_task(fn()) for name, fn in providers.items()}

    provider_counts: dict[str, int] = {}
    all_models: list[DiscoveredModel] = []

    for name, task in tasks.items():
        try:
            result = await task
            provider_counts[name] = len(result)
            all_models.extend(result)
            if verbose:
                print(f"  {name}: {len(result)} models found")
        except Exception as e:
            provider_counts[name] = 0
            if verbose:
                print(f"  {name}: FAILED ({e})")

    # Sort by relevance
    all_models.sort(key=lambda m: m.relevance_score, reverse=True)

    # Deduplicate — same base model across providers, keep highest-scored
    seen: set[str] = set()
    unique: list[DiscoveredModel] = []
    for m in all_models:
        # Normalize: remove version suffixes, lowercase
        base = m.name.lower().replace("-instruct", "").replace("-chat", "")
        base = base.split(":")[0].rstrip("0123456789.")
        key = base
        if key not in seen:
            seen.add(key)
            unique.append(m)

    duration = (datetime.now() - start).total_seconds()

    report = ModelScanReport(
        date=date.today().isoformat(),
        total_scanned=len(all_models),
        relevant_models=sum(1 for m in unique if m.relevance_score >= 0.15),
        integrate_candidates=sum(1 for m in unique if m.recommendation == "integrate"),
        test_candidates=sum(1 for m in unique if m.recommendation == "test"),
        models=unique,
        capability_gaps=gaps,
        providers_scanned=provider_counts,
        scan_duration_s=duration,
    )

    if verbose:
        print_model_report(report)

    return report


def print_model_report(report: ModelScanReport) -> None:
    """Print human-readable model scan report."""
    print(f"\n{'=' * 60}")
    print(f"  Model Scan Results — {report.date}")
    print(f"{'=' * 60}")
    print(f"  Total scanned:         {report.total_scanned}")
    print(f"  Unique relevant:       {report.relevant_models}")
    print(f"  INTEGRATE candidates:  {report.integrate_candidates}")
    print(f"  TEST candidates:       {report.test_candidates}")
    print(f"  Scan duration:         {report.scan_duration_s:.1f}s")
    print(f"  Providers:             {report.providers_scanned}")
    print(f"{'=' * 60}\n")

    for rec_type in ("integrate", "test", "monitor"):
        models = [m for m in report.models if m.recommendation == rec_type]
        if not models:
            continue

        label = {"integrate": "INTEGRATE", "test": "TEST", "monitor": "MONITOR"}[rec_type]
        limit = 15 if rec_type == "integrate" else 10
        print(f"  --- {label} ({len(models)}) ---")
        for m in models[:limit]:
            print(f"  [{m.provider:14s}] {m.relevance_score:.2f} | {m.name[:40]:40s} | {m.parameters:8s} | {m.cost}")
            for r in m.relevance_reasons[:3]:
                print(f"                            -> {r}")
            if m.url:
                print(f"                            {m.url}")
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
        "providers_scanned": report.providers_scanned,
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
        ],
    }

    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return filepath


async def main() -> None:
    report = await scan_all_providers(verbose=True)
    out = Path.home() / ".way2agi" / "research"
    path = save_model_report(report, out)
    print(f"\nReport saved: {path}")


if __name__ == "__main__":
    asyncio.run(main())
