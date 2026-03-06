"""
GitHub Repository Scanner — Finds cutting-edge AI repos every 3 days.

Searches GitHub for trending AI/AGI repositories, evaluates them
against our 6 goals (G1-G6), and generates integration concepts.

Scans:
- Trending repos in AI/ML/agents topics
- New repos with high growth (stars/forks ratio)
- Repos tagged with our goal-relevant keywords
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any

import httpx

from .goals import score_alignment, AlignmentReport, GoalID, GOALS

# Import resilience patterns from orchestrator package
import sys as _sys
_monorepo_root = str(Path(__file__).resolve().parents[2])
if _monorepo_root not in _sys.path:
    _sys.path.insert(0, _monorepo_root)
from orchestrator.src.resilience import RateLimiter, retry_with_backoff

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# Rate limiters: GitHub allows 10 search requests/min unauthenticated, 30 authenticated.
# We use conservative limits below the actual caps.
_github_rate_limiter_unauth = RateLimiter("github-unauth", max_calls=30, period=60.0)
_github_rate_limiter_auth = RateLimiter("github-auth", max_calls=60, period=60.0)

# Search queries aligned with our goals
SEARCH_QUERIES = [
    # G1: Autonomous Agency
    "autonomous agent framework language:Python stars:>50 pushed:>{since}",
    "agentic AI goal-driven language:TypeScript stars:>20 pushed:>{since}",
    # G2: Self-Improvement
    "self-improving AI metacognition stars:>10 pushed:>{since}",
    "self-refine LLM agent stars:>30 pushed:>{since}",
    # G3: Memory & Knowledge
    "long-term memory AI agent stars:>20 pushed:>{since}",
    "memory-augmented LLM vector stars:>50 pushed:>{since}",
    # G4: Model Orchestration
    "mixture of agents LLM stars:>30 pushed:>{since}",
    "multi-model orchestration stars:>20 pushed:>{since}",
    # G5: Research
    "cognitive architecture AI stars:>50 pushed:>{since}",
    # G6: Consciousness
    "AI consciousness global workspace stars:>5 pushed:>{since}",
    "theory of mind LLM stars:>10 pushed:>{since}",
    # General AGI
    "AGI framework open-source stars:>100 pushed:>{since}",
    "personal AI assistant self-hosted stars:>200 pushed:>{since}",
]


@dataclass
class GitHubRepo:
    full_name: str
    description: str
    url: str
    stars: int
    forks: int
    language: str | None
    topics: list[str]
    created_at: str
    pushed_at: str
    open_issues: int


@dataclass
class ScoredRepo:
    repo: GitHubRepo
    alignment: AlignmentReport
    integration_concepts: list[str] = field(default_factory=list)
    improvement_ideas: list[str] = field(default_factory=list)


@dataclass
class GithubScanReport:
    date: str
    total_repos: int
    relevant_repos: int
    implement_repos: int
    repos: list[ScoredRepo]


@retry_with_backoff(
    max_retries=3,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=(
        httpx.HTTPStatusError,
        httpx.ConnectError,
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
        TimeoutError,
        ConnectionError,
    ),
)
async def search_github(
    query: str,
    token: str | None = None,
    max_results: int = 30,
) -> list[GitHubRepo]:
    """Search GitHub API for repositories matching query."""
    # Acquire rate-limit token before calling
    limiter = _github_rate_limiter_auth if token else _github_rate_limiter_unauth
    await limiter.acquire()

    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": str(min(max_results, 100)),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{GITHUB_API}/search/repositories", params=params, headers=headers)
        if resp.status_code == 403:
            # Rate limited by GitHub — log and return empty
            logger.warning("GitHub API rate limit hit (403) for query: %s", query[:60])
            return []
        resp.raise_for_status()
        data = resp.json()

    repos = []
    for item in data.get("items", []):
        repos.append(GitHubRepo(
            full_name=item["full_name"],
            description=item.get("description") or "",
            url=item["html_url"],
            stars=item["stargazers_count"],
            forks=item["forks_count"],
            language=item.get("language"),
            topics=item.get("topics", []),
            created_at=item["created_at"],
            pushed_at=item["pushed_at"],
            open_issues=item["open_issues_count"],
        ))

    return repos


def _generate_integration_concepts(repo: GitHubRepo, alignment: AlignmentReport) -> list[str]:
    """Generate specific integration/improvement ideas for a repo."""
    concepts = []
    top = alignment.top_goal
    name = repo.full_name.split("/")[-1]

    if top == GoalID.G1_AUTONOMOUS_AGENCY:
        concepts.append(
            f"Analyse {name}'s agent architecture — compare with our InitiativeEngine + DriveSystem"
        )
        concepts.append(
            f"Extract goal generation patterns from {name} — may improve our GoalManager"
        )

    elif top == GoalID.G2_SELF_IMPROVEMENT:
        concepts.append(
            f"Study {name}'s self-improvement loop — compare with our 3-Layer Metacognition"
        )
        concepts.append(
            f"Check if {name} has novel reflection strategies for our ReflectionEngine"
        )

    elif top == GoalID.G3_MEMORY_KNOWLEDGE:
        concepts.append(
            f"Evaluate {name}'s memory architecture — compare with our 4-Tier system"
        )
        concepts.append(
            f"Check {name} for novel retrieval/consolidation methods for elias-memory"
        )

    elif top == GoalID.G4_MODEL_ORCHESTRATION:
        concepts.append(
            f"Benchmark {name}'s model routing against our Capability Registry + MoA Composer"
        )
        concepts.append(
            f"Extract model selection heuristics from {name} for our CostOptimizer"
        )

    elif top == GoalID.G6_CONSCIOUSNESS:
        concepts.append(
            f"Study {name}'s consciousness/attention implementation — compare with our GlobalWorkspace"
        )

    # General improvement ideas
    if repo.stars > 1000:
        concepts.append(f"HIGH PRIORITY: {name} has {repo.stars} stars — likely production-quality patterns")

    if repo.language and repo.language.lower() in ("typescript", "python"):
        concepts.append(f"Same language ({repo.language}) — direct code adaptation possible")

    return concepts


def _generate_improvement_ideas(repo: GitHubRepo, alignment: AlignmentReport) -> list[str]:
    """Generate ideas for how WE can improve on what the repo does."""
    ideas = []
    name = repo.full_name.split("/")[-1]

    ideas.append(
        f"Identify what {name} does well that we lack — gap analysis"
    )
    ideas.append(
        f"Identify what {name} does poorly that we can do better — "
        f"our 3-layer metacognition and drive system are unique advantages"
    )

    return ideas


async def scan_and_score(
    token: str | None = None,
    days_lookback: int = 3,
    threshold: float = 0.25,
) -> GithubScanReport:
    """
    Main entry point: scan GitHub, score repos, generate integration concepts.
    """
    since = (date.today() - timedelta(days=days_lookback)).isoformat()
    all_repos: list[GitHubRepo] = []
    seen: set[str] = set()

    # Run all searches
    for query_template in SEARCH_QUERIES:
        query = query_template.replace("{since}", since)
        try:
            repos = await search_github(query, token=token, max_results=20)
            for r in repos:
                if r.full_name not in seen:
                    seen.add(r.full_name)
                    all_repos.append(r)
        except Exception as e:
            print(f"[GitHub Scanner] Query failed: {e}")
            continue

        # Rate limit protection: brief pause between queries
        await asyncio.sleep(2)

    # Score each repo
    scored: list[ScoredRepo] = []
    for repo in all_repos:
        # Combine description + topics for scoring
        text = f"{repo.description} {' '.join(repo.topics)}"
        alignment = score_alignment(repo.full_name, text, threshold)

        sr = ScoredRepo(repo=repo, alignment=alignment)

        if alignment.recommendation in ("implement", "study"):
            sr.integration_concepts = _generate_integration_concepts(repo, alignment)
            sr.improvement_ideas = _generate_improvement_ideas(repo, alignment)

        scored.append(sr)

    # Sort by relevance
    scored.sort(key=lambda s: s.alignment.overall_score, reverse=True)

    relevant = [s for s in scored if s.alignment.is_relevant]
    return GithubScanReport(
        date=date.today().isoformat(),
        total_repos=len(scored),
        relevant_repos=len(relevant),
        implement_repos=sum(1 for s in scored if s.alignment.recommendation == "implement"),
        repos=scored,
    )


def save_github_report(report: GithubScanReport, output_dir: str | Path) -> Path:
    """Save GitHub scan report as JSON."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    filepath = out / f"github-{report.date}.json"
    data = {
        "date": report.date,
        "total_repos": report.total_repos,
        "relevant_repos": report.relevant_repos,
        "implement_repos": report.implement_repos,
        "repos": [
            {
                "full_name": sr.repo.full_name,
                "description": sr.repo.description,
                "url": sr.repo.url,
                "stars": sr.repo.stars,
                "language": sr.repo.language,
                "topics": sr.repo.topics,
                "overall_score": sr.alignment.overall_score,
                "top_goal": sr.alignment.top_goal.value if sr.alignment.top_goal else None,
                "recommendation": sr.alignment.recommendation,
                "integration_concepts": sr.integration_concepts,
                "improvement_ideas": sr.improvement_ideas,
            }
            for sr in report.repos
            if sr.alignment.is_relevant
        ],
    }

    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return filepath


