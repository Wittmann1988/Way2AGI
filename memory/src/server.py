"""
Way2AGI Memory Server — FastAPI bridge between TS cognitive core and Python ML layer.

Exposes the 4-tier memory system:
- Episodic Buffer (working memory)
- Episodic Memory (events + outcomes)
- Semantic Memory (facts + concepts via elias-memory)
- Procedural Memory (skill traces)

Plus: World Model queries, Knowledge Gap detection, Consolidation triggers.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

# --- Request/Response Models ---


class MemoryQuery(BaseModel):
    query: str
    top_k: int = 5
    memory_type: str = "semantic"  # semantic | episodic | procedural
    context: dict[str, Any] | None = None


class MemoryStore(BaseModel):
    content: str
    memory_type: str = "episodic"
    metadata: dict[str, Any] | None = None
    importance: float = 0.5


class KnowledgeGap(BaseModel):
    topic: str
    coverage: float  # 0.0 = no knowledge, 1.0 = full coverage


class SkillRate(BaseModel):
    skill: str
    rate: float  # success rate 0.0-1.0


class Pattern(BaseModel):
    pattern: str
    confidence: float


class ConsolidationResult(BaseModel):
    episodes_processed: int
    lessons_extracted: int
    memories_pruned: int


# --- In-memory stores (will be backed by elias-memory + sqlite-vec) ---

episodic_buffer: list[dict[str, Any]] = []
episodic_store: list[dict[str, Any]] = []
semantic_store: list[dict[str, Any]] = []
procedural_store: list[dict[str, Any]] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load elias-memory, initialize stores."""
    print("[Memory] Starting Way2AGI Memory Server")
    # TODO: Initialize elias-memory connection
    # TODO: Load sqlite-vec index
    yield
    print("[Memory] Shutting down Memory Server")


app = FastAPI(
    title="Way2AGI Memory Server",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "stores": {
            "episodic_buffer": len(episodic_buffer),
            "episodic": len(episodic_store),
            "semantic": len(semantic_store),
            "procedural": len(procedural_store),
        },
    }


@app.post("/memory/store")
async def store_memory(req: MemoryStore):
    """Store a new memory entry."""
    entry = {
        "content": req.content,
        "type": req.memory_type,
        "metadata": req.metadata or {},
        "importance": req.importance,
        "timestamp": datetime.now().isoformat(),
    }

    match req.memory_type:
        case "episodic":
            episodic_store.append(entry)
        case "semantic":
            semantic_store.append(entry)
        case "procedural":
            procedural_store.append(entry)
        case "buffer":
            episodic_buffer.append(entry)
            # Buffer auto-evicts after 50 entries
            if len(episodic_buffer) > 50:
                episodic_buffer.pop(0)

    return {"stored": True, "type": req.memory_type, "total": len(episodic_store)}


@app.post("/memory/query")
async def query_memory(req: MemoryQuery) -> list[dict[str, Any]]:
    """Query memories by type. TODO: vector search via elias-memory."""
    store = {
        "episodic": episodic_store,
        "semantic": semantic_store,
        "procedural": procedural_store,
        "buffer": episodic_buffer,
    }.get(req.memory_type, semantic_store)

    # Simple keyword matching for now — will be replaced by elias-memory vector search
    results = []
    query_lower = req.query.lower()
    for entry in reversed(store):
        if query_lower in entry["content"].lower():
            results.append(entry)
            if len(results) >= req.top_k:
                break

    return results


@app.get("/memory/knowledge-gaps")
async def knowledge_gaps() -> list[KnowledgeGap]:
    """Detect topics with low coverage — feeds the Curiosity Drive."""
    # TODO: Implement actual gap detection via embedding clustering
    # For now, return placeholder gaps based on store analysis
    topics = {}
    for entry in semantic_store:
        meta = entry.get("metadata", {})
        topic = meta.get("topic", "general")
        topics[topic] = topics.get(topic, 0) + 1

    if not topics:
        return [KnowledgeGap(topic="self-improvement", coverage=0.1)]

    max_count = max(topics.values())
    return [
        KnowledgeGap(topic=t, coverage=min(1.0, c / max_count))
        for t, c in sorted(topics.items(), key=lambda x: x[1])
    ]


@app.get("/memory/skill-rates")
async def skill_rates() -> list[SkillRate]:
    """Get skill success rates — feeds the Competence Drive."""
    skills: dict[str, dict[str, int]] = {}
    for entry in procedural_store:
        meta = entry.get("metadata", {})
        skill = meta.get("skill", "unknown")
        success = meta.get("success", False)
        if skill not in skills:
            skills[skill] = {"total": 0, "success": 0}
        skills[skill]["total"] += 1
        if success:
            skills[skill]["success"] += 1

    return [
        SkillRate(skill=s, rate=d["success"] / d["total"] if d["total"] > 0 else 0.0)
        for s, d in skills.items()
    ]


@app.get("/memory/patterns")
async def recent_patterns() -> list[Pattern]:
    """Detect interaction patterns — feeds the Social Drive."""
    # TODO: Implement actual pattern detection
    # This will use temporal analysis of episodic memories
    return []


@app.post("/memory/consolidate")
async def consolidate() -> ConsolidationResult:
    """Nightly consolidation: episodes -> lessons -> semantic/procedural."""
    # TODO: Implement actual consolidation via LLM
    # The agent re-experiences past episodes, extracts generalized lessons
    episodes_to_process = [e for e in episodic_store if not e.get("consolidated")]
    processed = 0
    lessons = 0

    for ep in episodes_to_process:
        ep["consolidated"] = True
        processed += 1
        # TODO: LLM extraction of lessons from episode

    return ConsolidationResult(
        episodes_processed=processed,
        lessons_extracted=lessons,
        memories_pruned=0,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
