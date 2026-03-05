"""
Goal Alignment Scorer — Evaluates how well something serves our AGI goals.

Used by:
- arXiv crawler to score papers
- Initiative Engine to prioritize tasks
- Reflection Engine to evaluate strategies
- Any component that needs "is this useful for AGI?" scoring
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GoalID(str, Enum):
    G1_AUTONOMOUS_AGENCY = "G1"
    G2_SELF_IMPROVEMENT = "G2"
    G3_MEMORY_KNOWLEDGE = "G3"
    G4_MODEL_ORCHESTRATION = "G4"
    G5_RESEARCH_INTEGRATION = "G5"
    G6_CONSCIOUSNESS = "G6"


@dataclass
class Goal:
    id: GoalID
    name: str
    description: str
    keywords: list[str]  # For keyword-based alignment scoring


# Our 6 core goals with associated keywords for matching
GOALS: list[Goal] = [
    Goal(
        id=GoalID.G1_AUTONOMOUS_AGENCY,
        name="Autonomous Agency",
        description="The agent acts on its own ideas, not just responds to prompts.",
        keywords=[
            "autonomous agent", "agency", "intrinsic motivation", "goal generation",
            "self-directed", "proactive", "initiative", "planning", "decision making",
            "goal-oriented", "agentic", "tool use", "action selection", "exploration",
            "curiosity-driven", "reward shaping", "self-play", "open-ended learning",
        ],
    ),
    Goal(
        id=GoalID.G2_SELF_IMPROVEMENT,
        name="Self-Improvement",
        description="Every interaction makes the agent better. Every failure is a lesson.",
        keywords=[
            "self-improvement", "self-refine", "self-evolving", "metacognition",
            "reflection", "learning from mistakes", "continual learning",
            "lifelong learning", "self-correction", "self-training", "bootstrapping",
            "recursive self-improvement", "auto-curriculum", "self-play",
            "self-supervised", "self-instruct", "skill acquisition",
        ],
    ),
    Goal(
        id=GoalID.G3_MEMORY_KNOWLEDGE,
        name="Memory & Knowledge",
        description="Never forget. Build a coherent world model.",
        keywords=[
            "memory", "long-term memory", "episodic memory", "semantic memory",
            "procedural memory", "knowledge graph", "retrieval augmented",
            "vector database", "embedding", "memory consolidation", "forgetting",
            "world model", "knowledge representation", "memory architecture",
            "context window", "memory-augmented", "persistent memory",
        ],
    ),
    Goal(
        id=GoalID.G4_MODEL_ORCHESTRATION,
        name="Multi-Model Orchestration",
        description="Use the right model for the right task. Compose, don't choose.",
        keywords=[
            "mixture of agents", "model composition", "model selection",
            "multi-agent", "ensemble", "routing", "orchestration", "cascade",
            "model merging", "speculative decoding", "distillation",
            "mixture of experts", "collaborative agents", "agent communication",
            "multi-model", "model collaboration", "tool orchestration",
        ],
    ),
    Goal(
        id=GoalID.G5_RESEARCH_INTEGRATION,
        name="Cutting-Edge Research",
        description="Every day, scan the frontier. Every week, integrate a new concept.",
        keywords=[
            "survey", "benchmark", "state-of-the-art", "novel architecture",
            "breakthrough", "frontier", "scaling", "emergent", "capability",
            "evaluation", "leaderboard", "foundation model", "paradigm",
        ],
    ),
    Goal(
        id=GoalID.G6_CONSCIOUSNESS,
        name="Consciousness Research",
        description="Explore the boundary between simulation and understanding.",
        keywords=[
            "consciousness", "awareness", "global workspace", "attention",
            "theory of mind", "phenomenal", "qualia", "sentience",
            "self-awareness", "inner experience", "subjective", "metacognitive",
            "cognitive architecture", "binding problem", "integrated information",
            "higher-order thought", "access consciousness", "stream of consciousness",
        ],
    ),
]


@dataclass
class AlignmentScore:
    goal_id: GoalID
    goal_name: str
    score: float  # 0.0 - 1.0
    matched_keywords: list[str]
    reasoning: str


@dataclass
class AlignmentReport:
    item_title: str
    item_description: str
    overall_score: float  # 0.0 - 1.0 (max of all goals)
    goal_scores: list[AlignmentScore]
    is_relevant: bool  # overall_score >= threshold
    top_goal: GoalID | None
    recommendation: str  # "ignore" | "monitor" | "study" | "implement"


def score_alignment(
    title: str,
    abstract: str,
    threshold: float = 0.3,
) -> AlignmentReport:
    """
    Score how well a paper/concept aligns with our AGI goals.

    Uses keyword matching + heuristic weighting.
    For production, this should be augmented with LLM-based scoring.
    """
    text = f"{title} {abstract}".lower()
    goal_scores: list[AlignmentScore] = []

    for goal in GOALS:
        matched = [kw for kw in goal.keywords if kw.lower() in text]
        # Score based on keyword density + title bonus
        title_matches = [kw for kw in goal.keywords if kw.lower() in title.lower()]

        raw_score = len(matched) / max(len(goal.keywords), 1)
        title_bonus = len(title_matches) * 0.15  # Title matches worth more
        score = min(1.0, raw_score + title_bonus)

        reasoning = (
            f"Matched {len(matched)}/{len(goal.keywords)} keywords"
            + (f" ({len(title_matches)} in title)" if title_matches else "")
        )

        goal_scores.append(AlignmentScore(
            goal_id=goal.id,
            goal_name=goal.name,
            score=round(score, 3),
            matched_keywords=matched,
            reasoning=reasoning,
        ))

    # Sort by score descending
    goal_scores.sort(key=lambda s: s.score, reverse=True)
    overall = goal_scores[0].score if goal_scores else 0.0
    top_goal = goal_scores[0].goal_id if goal_scores and goal_scores[0].score > 0 else None

    # Recommendation based on score
    if overall >= 0.6:
        recommendation = "implement"
    elif overall >= 0.4:
        recommendation = "study"
    elif overall >= threshold:
        recommendation = "monitor"
    else:
        recommendation = "ignore"

    return AlignmentReport(
        item_title=title,
        item_description=abstract[:200],
        overall_score=round(overall, 3),
        goal_scores=goal_scores,
        is_relevant=overall >= threshold,
        top_goal=top_goal,
        recommendation=recommendation,
    )
