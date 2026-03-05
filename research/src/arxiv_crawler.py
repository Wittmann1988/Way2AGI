"""
arXiv Daily Crawler — Fetches latest AI research papers and scores them.

Monitors:
- cs.AI  (Artificial Intelligence)
- cs.LG  (Machine Learning)
- cs.CL  (Computation and Language / NLP)
- cs.MA  (Multi-Agent Systems)

Scores each paper against our 6 AGI goals and generates
implementation concepts for high-scoring papers.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Any

import httpx

from .goals import score_alignment, AlignmentReport, GoalID


# arXiv API endpoint (Atom feed)
ARXIV_API = "http://export.arxiv.org/api/query"

# Categories to monitor
CATEGORIES = [
    "cs.AI",   # Artificial Intelligence
    "cs.LG",   # Machine Learning
    "cs.CL",   # Computation and Language
    "cs.MA",   # Multi-Agent Systems
]

MAX_RESULTS_PER_CATEGORY = 50


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published: str
    url: str
    pdf_url: str


@dataclass
class ScoredPaper:
    paper: ArxivPaper
    alignment: AlignmentReport
    concepts: list[str] = field(default_factory=list)


@dataclass
class DailyReport:
    date: str
    total_papers: int
    relevant_papers: int
    implement_papers: int
    study_papers: int
    monitor_papers: int
    papers: list[ScoredPaper]


async def fetch_papers(
    category: str,
    max_results: int = MAX_RESULTS_PER_CATEGORY,
) -> list[ArxivPaper]:
    """Fetch recent papers from arXiv API for a given category."""
    params = {
        "search_query": f"cat:{category}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(max_results),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(ARXIV_API, params=params)
        resp.raise_for_status()

    return _parse_atom_feed(resp.text)


def _parse_atom_feed(xml_text: str) -> list[ArxivPaper]:
    """Parse arXiv Atom XML feed into ArxivPaper objects."""
    papers = []

    # Simple XML parsing without lxml dependency
    entries = re.findall(r"<entry>(.*?)</entry>", xml_text, re.DOTALL)

    for entry in entries:
        arxiv_id = _extract_tag(entry, "id").split("/abs/")[-1]
        title = _extract_tag(entry, "title").strip().replace("\n", " ")
        abstract = _extract_tag(entry, "summary").strip().replace("\n", " ")
        published = _extract_tag(entry, "published")

        # Authors
        authors = re.findall(r"<name>(.*?)</name>", entry)

        # Categories
        categories = re.findall(r'<category[^>]*term="([^"]*)"', entry)

        # URLs
        url = f"https://arxiv.org/abs/{arxiv_id}"
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

        papers.append(ArxivPaper(
            arxiv_id=arxiv_id,
            title=title,
            authors=authors[:5],  # Limit to first 5 authors
            abstract=abstract[:1000],  # Limit abstract length
            categories=categories,
            published=published,
            url=url,
            pdf_url=pdf_url,
        ))

    return papers


def _extract_tag(text: str, tag: str) -> str:
    """Extract content from an XML tag."""
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1) if match else ""


async def crawl_and_score(
    categories: list[str] | None = None,
    threshold: float = 0.3,
) -> DailyReport:
    """
    Main entry point: crawl arXiv, score all papers, generate report.
    """
    cats = categories or CATEGORIES
    all_papers: list[ArxivPaper] = []
    seen_ids: set[str] = set()

    # Fetch from all categories (with dedup)
    for cat in cats:
        papers = await fetch_papers(cat)
        for p in papers:
            if p.arxiv_id not in seen_ids:
                seen_ids.add(p.arxiv_id)
                all_papers.append(p)

    # Score each paper against our goals
    scored: list[ScoredPaper] = []
    for paper in all_papers:
        alignment = score_alignment(paper.title, paper.abstract, threshold)
        sp = ScoredPaper(paper=paper, alignment=alignment)

        # Generate implementation concepts for high-scoring papers
        if alignment.recommendation in ("implement", "study"):
            sp.concepts = _generate_concepts(paper, alignment)

        scored.append(sp)

    # Sort by relevance score
    scored.sort(key=lambda s: s.alignment.overall_score, reverse=True)

    # Build report
    relevant = [s for s in scored if s.alignment.is_relevant]
    return DailyReport(
        date=date.today().isoformat(),
        total_papers=len(scored),
        relevant_papers=len(relevant),
        implement_papers=sum(1 for s in scored if s.alignment.recommendation == "implement"),
        study_papers=sum(1 for s in scored if s.alignment.recommendation == "study"),
        monitor_papers=sum(1 for s in scored if s.alignment.recommendation == "monitor"),
        papers=scored,
    )


def _generate_concepts(paper: ArxivPaper, alignment: AlignmentReport) -> list[str]:
    """
    Generate implementation concept suggestions based on paper content.

    This is the keyword-based version. For production, augment with
    LLM-based concept generation (send paper abstract to Claude/GPT
    with our goal context and ask for implementation ideas).
    """
    concepts = []
    top = alignment.top_goal

    if top == GoalID.G1_AUTONOMOUS_AGENCY:
        concepts.append(
            f"Integrate '{paper.title}' concepts into InitiativeEngine — "
            f"may improve autonomous goal generation"
        )
        if "planning" in paper.abstract.lower():
            concepts.append("Evaluate paper's planning approach for GoalManager improvements")

    elif top == GoalID.G2_SELF_IMPROVEMENT:
        concepts.append(
            f"Apply '{paper.title}' to ReflectionEngine — "
            f"may improve Layer 2/3 self-modification quality"
        )
        if "self-refine" in paper.abstract.lower() or "iterative" in paper.abstract.lower():
            concepts.append("Test iterative refinement loop from this paper in our metacognitive cycle")

    elif top == GoalID.G3_MEMORY_KNOWLEDGE:
        concepts.append(
            f"Evaluate '{paper.title}' for memory/ module — "
            f"may improve retrieval or consolidation"
        )
        if "consolidation" in paper.abstract.lower():
            concepts.append("Compare paper's consolidation strategy with our nightly consolidation")

    elif top == GoalID.G4_MODEL_ORCHESTRATION:
        concepts.append(
            f"Test '{paper.title}' approach in orchestrator/composer.py — "
            f"may improve multi-model composition"
        )
        if "mixture" in paper.abstract.lower():
            concepts.append("Benchmark paper's MoA variant against our current MoA implementation")

    elif top == GoalID.G5_RESEARCH_INTEGRATION:
        concepts.append(f"Add '{paper.title}' to research tracking — survey/benchmark paper")

    elif top == GoalID.G6_CONSCIOUSNESS:
        concepts.append(
            f"Study '{paper.title}' for consciousness module — "
            f"may inform Global Workspace or Theory of Mind implementation"
        )
        if "global workspace" in paper.abstract.lower():
            concepts.append("Compare paper's GWT implementation with our workspace.ts")

    return concepts


def save_report(report: DailyReport, output_dir: str | Path) -> Path:
    """Save daily report as JSON."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    filepath = out / f"arxiv-{report.date}.json"

    # Convert to serializable dict
    data = {
        "date": report.date,
        "total_papers": report.total_papers,
        "relevant_papers": report.relevant_papers,
        "implement_papers": report.implement_papers,
        "study_papers": report.study_papers,
        "monitor_papers": report.monitor_papers,
        "papers": [
            {
                "arxiv_id": sp.paper.arxiv_id,
                "title": sp.paper.title,
                "authors": sp.paper.authors,
                "url": sp.paper.url,
                "categories": sp.paper.categories,
                "overall_score": sp.alignment.overall_score,
                "top_goal": sp.alignment.top_goal.value if sp.alignment.top_goal else None,
                "recommendation": sp.alignment.recommendation,
                "concepts": sp.concepts,
                "goal_scores": [
                    {
                        "goal": gs.goal_id.value,
                        "name": gs.goal_name,
                        "score": gs.score,
                        "matched_keywords": gs.matched_keywords,
                    }
                    for gs in sp.alignment.goal_scores
                    if gs.score > 0
                ],
            }
            for sp in report.papers
            if sp.alignment.is_relevant
        ],
    }

    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return filepath


