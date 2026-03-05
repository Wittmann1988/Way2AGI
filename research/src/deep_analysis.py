"""
Deep Analysis Pipeline — Multi-model research analysis with self-improvement.

This is the BRAIN of the research module. When a paper/repo scores high,
it doesn't just flag it — it:

1. Sends the paper to multiple LLM models for deep analysis
2. Generates concrete implementation plans
3. Creates self-improvement actions (code patches, new skills, config changes)
4. Documents everything in a structured progress log
5. Tracks improvements over time with metrics

Uses our Sidekick models via the orchestrator for multi-model consensus.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Any

import httpx

from .goals import GoalID, GOALS, AlignmentReport


# --- Types ---

@dataclass
class AnalysisResult:
    """Result from a single model's analysis."""
    model: str
    summary: str
    key_insights: list[str]
    applicable_to_way2agi: list[str]
    implementation_steps: list[str]
    estimated_impact: str  # "low" | "medium" | "high" | "critical"
    confidence: float  # 0.0-1.0


@dataclass
class ConsensusAnalysis:
    """Synthesized analysis from multiple models."""
    paper_title: str
    paper_url: str
    aligned_goal: GoalID | None
    individual_analyses: list[AnalysisResult]
    consensus_summary: str
    consensus_insights: list[str]
    implementation_plan: list[str]
    self_improvement_actions: list[SelfImprovementAction]
    overall_impact: str
    confidence: float


@dataclass
class SelfImprovementAction:
    """A concrete action to improve Way2AGI based on research."""
    id: str
    source_paper: str
    target_module: str  # e.g. "cognition/metacontroller.ts", "memory/server.py"
    action_type: str  # "code_change" | "new_feature" | "config_update" | "architecture_change"
    description: str
    priority: int  # 1-10
    estimated_effort: str  # "trivial" | "small" | "medium" | "large"
    aligned_goals: list[GoalID]
    status: str = "proposed"  # proposed | approved | in_progress | completed | rejected
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None
    result_summary: str | None = None


@dataclass
class ProgressEntry:
    """Single entry in the progress log."""
    date: str
    event_type: str  # "research_scan" | "deep_analysis" | "improvement_proposed" | "improvement_completed"
    description: str
    metrics: dict[str, Any]
    related_goals: list[str]
    source: str  # paper URL or repo URL


@dataclass
class ProgressReport:
    """Accumulated progress over time."""
    generated_at: str
    total_papers_scanned: int
    total_repos_scanned: int
    total_analyses_completed: int
    improvements_proposed: int
    improvements_completed: int
    improvements_rejected: int
    goal_progress: dict[str, GoalProgress]
    timeline: list[ProgressEntry]


@dataclass
class GoalProgress:
    """Progress tracking per goal."""
    goal_id: str
    goal_name: str
    papers_relevant: int
    repos_relevant: int
    improvements_proposed: int
    improvements_completed: int
    key_insights: list[str]
    impact_score: float  # 0.0-1.0, how much this goal has advanced


# --- LLM Interface ---

async def call_sidekick(
    prompt: str,
    model: str = "auto",
    system_context: str = "",
    sidekick_url: str = "http://localhost:18789",
) -> str:
    """Call our Sidekick models via the gateway or directly via MCP."""
    # In production, this calls the orchestrator's MoA or specific model
    # For now, format the request for external LLM calls
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(f"{sidekick_url}/api/complete", json={
                "model": model,
                "system": system_context,
                "prompt": prompt,
                "max_tokens": 2000,
            })
            if resp.status_code == 200:
                return resp.json().get("response", "")
        except Exception:
            pass

    # Fallback: return empty (will be handled gracefully)
    return ""


# --- Deep Analysis ---

