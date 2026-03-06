"""
Training Data Generator — Multi-model traces for SFT/DPO training.

Queries multiple models with curated prompts to generate training pairs.
Output: JSONL files ready for HuggingFace SFT/DPO training.

Pipeline: Generate traces -> JSONL -> HF Dataset -> Train SFT/DPO -> GGUF -> Ollama
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


@dataclass
class TrainingExample:
    """A single training example (prompt + response pair)."""
    prompt: str
    response: str
    model_id: str
    provider: str
    domain: str
    quality_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DPOPair:
    """A DPO training pair (prompt + chosen + rejected)."""
    prompt: str
    chosen: str
    rejected: str
    chosen_model: str
    rejected_model: str
    domain: str


# --- Curated training prompts per domain ---

TRAINING_PROMPTS: dict[str, list[dict[str, str]]] = {
    "reasoning": [
        {
            "system": "Du bist ein praeziser Denkassistent. Erklaere Schritt fuer Schritt.",
            "prompt": "Erklaere den Unterschied zwischen deduktivem und induktivem Denken mit jeweils einem Beispiel aus der Informatik.",
        },
        {
            "system": "You are a logical reasoning expert.",
            "prompt": "A farmer has 17 sheep. All but 9 die. How many sheep are left? Explain your reasoning step by step.",
        },
        {
            "system": "You are a critical thinking assistant.",
            "prompt": "Analyze this argument: 'AI will replace all jobs because it can learn faster than humans.' Identify logical fallacies and provide a nuanced counterargument.",
        },
        {
            "system": "Du bist ein Problemloeser.",
            "prompt": "Ein Zug faehrt um 8:00 mit 120km/h los. Ein zweiter Zug faehrt um 9:00 mit 160km/h in die gleiche Richtung. Wann holt der zweite Zug den ersten ein?",
        },
    ],
    "code": [
        {
            "system": "You are an expert Python developer. Write clean, efficient code.",
            "prompt": "Write a Python function that implements a thread-safe LRU cache with TTL support. Include type hints and docstrings.",
        },
        {
            "system": "You are a systems programmer.",
            "prompt": "Implement a simple circuit breaker pattern in Python using asyncio. It should track failures, open after threshold, and auto-recover after timeout.",
        },
        {
            "system": "Du bist ein Code-Review-Experte.",
            "prompt": "Reviewe diesen Code und finde Bugs:\n```python\ndef merge_sorted(a, b):\n    result = []\n    i = j = 0\n    while i < len(a) and j < len(b):\n        if a[i] <= b[j]:\n            result.append(a[i])\n            i += 1\n        else:\n            result.append(b[j])\n            j += 1\n    return result\n```",
        },
        {
            "system": "You are a TypeScript expert.",
            "prompt": "Implement a generic event emitter in TypeScript with type-safe event names and payloads using mapped types and conditional types.",
        },
    ],
    "agent": [
        {
            "system": "You are an AI agent design specialist.",
            "prompt": "Design a multi-agent system where 3 specialized agents (researcher, coder, reviewer) collaborate to solve a complex software engineering task. Define their communication protocol.",
        },
        {
            "system": "You are an autonomous agent.",
            "prompt": "You have access to tools: search_web, read_file, write_file, run_code. Plan how to research and implement a rate limiter for an API, step by step.",
        },
    ],
    "analysis": [
        {
            "system": "You are a research analyst.",
            "prompt": "Compare Mixture-of-Agents (MoA) vs Mixture-of-Experts (MoE) architectures. When should each be used? What are the trade-offs?",
        },
        {
            "system": "Du bist ein Technologie-Analyst.",
            "prompt": "Analysiere die Vor- und Nachteile von lokalen LLMs (Ollama) vs Cloud-APIs (OpenAI, Anthropic) fuer ein persoenliches AI-System. Beruecksichtige: Kosten, Latenz, Datenschutz, Qualitaet.",
        },
    ],
    "creative": [
        {
            "system": "You are a creative writing assistant with deep knowledge of AI and technology.",
            "prompt": "Write a short technical blog post (300 words) explaining Global Workspace Theory and how it could be applied to AI consciousness research.",
        },
    ],
    "multilingual": [
        {
            "system": "Du bist ein mehrsprachiger Assistent. Antworte immer in der Sprache der Frage.",
            "prompt": "Erklaere wie ein Transformer-Modell funktioniert. Verwende einfache Analogien die auch Nicht-Informatiker verstehen.",
        },
        {
            "system": "You are a multilingual AI. Respond in the language of the question.",
            "prompt": "What is retrieval-augmented generation (RAG) and why is it important for reducing hallucinations in LLMs?",
        },
    ],
}


# --- Provider-specific API calls ---

async def _call_openrouter(
    model_id: str, system: str, prompt: str, api_key: str
) -> str | None:
    """Call OpenRouter API."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 2048,
                "temperature": 0.7,
            },
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_groq(
    model_id: str, system: str, prompt: str, api_key: str
) -> str | None:
    """Call Groq API."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 2048,
                "temperature": 0.7,
            },
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_xai(
    model_id: str, system: str, prompt: str, api_key: str
) -> str | None:
    """Call xAI/Grok API."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 2048,
                "temperature": 0.7,
            },
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_google(
    model_id: str, system: str, prompt: str, api_key: str
) -> str | None:
    """Call Google Gemini API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.7},
            },
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        return parts[0]["text"] if parts else None


async def _call_nvidia(
    model_id: str, system: str, prompt: str, api_key: str
) -> str | None:
    """Call NVIDIA NIM API."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 2048,
                "temperature": 0.7,
            },
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_ollama(
    model_id: str, system: str, prompt: str, api_key: str
) -> str | None:
    """Call Ollama Cloud API."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://ollama.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 2048,
                "temperature": 0.7,
            },
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# Provider dispatch
_PROVIDER_CALLERS = {
    "openrouter": _call_openrouter,
    "groq": _call_groq,
    "xai": _call_xai,
    "google": _call_google,
    "nvidia": _call_nvidia,
    "ollama": _call_ollama,
    "ollama-cloud": _call_ollama,
}

_API_KEY_ENV = {
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "xai": "XAI_API_KEY",
    "google": "GEMINI_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "ollama": "OLLAMA_API_KEY",
    "ollama-cloud": "OLLAMA_API_KEY",
}


def _strip_provider_prefix(model_id: str, provider: str) -> str:
    """Remove provider prefix from model ID (e.g. 'groq:llama...' -> 'llama...')."""
    prefixes = [f"{provider}:", f"{provider}-"]
    for prefix in prefixes:
        if model_id.startswith(prefix):
            return model_id[len(prefix):]
    # Also handle 'openrouter:google/...' -> 'google/...'
    if ":" in model_id:
        return model_id.split(":", 1)[1]
    return model_id


async def call_model(
    model_id: str, provider: str, system: str, prompt: str
) -> str | None:
    """Call a model via its provider API. Returns response or None on failure."""
    caller = _PROVIDER_CALLERS.get(provider)
    if not caller:
        return None

    key_env = _API_KEY_ENV.get(provider, "")
    api_key = os.environ.get(key_env, "")
    if not api_key:
        return None

    # Strip provider prefix from model ID for API calls
    clean_id = _strip_provider_prefix(model_id, provider)

    try:
        return await caller(clean_id, system, prompt, api_key)
    except Exception:
        return None


# --- Training data generation ---

def _select_models_for_training(
    scan_report_path: Path | None = None,
    max_per_provider: int = 3,
) -> list[dict[str, str]]:
    """Select diverse models for training data generation."""
    if scan_report_path is None:
        scan_dir = Path.home() / ".way2agi" / "research"
        reports = sorted(scan_dir.glob("models-*.json"), reverse=True)
        if not reports:
            return []
        scan_report_path = reports[0]

    data = json.loads(scan_report_path.read_text(encoding="utf-8"))
    models = data.get("models", [])

    # Group by provider, pick top-scored per provider
    by_provider: dict[str, list[dict]] = {}
    for m in models:
        prov = m.get("provider", "unknown")
        # Skip embedding-only, image-gen, and audio-only models
        caps = [c.lower() for c in m.get("capabilities", [])]
        name_l = m.get("name", "").lower()
        desc_l = m.get("description", "").lower()
        if all(c in ("embedding", "audio", "speech") for c in caps) and caps:
            continue
        if any(kw in name_l for kw in ("embed", "bge-", "gte-", "e5-", "nomic-embed",
                                        "imagine", "image-gen", "tts", "whisper",
                                        "orpheus", "retriever")):
            continue
        if "embedding" in desc_l and "chat" not in desc_l and "instruct" not in desc_l:
            continue
        by_provider.setdefault(prov, []).append(m)

    selected = []
    # Skip NVIDIA (needs per-model API keys) and HuggingFace (no chat API)
    skip_providers = {"nvidia", "huggingface"}
    for prov, prov_models in by_provider.items():
        if prov not in _PROVIDER_CALLERS or prov in skip_providers:
            continue
        # Sort by relevance, take top N
        prov_models.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        for m in prov_models[:max_per_provider]:
            selected.append({"id": m["id"], "provider": prov, "name": m.get("name", m["id"])})

    return selected


async def generate_sft_data(
    output_dir: str | Path | None = None,
    max_per_provider: int = 3,
    domains: list[str] | None = None,
    verbose: bool = True,
) -> Path:
    """
    Generate SFT training data by querying multiple models.

    Returns path to the JSONL output file.
    """
    out = Path(output_dir or Path.home() / ".way2agi" / "training")
    out.mkdir(parents=True, exist_ok=True)

    models = _select_models_for_training(max_per_provider=max_per_provider)
    if not models:
        raise RuntimeError("No models found in scan report")

    target_domains = domains or list(TRAINING_PROMPTS.keys())

    if verbose:
        print(f"[Training] {len(models)} models selected from {len(set(m['provider'] for m in models))} providers")
        print(f"[Training] Domains: {target_domains}")
        print(f"[Training] Prompts per domain: {[len(TRAINING_PROMPTS.get(d,[])) for d in target_domains]}")

    examples: list[TrainingExample] = []
    total_calls = 0
    successful = 0

    for domain in target_domains:
        prompts = TRAINING_PROMPTS.get(domain, [])
        for prompt_data in prompts:
            system = prompt_data["system"]
            prompt = prompt_data["prompt"]

            # Query all models in parallel for this prompt
            tasks = []
            task_models = []
            for model in models:
                tasks.append(call_model(model["id"], model["provider"], system, prompt))
                task_models.append(model)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for model, result in zip(task_models, results):
                total_calls += 1
                if isinstance(result, str) and len(result) > 20:
                    successful += 1
                    examples.append(TrainingExample(
                        prompt=prompt,
                        response=result,
                        model_id=model["id"],
                        provider=model["provider"],
                        domain=domain,
                        quality_score=0.0,  # scored later
                        metadata={
                            "system": system,
                            "model_name": model["name"],
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                        },
                    ))
                    if verbose:
                        print(f"  OK: {model['name'][:30]:30s} | {domain:12s} | {len(result)} chars")
                elif verbose:
                    err = str(result)[:60] if isinstance(result, Exception) else "empty/short"
                    print(f"  FAIL: {model['name'][:30]:30s} | {domain:12s} | {err}")

            # Brief pause between prompt batches
            await asyncio.sleep(1)

    if verbose:
        print(f"\n[Training] {successful}/{total_calls} calls successful")
        print(f"[Training] {len(examples)} training examples generated")

    # Write SFT JSONL (ChatML format for HuggingFace TRL)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    sft_path = out / f"sft-traces-{timestamp}.jsonl"

    with open(sft_path, "w", encoding="utf-8") as f:
        for ex in examples:
            entry = {
                "messages": [
                    {"role": "system", "content": ex.metadata.get("system", "")},
                    {"role": "user", "content": ex.prompt},
                    {"role": "assistant", "content": ex.response},
                ],
                "domain": ex.domain,
                "model_id": ex.model_id,
                "provider": ex.provider,
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if verbose:
        print(f"[Training] SFT data saved: {sft_path}")
        print(f"[Training] File size: {sft_path.stat().st_size / 1024:.1f} KB")

    return sft_path


async def generate_dpo_data(
    sft_path: str | Path,
    output_dir: str | Path | None = None,
    verbose: bool = True,
) -> Path:
    """
    Generate DPO pairs from SFT data.

    Strategy: For each prompt, pick the longest+most detailed response
    as 'chosen' and the shortest as 'rejected'.
    """
    out = Path(output_dir or Path.home() / ".way2agi" / "training")

    # Load SFT examples grouped by prompt
    by_prompt: dict[str, list[dict]] = {}
    with open(sft_path, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            prompt = entry["messages"][1]["content"]
            by_prompt.setdefault(prompt, []).append(entry)

    dpo_pairs: list[dict] = []
    for prompt, entries in by_prompt.items():
        if len(entries) < 2:
            continue

        # Sort by response length (proxy for detail/quality)
        entries.sort(key=lambda e: len(e["messages"][2]["content"]), reverse=True)
        chosen = entries[0]
        rejected = entries[-1]

        # Only create pair if there's meaningful difference
        chosen_len = len(chosen["messages"][2]["content"])
        rejected_len = len(rejected["messages"][2]["content"])
        if chosen_len > rejected_len * 1.3:
            dpo_pairs.append({
                "prompt": prompt,
                "system": chosen["messages"][0]["content"],
                "chosen": chosen["messages"][2]["content"],
                "rejected": rejected["messages"][2]["content"],
                "chosen_model": chosen["model_id"],
                "rejected_model": rejected["model_id"],
                "domain": chosen["domain"],
            })

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dpo_path = out / f"dpo-pairs-{timestamp}.jsonl"

    with open(dpo_path, "w", encoding="utf-8") as f:
        for pair in dpo_pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    if verbose:
        print(f"[DPO] {len(dpo_pairs)} pairs created from {len(by_prompt)} unique prompts")
        print(f"[DPO] Saved: {dpo_path}")

    return dpo_path


# --- CLI ---

async def main() -> None:
    print("[Way2AGI Training Data Generator]")
    print("=" * 50)

    # Step 1: Generate SFT traces
    sft_path = await generate_sft_data(verbose=True)

    # Step 2: Generate DPO pairs from SFT data
    dpo_path = await generate_dpo_data(sft_path, verbose=True)

    print(f"\nDone! Files ready for HuggingFace training:")
    print(f"  SFT: {sft_path}")
    print(f"  DPO: {dpo_path}")
    print(f"\nNext steps:")
    print(f"  1. Upload to HuggingFace: huggingface-cli upload erik1988/way2agi-traces {sft_path}")
    print(f"  2. Train SFT: trl sft --model_name_or_path <base> --dataset_name erik1988/way2agi-traces")
    print(f"  3. Convert GGUF: python llama.cpp/convert.py <model> --outtype q4_K_M")
    print(f"  4. Deploy: ollama create way2agi -f Modelfile")


if __name__ == "__main__":
    asyncio.run(main())