def print_github_report(report: GithubScanReport, top_n: int = 15) -> None:
    """Print human-readable GitHub scan summary."""
    print(f"\n{'=' * 60}")
    print(f"  Way2AGI GitHub Scanner — {report.date}")
    print(f"{'=' * 60}")
    print(f"  Total repos found:     {report.total_repos}")
    print(f"  Relevant to our goals: {report.relevant_repos}")
    print(f"  IMPLEMENT candidates:  {report.implement_repos}")
    print(f"{'=' * 60}\n")

    relevant = [s for s in report.repos if s.alignment.is_relevant][:top_n]

    for sr in relevant:
        rec = sr.alignment.recommendation.upper()
        goal = sr.alignment.top_goal.value if sr.alignment.top_goal else "?"
        score = sr.alignment.overall_score
        stars = sr.repo.stars

        print(f"  [{rec:9s}] ({goal}, {score:.2f}) {sr.repo.full_name} ({stars} stars)")
        print(f"             {sr.repo.url}")
        print(f"             {sr.repo.description[:80]}")
        for concept in sr.integration_concepts[:2]:
            print(f"             -> {concept[:80]}")
        print()


# CLI entry point
async def main() -> None:
    import os

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    print("[Way2AGI] Starting GitHub repository scan...")

    report = await scan_and_score(token=token)
    print_github_report(report)

    report_path = save_github_report(report, Path.home() / ".way2agi" / "research")
    print(f"Report saved: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
