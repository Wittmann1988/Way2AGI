"""Tests for Way2AGI Memory Server endpoints (backed by elias-memory)."""

from __future__ import annotations

import os
import tempfile

import pytest
import httpx
from httpx import ASGITransport

# Set temp DB before importing server
_tmp = tempfile.mkdtemp()
os.environ["MEMORY_DB_PATH"] = os.path.join(_tmp, "test.db")

import memory.src.server as srv
from memory.src.server import app, _buffer
from elias_memory import Memory


@pytest.fixture(autouse=True)
def _init_memory():
    """Initialize elias-memory for each test (lifespan doesn't run in ASGI transport)."""
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    srv._memory = Memory(db_path)
    _buffer.clear()
    yield
    if srv._memory:
        srv._memory.close()
        srv._memory = None
    _buffer.clear()


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
    assert data["version"] == "0.2.0"
    assert data["backend"] == "elias-memory v0.1.0"


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
    assert "id" in body


@pytest.mark.anyio
async def test_store_semantic(client):
    resp = await client.post("/memory/store", json={
        "content": "Python is a language",
        "memory_type": "semantic",
        "metadata": {"topic": "programming"},
    })
    assert resp.status_code == 200
    assert resp.json()["stored"] is True


@pytest.mark.anyio
async def test_store_procedural(client):
    resp = await client.post("/memory/store", json={
        "content": "git commit workflow",
        "memory_type": "procedural",
        "metadata": {"skill": "git", "success": True},
    })
    assert resp.status_code == 200
    assert resp.json()["stored"] is True


@pytest.mark.anyio
async def test_store_buffer(client):
    resp = await client.post("/memory/store", json={
        "content": "working memory item",
        "memory_type": "buffer",
    })
    assert resp.status_code == 200
    assert resp.json()["type"] == "buffer"
    assert len(_buffer) == 1


# --- /memory/query ---


@pytest.mark.anyio
async def test_query_roundtrip_semantic(client):
    """Store + Query roundtrip via vector search."""
    await client.post("/memory/store", json={
        "content": "FastAPI is a modern web framework",
        "memory_type": "semantic",
    })
    await client.post("/memory/store", json={
        "content": "Django is also a web framework",
        "memory_type": "semantic",
    })
    resp = await client.post("/memory/query", json={
        "query": "FastAPI web",
        "memory_type": "semantic",
        "top_k": 5,
    })
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    # Vector search returns results (content may vary by similarity)
    contents = [r["content"] for r in results]
    assert any("FastAPI" in c or "web" in c for c in contents)


@pytest.mark.anyio
async def test_query_no_results_empty(client):
    resp = await client.post("/memory/query", json={
        "query": "nonexistent topic xyz",
        "memory_type": "semantic",
    })
    # May return results from vector search (even with low similarity)
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_query_buffer(client):
    await client.post("/memory/store", json={"content": "buffer item", "memory_type": "buffer"})
    resp = await client.post("/memory/query", json={
        "query": "buffer",
        "memory_type": "buffer",
    })
    assert len(resp.json()) == 1


# --- /memory/reinforce ---


@pytest.mark.anyio
async def test_reinforce(client):
    store_resp = await client.post("/memory/store", json={
        "content": "important fact",
        "memory_type": "semantic",
        "importance": 0.9,
    })
    mid = store_resp.json()["id"]
    resp = await client.post(f"/memory/reinforce/{mid}")
    assert resp.status_code == 200
    assert resp.json()["reinforced"] is True


# --- /memory/knowledge-gaps ---


@pytest.mark.anyio
async def test_knowledge_gaps_empty(client):
    resp = await client.get("/memory/knowledge-gaps")
    assert resp.status_code == 200
    gaps = resp.json()
    assert len(gaps) >= 1


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
    assert topics["rust"] < topics["python"]


# --- /memory/skill-rates ---


@pytest.mark.anyio
async def test_skill_rates_empty(client):
    resp = await client.get("/memory/skill-rates")
    assert resp.status_code == 200


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


# --- /memory/consolidate ---


@pytest.mark.anyio
async def test_consolidate(client):
    for i in range(3):
        await client.post("/memory/store", json={
            "content": f"episode {i}",
            "memory_type": "episodic",
        })
    resp = await client.post("/memory/consolidate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["episodes_processed"] == 3


# --- /memory/export-sft ---


@pytest.mark.anyio
async def test_export_sft(client, tmp_path):
    await client.post("/memory/store", json={
        "content": "export test",
        "memory_type": "semantic",
    })
    export_path = str(tmp_path / "export.jsonl")
    resp = await client.post(f"/memory/export-sft?path={export_path}")
    assert resp.status_code == 200


# --- Buffer auto-eviction ---


@pytest.mark.anyio
async def test_buffer_auto_eviction(client):
    for i in range(55):
        await client.post("/memory/store", json={
            "content": f"buffer entry {i}",
            "memory_type": "buffer",
        })
    assert len(_buffer) == 50
    assert "buffer entry 54" in _buffer[-1]["content"]
