"""Tests for the Goal Alignment Scorer."""

import pytest
from research.src.goals import score_alignment, GoalID, GOALS


class TestGoalAlignment:
    def test_highly_relevant_paper_scores_high(self):
        report = score_alignment(
            "Self-Improving Autonomous Agents with Intrinsic Motivation",
            "We present a novel framework for autonomous agent self-improvement "
            "through intrinsic motivation and curiosity-driven exploration. "
            "The agent generates its own goals and learns from mistakes.",
        )
        assert report.overall_score >= 0.4
        assert report.is_relevant
        assert report.recommendation in ("study", "implement")

    def test_irrelevant_paper_scores_low(self):
        report = score_alignment(
            "Optimal Pricing Strategies for Cloud Computing",
            "We study dynamic pricing models for cloud computing resources "
            "using game theory and auction mechanisms.",
        )
        assert report.overall_score < 0.3
        assert not report.is_relevant
        assert report.recommendation == "ignore"

    def test_memory_paper_aligns_with_g3(self):
        report = score_alignment(
            "Long-Term Memory Consolidation in Neural Networks",
            "We propose a novel memory consolidation mechanism inspired by "
            "episodic memory and semantic memory systems in the brain. "
            "Our approach uses vector database retrieval augmented generation.",
        )
        assert report.top_goal == GoalID.G3_MEMORY_KNOWLEDGE
        assert report.is_relevant

    def test_consciousness_paper_aligns_with_g6(self):
        report = score_alignment(
            "Global Workspace Theory for AI Consciousness",
            "We implement a global workspace architecture with attention "
            "spotlight and theory of mind capabilities for self-awareness.",
        )
        assert report.top_goal == GoalID.G6_CONSCIOUSNESS
        assert report.overall_score >= 0.3

    def test_moa_paper_aligns_with_g4(self):
        report = score_alignment(
            "Mixture of Agents for Multi-Model Orchestration",
            "We present a mixture of agents approach where multiple models "
            "collaborate through ensemble routing and model composition.",
        )
        assert report.top_goal == GoalID.G4_MODEL_ORCHESTRATION

    def test_all_goals_have_keywords(self):
        for goal in GOALS:
            assert len(goal.keywords) >= 10, f"{goal.id} has too few keywords"

    def test_recommendation_levels(self):
        # High score -> implement
        high = score_alignment(
            "Autonomous Agent Self-Improvement via Metacognition and Intrinsic Motivation",
            "autonomous agent self-improvement metacognition intrinsic motivation "
            "curiosity-driven goal generation self-directed planning exploration "
            "self-refine self-evolving continual learning bootstrapping "
            "recursive self-improvement skill acquisition reflection",
        )
        assert high.recommendation == "implement"

    def test_custom_threshold(self):
        report = score_alignment(
            "Some AI Paper",
            "A paper about machine learning models.",
            threshold=0.01,
        )
        # With very low threshold, even vague matches may be relevant
        assert isinstance(report.is_relevant, bool)

    def test_empty_input(self):
        report = score_alignment("", "")
        assert report.overall_score == 0.0
        assert report.recommendation == "ignore"
