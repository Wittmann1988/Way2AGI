"""Tests for RLHF-light feedback collection."""
import os
import tempfile
import pytest
from cli.feedback import FeedbackStore


def test_store_positive_feedback():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        store = FeedbackStore(f.name)
        store.record("Was ist Python?", "Python ist eine Programmiersprache.", rating=1)
        entries = store.load_all()
        assert len(entries) == 1
        assert entries[0]["rating"] == 1
        assert entries[0]["user"] == "Was ist Python?"
    os.unlink(f.name)


def test_store_negative_feedback():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        store = FeedbackStore(f.name)
        store.record("Frage", "Schlechte Antwort", rating=-1)
        entries = store.load_all()
        assert len(entries) == 1
        assert entries[0]["rating"] == -1
    os.unlink(f.name)


def test_export_dpo_pairs():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        store = FeedbackStore(f.name)
        store.record("Was ist KI?", "KI ist Kuenstliche Intelligenz.", rating=1)
        store.record("Was ist KI?", "Keine Ahnung.", rating=-1)
        pairs = store.export_dpo_pairs()
        assert len(pairs) == 1
        assert pairs[0]["chosen"] == "KI ist Kuenstliche Intelligenz."
        assert pairs[0]["rejected"] == "Keine Ahnung."
    os.unlink(f.name)


def test_stats():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        store = FeedbackStore(f.name)
        store.record("A", "B", 1)
        store.record("C", "D", -1)
        store.record("E", "F", 1)
        stats = store.stats()
        assert stats["total"] == 3
        assert stats["positive"] == 2
        assert stats["negative"] == 1
    os.unlink(f.name)
