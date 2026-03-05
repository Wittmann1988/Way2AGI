"""Tests for Way2AGI Memory Server endpoints."""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

from memory.src.server import (
    app,
    episodic_buffer,
    episodic_store,
    semantic_store,
    procedural_store,
)


@pytest.fixture(autouse=True)
def _clear_stores():
    """Reset all in-memory stores before each test."""
    episodic_buffer.clear()
    episodic_store.clear()
    semantic_store.clear()
    procedural_store.clear()
    yield
    episodic_buffer.clear()
    episodic_store.clear()
    semantic_store.clear()
    procedural_store.clear()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# --- /health ---


@pytest.mark.anyio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "stores" in data
    for key in ("episodic_buffer", "episodic", "semantic", "procedural"):
        assert data["stores"][key] == 0


@pytest.mark.anyio
async def test_health_reflects_store_counts(client):
    await client.post("/memory/store", json={"content": "a", "memory_type": "semantic"})
    await client.post("/memory/store", json={"content": "b", "memory_type": "episodic"})
    resp = await client.get("/health")
    data = resp.json()
    assert data["stores"]["semantic"] == 1
    assert data["stores"]["episodic"] == 1


# --- /memory/store ---


@pytest.mark.anyio
async def test_store_episodic(client):
    resp = await client.post("/memory/store", json={
        "content": "test event",
        "memory_type": "episodic",
        "importance": 0.8,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["stored"] is True
    assert body["type"] == "episodic"
    assert len(episodic_store) == 1
    assert episodic_store[0]["content"] == "test event"
    assert episodic_store[0]["importance"] == 0.8


@pytest.mark.anyio
async def test_store_semantic(client):
    resp = await client.post("/memory/store", json={
        "content": "Python is a language",
        "memory_type": "semantic",
        "metadata": {"topic": "programming"},
    })
    assert resp.status_code == 200
    assert len(semantic_store) == 1
    assert semantic_store[0]["metadata"]["topic"] == "programming"


@pytest.mark.anyio
async def test_store_procedural(client):
    resp = await client.post("/memory/store", json={
        "content": "git commit workflow",
        "memory_type": "procedural",
        "metadata": {"skill": "git", "success": True},
    })
    assert resp.status_code == 200
    assert len(procedural_store) == 1


@pytest.mark.anyio
async def test_store_buffer(client):
    resp = await client.post("/memory/store", json={
        "content": "working memory item",
        "memory_type": "buffer",
    })
    assert resp.status_code == 200
    assert len(episodic_buffer) == 1


# --- /memory/query ---


@pytest.mark.anyio
async def test_query_roundtrip_semantic(client):
    """Store + Query roundtrip: stored content is retrievable."""
    await client.post("/memory/store", json={
        "content": "FastAPI is a modern web framework",
        "memory_type": "semantic",
    })
    await client.post("/memory/store", json={
        "content": "Django is also a web framework",
        "memory_type": "semantic",
    })
    resp = await client.post("/memory/query", json={
        "query": "FastAPI",
        "memory_type": "semantic",
        "top_k": 5,
    })
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert "FastAPI" in results[0]["content"]


@pytest.mark.anyio
async def test_query_respects_top_k(client):
    for i in range(10):
        await client.post("/memory/store", json={
            "content": f"test entry {i}",
            "memory_type": "episodic",
        })
    resp = await client.post("/memory/query", json={
        "query": "test entry",
        "memory_type": "episodic",
        "top_k": 3,
    })
    results = resp.json()
    assert len(results) == 3


@pytest.mark.anyio
async def test_query_returns_most_recent_first(client):
    """Reversed iteration means newest entries come first."""
    await client.post("/memory/store", json={"content": "alpha event", "memory_type": "episodic"})
    await client.post("/memory/store", json={"content": "beta event", "memory_type": "episodic"})
    resp = await client.post("/memory/query", json={
        "query": "event",
        "memory_type": "episodic",
        "top_k": 2,
    })
    results = resp.json()
    assert results[0]["content"] == "beta event"
    assert results[1]["content"] == "alpha event"


@pytest.mark.anyio
async def test_query_no_results(client):
    resp = await client.post("/memory/query", json={
        "query": "nonexistent",
        "memory_type": "semantic",
    })
    assert resp.json() == []


@pytest.mark.anyio
async def test_query_buffer(client):
    await client.post("/memory/store", json={"content": "buffer item", "memory_type": "buffer"})
    resp = await client.post("/memory/query", json={
        "query": "buffer",
        "memory_type": "buffer",
    })
    assert len(resp.json()) == 1


# --- /memory/knowledge-gaps ---


@pytest.mark.anyio
async def test_knowledge_gaps_empty(client):
    """Empty semantic store returns default gap."""
    resp = await client.get("/memory/knowledge-gaps")
    assert resp.status_code == 200
    gaps = resp.json()
    assert len(gaps) == 1
    assert gaps[0]["topic"] == "self-improvement"
    assert gaps[0]["coverage"] == pytest.approx(0.1)


@pytest.mark.anyio
async def test_knowledge_gaps_with_topics(client):
    for _ in range(3):
        await client.post("/memory/store", json={
            "content": "python info",
            "memory_type": "semantic",
            "metadata": {"topic": "python"},
        })
    await client.post("/memory/store", json={
        "content": "rust info",
        "memory_type": "semantic",
        "metadata": {"topic": "rust"},
    })
    resp = await client.get("/memory/knowledge-gaps")
    gaps = resp.json()
    topics = {g["topic"]: g["coverage"] for g in gaps}
    assert "rust" in topics
    assert "python" in topics
    # rust has 1 entry, python has 3 (max), so rust coverage < python coverage
    assert topics["rust"] < topics["python"]
    assert topics["python"] == pytest.approx(1.0)


# --- /memory/skill-rates ---


@pytest.mark.anyio
async def test_skill_rates_empty(client):
    resp = await client.get("/memory/skill-rates")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_skill_rates_calculates_correctly(client):
    for success in [True, True, False]:
        await client.post("/memory/store", json={
            "content": "coding attempt",
            "memory_type": "procedural",
            "metadata": {"skill": "python", "success": success},
        })
    resp = await client.get("/memory/skill-rates")
    rates = resp.json()
    assert len(rates) == 1
    assert rates[0]["skill"] == "python"
    assert rates[0]["rate"] == pytest.approx(2.0 / 3.0)


@pytest.mark.anyio
async def test_skill_rates_multiple_skills(client):
    await client.post("/memory/store", json={
        "content": "git task",
        "memory_type": "procedural",
        "metadata": {"skill": "git", "success": True},
    })
    await client.post("/memory/store", json={
        "content": "docker task",
        "memory_type": "procedural",
        "metadata": {"skill": "docker", "success": False},
    })
    resp = await client.get("/memory/skill-rates")
    rates = {r["skill"]: r["rate"] for r in resp.json()}
    assert rates["git"] == pytest.approx(1.0)
    assert rates["docker"] == pytest.approx(0.0)


# --- /memory/consolidate ---


@pytest.mark.anyio
async def test_consolidate_empty(client):
    resp = await client.post("/memory/consolidate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["episodes_processed"] == 0
    assert data["lessons_extracted"] == 0
    assert data["memories_pruned"] == 0


@pytest.mark.anyio
async def test_consolidate_marks_episodes(client):
    for i in range(3):
        await client.post("/memory/store", json={
            "content": f"episode {i}",
            "memory_type": "episodic",
        })
    resp = await client.post("/memory/consolidate")
    data = resp.json()
    assert data["episodes_processed"] == 3
    # All episodes should now be marked as consolidated
    assert all(e.get("consolidated") for e in episodic_store)
    # Running again should process 0
    resp2 = await client.post("/memory/consolidate")
    assert resp2.json()["episodes_processed"] == 0


# --- Buffer auto-eviction ---


@pytest.mark.anyio
async def test_buffer_auto_eviction(client):
    """Buffer should auto-evict oldest entries when exceeding 50."""
    for i in range(55):
        await client.post("/memory/store", json={
            "content": f"buffer entry {i}",
            "memory_type": "buffer",
        })
    assert len(episodic_buffer) == 50
    # The oldest 5 entries (0-4) should have been evicted
    assert "buffer entry 5" in episodic_buffer[0]["content"]
    assert "buffer entry 54" in episodic_buffer[-1]["content"]