async def analyze_paper_deeply(
    title: str,
    abstract: str,
    url: str,
    alignment: AlignmentReport,
    models: list[str] | None = None,
) -> ConsensusAnalysis:
    """
    Multi-model deep analysis of a research paper.

    Sends the paper to 3+ models with our goal context,
    then synthesizes a consensus with implementation plan.
    """
    target_models = models or ["step-flash", "kimi-k2", "qwen-coder"]

    # Build analysis prompt with our goals context
    goals_context = "\n".join(
        f"- {g.id.value}: {g.name} — {g.description}"
        for g in GOALS
    )

    analysis_prompt = f"""Analyze this research paper for Way2AGI (a cognitive AI agent pursuing AGI).

PAPER: {title}
URL: {url}
ABSTRACT: {abstract}

OUR GOALS:
{goals_context}

TOP ALIGNED GOAL: {alignment.top_goal.value if alignment.top_goal else 'None'} (score: {alignment.overall_score})

Analyze and respond in JSON format:
{{
  "summary": "2-3 sentence summary of the paper's contribution",
  "key_insights": ["insight1", "insight2", ...],
  "applicable_to_way2agi": ["how this applies to our specific modules"],
  "implementation_steps": ["step1", "step2", ...],
  "estimated_impact": "low|medium|high|critical",
  "confidence": 0.0-1.0
}}

Focus on CONCRETE, ACTIONABLE insights. Which of our modules can be improved? How exactly?"""

    system = (
        "You are a senior AI researcher analyzing papers for a cognitive AI agent project. "
        "Be specific about implementation. Reference concrete modules and code patterns. "
        "Respond ONLY with valid JSON."
    )

    # Run analyses in parallel across models
    tasks = [
        _analyze_with_model(model, system, analysis_prompt)
        for model in target_models
    ]
    individual_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out failures
    analyses: list[AnalysisResult] = []
    for i, result in enumerate(individual_results):
        if isinstance(result, AnalysisResult):
            analyses.append(result)
        elif isinstance(result, Exception):
            print(f"[DeepAnalysis] Model {target_models[i]} failed: {result}")

    # Generate consensus
    consensus = _build_consensus(title, url, alignment, analyses)

    # Generate self-improvement actions
    actions = _generate_self_improvement_actions(title, url, alignment, consensus)
    consensus.self_improvement_actions = actions

    return consensus


async def _analyze_with_model(
    model: str,
    system: str,
    prompt: str,
) -> AnalysisResult:
    """Run analysis with a single model."""
    response = await call_sidekick(prompt, model=model, system_context=system)

    if not response:
        return AnalysisResult(
            model=model,
            summary="Analysis unavailable (model did not respond)",
            key_insights=[],
            applicable_to_way2agi=[],
            implementation_steps=[],
            estimated_impact="low",
            confidence=0.0,
        )

    # Parse JSON response (with fallback)
    try:
        # Try to extract JSON from response
        json_match = _extract_json(response)
        data = json.loads(json_match) if json_match else {}
    except json.JSONDecodeError:
        data = {}

    return AnalysisResult(
        model=model,
        summary=data.get("summary", response[:200]),
        key_insights=data.get("key_insights", []),
        applicable_to_way2agi=data.get("applicable_to_way2agi", []),
        implementation_steps=data.get("implementation_steps", []),
        estimated_impact=data.get("estimated_impact", "medium"),
        confidence=float(data.get("confidence", 0.5)),
    )


def _extract_json(text: str) -> str | None:
    """Extract JSON from text that may contain markdown or extra content."""
    import re
    # Try markdown codeblock first
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    # Try raw JSON
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return None


