"""
Way2AGI Memory Server — FastAPI bridge between TS cognitive core and Python ML layer.

Exposes the 4-tier memory system backed by elias-memory:
- Episodic Buffer (working memory, in-memory with auto-eviction)
- Episodic Memory (events + outcomes, persisted via elias-memory)
- Semantic Memory (facts + concepts via elias-memory vector search)
- Procedural Memory (skill traces, persisted via elias-memory)

Plus: World Model queries, Knowledge Gap detection, Consolidation triggers.
"""

from __future__ import annotations

import os
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from elias_memory import Memory, MemoryRecord
from .logger import create_logger

log = create_logger("memory-server")

# --- Request/Response Models ---


class MemoryQueryReq(BaseModel):
    query: str
    top_k: int = 5
    memory_type: str = "semantic"  # semantic | episodic | procedural | buffer
    context: dict[str, Any] | None = None


class MemoryStoreReq(BaseModel):
    content: str
    memory_type: str = "episodic"
    metadata: dict[str, Any] | None = None
    importance: float = 0.5


class KnowledgeGap(BaseModel):
    topic: str
    coverage: float


class SkillRate(BaseModel):
    skill: str
    rate: float


class Pattern(BaseModel):
    pattern: str
    confidence: float


class ConsolidationResult(BaseModel):
    episodes_processed: int
    lessons_extracted: int
    memories_pruned: int


# --- Persistent store (elias-memory) + ephemeral buffer ---