def print_report(report: DailyReport, top_n: int = 15) -> None:
    """Print a human-readable summary of the daily report."""
    print(f"\n{'=' * 60}")
    print(f"  Way2AGI Research Report — {report.date}")
    print(f"{'=' * 60}")
    print(f"  Total papers scanned:  {report.total_papers}")
    print(f"  Relevant to our goals: {report.relevant_papers}")
    print(f"  IMPLEMENT:             {report.implement_papers}")
    print(f"  STUDY:                 {report.study_papers}")
    print(f"  MONITOR:               {report.monitor_papers}")
    print(f"{'=' * 60}\n")

    relevant = [s for s in report.papers if s.alignment.is_relevant][:top_n]

    for i, sp in enumerate(relevant, 1):
        rec = sp.alignment.recommendation.upper()
        goal = sp.alignment.top_goal.value if sp.alignment.top_goal else "?"
        score = sp.alignment.overall_score

        print(f"  [{rec:9s}] ({goal}, {score:.2f}) {sp.paper.title[:70]}")
        print(f"             {sp.paper.url}")
        for concept in sp.concepts[:2]:
            print(f"             -> {concept[:80]}")
        print()


# CLI entry point
async def main() -> None:
    """Run the daily crawl from command line."""
    import sys
    from pathlib import Path

    print("[Way2AGI Research] Starting daily arXiv crawl...")
    report = await crawl_and_score()
    print_report(report)

    # Save report
    home = Path.home()
    report_path = save_report(report, home / ".way2agi" / "research")
    print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