def _build_consensus(
    title: str,
    url: str,
    alignment: AlignmentReport,
    analyses: list[AnalysisResult],
) -> ConsensusAnalysis:
    """Build consensus from multiple model analyses."""
    if not analyses:
        return ConsensusAnalysis(
            paper_title=title,
            paper_url=url,
            aligned_goal=alignment.top_goal,
            individual_analyses=[],
            consensus_summary="No analyses available",
            consensus_insights=[],
            implementation_plan=[],
            self_improvement_actions=[],
            overall_impact="low",
            confidence=0.0,
        )

    # Merge insights (deduplicate similar ones)
    all_insights = []
    for a in analyses:
        all_insights.extend(a.key_insights)
    unique_insights = list(dict.fromkeys(all_insights))[:10]

    # Merge implementation steps
    all_steps = []
    for a in analyses:
        all_steps.extend(a.implementation_steps)
    unique_steps = list(dict.fromkeys(all_steps))[:10]

    # Merge applicable items
    all_applicable = []
    for a in analyses:
        all_applicable.extend(a.applicable_to_way2agi)
    unique_applicable = list(dict.fromkeys(all_applicable))[:10]

    # Consensus impact = most common impact
    impacts = [a.estimated_impact for a in analyses if a.estimated_impact]
    impact_counts: dict[str, int] = {}
    for imp in impacts:
        impact_counts[imp] = impact_counts.get(imp, 0) + 1
    overall_impact = max(impact_counts, key=impact_counts.get) if impact_counts else "medium"

    # Average confidence
    confidences = [a.confidence for a in analyses if a.confidence > 0]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

    # Best summary (from highest confidence model)
    best = max(analyses, key=lambda a: a.confidence)

    return ConsensusAnalysis(
        paper_title=title,
        paper_url=url,
        aligned_goal=alignment.top_goal,
        individual_analyses=analyses,
        consensus_summary=best.summary,
        consensus_insights=unique_insights,
        implementation_plan=unique_steps,
        self_improvement_actions=[],  # filled later
        overall_impact=overall_impact,
        confidence=round(avg_confidence, 2),
    )


def _generate_self_improvement_actions(
    title: str,
    url: str,
    alignment: AlignmentReport,
    consensus: ConsensusAnalysis,
) -> list[SelfImprovementAction]:
    """Generate concrete self-improvement actions from consensus analysis."""
    actions: list[SelfImprovementAction] = []
    goal = alignment.top_goal
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Map goals to target modules
    goal_to_modules: dict[GoalID, list[str]] = {
        GoalID.G1_AUTONOMOUS_AGENCY: ["cognition/src/initiative.ts", "cognition/src/drives/registry.ts"],
        GoalID.G2_SELF_IMPROVEMENT: ["cognition/src/reflection.ts", "cognition/src/metacontroller.ts"],
        GoalID.G3_MEMORY_KNOWLEDGE: ["memory/src/server.py", "cognition/src/workspace.ts"],
        GoalID.G4_MODEL_ORCHESTRATION: ["orchestrator/src/composer.py", "orchestrator/src/registry.py"],
        GoalID.G5_RESEARCH_INTEGRATION: ["research/src/arxiv_crawler.py", "research/src/deep_analysis.py"],
        GoalID.G6_CONSCIOUSNESS: ["cognition/src/workspace.ts", "cognition/src/monologue.ts"],
    }

    target_modules = goal_to_modules.get(goal, ["cognition/src/workspace.ts"]) if goal else []

    for i, step in enumerate(consensus.implementation_plan[:5]):
        module = target_modules[i % len(target_modules)] if target_modules else "docs/"
        actions.append(SelfImprovementAction(
            id=f"sia-{timestamp}-{i}",
            source_paper=url,
            target_module=module,
            action_type="code_change" if "implement" in step.lower() else "new_feature",
            description=step,
            priority=min(10, 5 + (2 if consensus.overall_impact == "critical" else
                                  1 if consensus.overall_impact == "high" else 0)),
            estimated_effort="medium",
            aligned_goals=[goal] if goal else [],
        ))

    return actions


# --- Progress Tracking ---