DB_PATH = os.environ.get("MEMORY_DB_PATH", "data/way2agi_memory.db")
_memory: Memory | None = None
_buffer: deque[dict[str, Any]] = deque(maxlen=50)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize elias-memory backend."""
    global _memory
    print(f"[Memory] Starting Way2AGI Memory Server (db: {DB_PATH})")
    log.info("server starting", extra={"metadata": {"db_path": DB_PATH}})
    _memory = Memory(DB_PATH)
    log.info("memories loaded", extra={"metadata": {"count": len(_memory._records)}})
    print(f"[Memory] Loaded {len(_memory._records)} existing memories")
    yield
    if _memory:
        _memory.close()
    log.info("server shutdown")
    print("[Memory] Shutting down Memory Server")


app = FastAPI(
    title="Way2AGI Memory Server",
    version="0.2.0",
    lifespan=lifespan,
)


def _get_memory() -> Memory:
    assert _memory is not None, "Memory not initialized"
    return _memory


# --- Map Way2AGI 4-tier types to elias-memory 2 types (v1) ---
# episodic + buffer + procedural -> "episodic" in elias-memory
# semantic -> "semantic" in elias-memory
# The memory_type is preserved in metadata for filtering

def _to_elias_type(memory_type: str) -> str:
    return "semantic" if memory_type == "semantic" else "episodic"


@app.get("/health")
async def health():
    mem = _get_memory()
    type_counts: dict[str, int] = {}
    for rec in mem._records.values():
        mt = rec.metadata.get("way2agi_type", rec.type)
        type_counts[mt] = type_counts.get(mt, 0) + 1
    return {
        "status": "ok",
        "version": "0.2.0",
        "backend": "elias-memory v0.1.0",
        "total_memories": len(mem._records),
        "buffer_size": len(_buffer),
        "stores": type_counts,
    }


@app.post("/memory/store")
async def store_memory(req: MemoryStoreReq):
    """Store a new memory entry."""
    mem = _get_memory()

    # Buffer is ephemeral (in-memory only)
    if req.memory_type == "buffer":
        entry = {
            "content": req.content,
            "type": "buffer",
            "metadata": req.metadata or {},
            "importance": req.importance,
            "timestamp": datetime.now().isoformat(),
        }
        _buffer.append(entry)
        log.info("memory stored", extra={"metadata": {"memory_type": "buffer", "buffer_size": len(_buffer)}})
        return {"stored": True, "type": "buffer", "buffer_size": len(_buffer)}

    # All other types go to elias-memory
    metadata = req.metadata or {}
    metadata["way2agi_type"] = req.memory_type
    metadata["timestamp"] = datetime.now().isoformat()

    mid = mem.add(
        req.content,
        type=_to_elias_type(req.memory_type),
        importance=req.importance,
        metadata=metadata,
    )

    log.info("memory stored", extra={"metadata": {"memory_type": req.memory_type, "id": mid, "total": len(mem._records)}})
    return {"stored": True, "type": req.memory_type, "id": mid, "total": len(mem._records)}


@app.post("/memory/query")
async def query_memory(req: MemoryQueryReq) -> list[dict[str, Any]]:
    """Query memories using vector search via elias-memory."""
    mem = _get_memory()

    # Buffer queries are simple keyword search (ephemeral)
    if req.memory_type == "buffer":
        results = []
        query_lower = req.query.lower()
        for entry in reversed(_buffer):
            if query_lower in entry["content"].lower():
                results.append(entry)
                if len(results) >= req.top_k:
                    break
        return results

    # Vector search via elias-memory
    all_results = mem.recall(req.query, top_k=req.top_k * 3)

    # Filter by way2agi_type
    filtered = []
    for rec in all_results:
        way2agi_type = rec.metadata.get("way2agi_type", rec.type)
        if req.memory_type == "all" or way2agi_type == req.memory_type:
            filtered.append({
                "id": rec.id,
                "content": rec.content,
                "type": way2agi_type,
                "importance": rec.importance,
                "metadata": rec.metadata,
                "created_at": rec.created_at.isoformat(),
                "access_count": rec.access_count,
            })
            if len(filtered) >= req.top_k:
                break

    log.info("memory queried", extra={"metadata": {"memory_type": req.memory_type, "results": len(filtered)}})
    return filtered


@app.post("/memory/reinforce/{memory_id}")
async def reinforce_memory(memory_id: str):
    """Reinforce a memory (increases access count, delays decay)."""
    mem = _get_memory()
    mem.reinforce(memory_id)
    return {"reinforced": True, "id": memory_id}


@app.get("/memory/knowledge-gaps")
async def knowledge_gaps() -> list[KnowledgeGap]:
    """Detect topics with low coverage — feeds the Curiosity Drive."""
    mem = _get_memory()
    topics: dict[str, int] = {}
    for rec in mem._records.values():
        topic = rec.metadata.get("topic", "general")
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
    mem = _get_memory()
    skills: dict[str, dict[str, int]] = {}
    for rec in mem._records.values():
        if rec.metadata.get("way2agi_type") != "procedural":
            continue
        skill = rec.metadata.get("skill", "unknown")
        success = rec.metadata.get("success", False)
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
    # TODO: Implement pattern detection via temporal analysis
    return []


@app.post("/memory/consolidate")
async def consolidate() -> ConsolidationResult:
    """Nightly consolidation: episodes -> lessons -> semantic/procedural."""
    mem = _get_memory()

    # Find unconsolidated episodic memories
    episodes = [
        rec for rec in mem._records.values()
        if rec.metadata.get("way2agi_type") == "episodic"
        and not rec.metadata.get("consolidated")
    ]

    processed = 0
    lessons = 0

    for rec in episodes:
        rec.metadata["consolidated"] = True
        processed += 1
        # TODO: LLM extraction of lessons from episode

    # Run decay cycle
    mem.decay_cycle()

    # Count prunable memories (importance at floor)
    prunable = sum(1 for r in mem._records.values() if r.importance <= 0.02)

    log.info("consolidation complete", extra={"metadata": {
        "episodes_processed": processed,
        "lessons_extracted": lessons,
        "memories_pruned": prunable,
    }})
    return ConsolidationResult(
        episodes_processed=processed,
        lessons_extracted=lessons,
        memories_pruned=prunable,
    )


@app.post("/memory/export-sft")
async def export_sft(path: str = "data/sft_export.jsonl"):
    """Export all memories as SFT training data."""
    mem = _get_memory()
    mem.export_sft(path)
    return {"exported": len(mem._records), "path": path}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
