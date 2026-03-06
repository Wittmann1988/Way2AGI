"""RLHF-light — Thumbs up/down feedback store for future DPO training."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any


class FeedbackStore:
    """JSONL-based feedback store for RLHF-light."""

    def __init__(self, path: str | None = None):
        if path is None:
            data_dir = os.path.join(os.path.expanduser("~"), ".way2agi")
            os.makedirs(data_dir, exist_ok=True)
            path = os.path.join(data_dir, "feedback.jsonl")
        self.path = path

    def record(
        self,
        user_msg: str,
        assistant_msg: str,
        rating: int,
        model: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "user": user_msg,
            "assistant": assistant_msg,
            "rating": rating,
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load_all(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        entries = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def stats(self) -> dict[str, int]:
        entries = self.load_all()
        positive = sum(1 for e in entries if e.get("rating", 0) > 0)
        negative = sum(1 for e in entries if e.get("rating", 0) < 0)
        return {"total": len(entries), "positive": positive, "negative": negative}

    def export_dpo_pairs(self) -> list[dict[str, str]]:
        entries = self.load_all()
        by_prompt: dict[str, dict[str, list[str]]] = {}
        for e in entries:
            prompt = e["user"]
            if prompt not in by_prompt:
                by_prompt[prompt] = {"positive": [], "negative": []}
            if e["rating"] > 0:
                by_prompt[prompt]["positive"].append(e["assistant"])
            elif e["rating"] < 0:
                by_prompt[prompt]["negative"].append(e["assistant"])
        pairs = []
        for prompt, responses in by_prompt.items():
            for chosen in responses["positive"]:
                for rejected in responses["negative"]:
                    pairs.append({"prompt": prompt, "chosen": chosen, "rejected": rejected})
        return pairs