class ProgressTracker:
    """Tracks and documents all research progress over time."""

    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".way2agi" / "research"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.data_dir / "progress.json"
        self.actions_file = self.data_dir / "improvement_actions.json"
        self.log_file = self.data_dir / "progress_log.jsonl"
        self._load()

    def _load(self) -> None:
        self.actions: list[dict] = []
        if self.actions_file.exists():
            self.actions = json.loads(self.actions_file.read_text())

        self.progress_data: dict = {
            "total_papers_scanned": 0,
            "total_repos_scanned": 0,
            "total_analyses": 0,
            "goal_progress": {},
        }
        if self.progress_file.exists():
            self.progress_data = json.loads(self.progress_file.read_text())

    def _save(self) -> None:
        self.actions_file.write_text(json.dumps(self.actions, indent=2, ensure_ascii=False))
        self.progress_file.write_text(json.dumps(self.progress_data, indent=2, ensure_ascii=False))

    def log_event(self, entry: ProgressEntry) -> None:
        """Append an event to the progress log."""
        with open(self.log_file, "a") as f:
            f.write(json.dumps({
                "date": entry.date,
                "type": entry.event_type,
                "description": entry.description,
                "metrics": entry.metrics,
                "goals": entry.related_goals,
                "source": entry.source,
            }) + "\n")

    def record_scan(self, scan_type: str, total: int, relevant: int) -> None:
        """Record a research scan (arXiv or GitHub)."""
        key = "total_papers_scanned" if scan_type == "arxiv" else "total_repos_scanned"
        self.progress_data[key] = self.progress_data.get(key, 0) + total

        self.log_event(ProgressEntry(
            date=datetime.now().isoformat(),
            event_type="research_scan",
            description=f"{scan_type} scan: {total} total, {relevant} relevant",
            metrics={"total": total, "relevant": relevant, "type": scan_type},
            related_goals=[],
            source=scan_type,
        ))
        self._save()

    def record_analysis(self, consensus: ConsensusAnalysis) -> None:
        """Record a completed deep analysis."""
        self.progress_data["total_analyses"] = self.progress_data.get("total_analyses", 0) + 1

        # Update goal progress
        if consensus.aligned_goal:
            gid = consensus.aligned_goal.value
            gp = self.progress_data.setdefault("goal_progress", {}).setdefault(gid, {
                "papers_analyzed": 0,
                "improvements_proposed": 0,
                "improvements_completed": 0,
                "key_insights": [],
                "impact_score": 0.0,
            })
            gp["papers_analyzed"] = gp.get("papers_analyzed", 0) + 1
            gp["key_insights"] = (gp.get("key_insights", []) + consensus.consensus_insights[:3])[-20:]

        self.log_event(ProgressEntry(
            date=datetime.now().isoformat(),
            event_type="deep_analysis",
            description=f"Analyzed: {consensus.paper_title[:60]}",
            metrics={
                "models_used": len(consensus.individual_analyses),
                "insights": len(consensus.consensus_insights),
                "actions": len(consensus.self_improvement_actions),
                "impact": consensus.overall_impact,
                "confidence": consensus.confidence,
            },
            related_goals=[consensus.aligned_goal.value] if consensus.aligned_goal else [],
            source=consensus.paper_url,
        ))
        self._save()

    def propose_improvement(self, action: SelfImprovementAction) -> None:
        """Record a proposed self-improvement action."""
        self.actions.append({
            "id": action.id,
            "source": action.source_paper,
            "module": action.target_module,
            "type": action.action_type,
            "description": action.description,
            "priority": action.priority,
            "effort": action.estimated_effort,
            "goals": [g.value for g in action.aligned_goals],
            "status": "proposed",
            "proposed_at": action.created_at,
            "completed_at": None,
            "result": None,
        })

        gid = action.aligned_goals[0].value if action.aligned_goals else None
        if gid:
            gp = self.progress_data.setdefault("goal_progress", {}).setdefault(gid, {})
            gp["improvements_proposed"] = gp.get("improvements_proposed", 0) + 1

        self.log_event(ProgressEntry(
            date=datetime.now().isoformat(),
            event_type="improvement_proposed",
            description=f"[{action.target_module}] {action.description[:60]}",
            metrics={"priority": action.priority, "effort": action.estimated_effort},
            related_goals=[g.value for g in action.aligned_goals],
            source=action.source_paper,
        ))
        self._save()

    def complete_improvement(self, action_id: str, result_summary: str) -> None:
        """Mark an improvement action as completed."""
        for action in self.actions:
            if action["id"] == action_id:
                action["status"] = "completed"
                action["completed_at"] = datetime.now().isoformat()
                action["result"] = result_summary

                gid = action["goals"][0] if action["goals"] else None
                if gid:
                    gp = self.progress_data.get("goal_progress", {}).get(gid, {})
                    gp["improvements_completed"] = gp.get("improvements_completed", 0) + 1
                    # Increase impact score
                    gp["impact_score"] = min(1.0, gp.get("impact_score", 0) + 0.1)

                self.log_event(ProgressEntry(
                    date=datetime.now().isoformat(),
                    event_type="improvement_completed",
                    description=f"COMPLETED: {action['description'][:60]}",
                    metrics={"result": result_summary[:100]},
                    related_goals=action["goals"],
                    source=action["source"],
                ))
                break
        self._save()

    def get_pending_actions(self, min_priority: int = 5) -> list[dict]:
        """Get proposed actions sorted by priority."""
        return sorted(
            [a for a in self.actions if a["status"] == "proposed" and a["priority"] >= min_priority],
            key=lambda a: a["priority"],
            reverse=True,
        )

    def generate_progress_report(self) -> str:
        """Generate a human-readable progress report (Markdown)."""
        lines = [
            f"# Way2AGI Research Progress Report",
            f"**Generated:** {datetime.now().isoformat()}",
            "",
            "## Overview",
            f"- Papers scanned: **{self.progress_data.get('total_papers_scanned', 0)}**",
            f"- Repos scanned: **{self.progress_data.get('total_repos_scanned', 0)}**",
            f"- Deep analyses: **{self.progress_data.get('total_analyses', 0)}**",
            f"- Improvements proposed: **{sum(1 for a in self.actions if a['status'] == 'proposed')}**",
            f"- Improvements completed: **{sum(1 for a in self.actions if a['status'] == 'completed')}**",
            "",
            "## Goal Progress",
        ]

        goal_names = {g.id.value: g.name for g in GOALS}
        for gid, gp in self.progress_data.get("goal_progress", {}).items():
            name = goal_names.get(gid, gid)
            impact = gp.get("impact_score", 0)
            bar_len = int(impact * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)

            lines.append(f"\n### {gid}: {name}")
            lines.append(f"Impact: [{bar}] {impact:.0%}")
            lines.append(f"- Papers analyzed: {gp.get('papers_analyzed', 0)}")
            lines.append(f"- Improvements proposed: {gp.get('improvements_proposed', 0)}")
            lines.append(f"- Improvements completed: {gp.get('improvements_completed', 0)}")
            if gp.get("key_insights"):
                lines.append("- Key insights:")
                for insight in gp["key_insights"][-5:]:
                    lines.append(f"  - {insight[:80]}")

        # Pending actions
        pending = self.get_pending_actions(min_priority=1)
        if pending:
            lines.append("\n## Pending Improvements (by priority)")
            for a in pending[:15]:
                status_icon = "🔴" if a["priority"] >= 8 else "🟡" if a["priority"] >= 5 else "🟢"
                lines.append(
                    f"- {status_icon} **P{a['priority']}** [{a['module']}] {a['description'][:60]}"
                )
                lines.append(f"  Source: {a['source']}")

        # Recent completions
        completed = [a for a in self.actions if a["status"] == "completed"]
        if completed:
            lines.append("\n## Recent Completions")
            for a in completed[-10:]:
                lines.append(f"- [{a['module']}] {a['description'][:60]}")
                if a.get("result"):
                    lines.append(f"  Result: {a['result'][:80]}")

        return "\n".join(lines)

    def save_progress_report_md(self) -> Path:
        """Save progress report as Markdown file."""
        report = self.generate_progress_report()
        filepath = self.data_dir / "PROGRESS.md"
        filepath.write_text(report)
        return filepath
