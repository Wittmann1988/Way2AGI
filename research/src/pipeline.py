"""
Full Research Pipeline — Combines all research components.

Daily (arXiv):
1. Crawl latest papers
2. Score against our 6 goals (G1-G6)
3. Deep analysis of high-scoring papers (multi-model)
4. Generate self-improvement actions
5. Document progress

Every 3 days (GitHub):
6. Scan trending repos
7. Score against goals
8. Generate integration concepts
9. Document progress

Continuous:
10. Track all progress in PROGRESS.md
11. Feed improvements back to Initiative Engine
"""

from __future__ import annotations

import asyncio
from datetime import datetime, date
from pathlib import Path

from .arxiv_crawler import crawl_and_score, save_report, print_report, ScoredPaper
from .github_scanner import scan_and_score as github_scan, save_github_report, print_github_report
from .deep_analysis import (
    analyze_paper_deeply,
    ConsensusAnalysis,
    ProgressTracker,
    ProgressEntry,
)
from .goals import AlignmentReport
from .logger import create_logger

log = create_logger("pipeline")


async def run_full_pipeline(
    output_dir: str | Path | None = None,
    notify_url: str | None = None,
    github_token: str | None = None,
    deep_analysis_models: list[str] | None = None,
    verbose: bool = True,
) -> dict:
    """
    Execute the full research pipeline.

    Returns a summary with all findings and actions.
    """
    out = Path(output_dir) if output_dir else Path.home() / ".way2agi" / "research"
    tracker = ProgressTracker(out)

    log.info("pipeline started", extra={"metadata": {"output_dir": str(out)}})

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"  Way2AGI Full Research Pipeline")
        print(f"  {datetime.now().isoformat()}")
        print(f"{'=' * 60}\n")

    results: dict = {
        "date": date.today().isoformat(),
        "arxiv": None,
        "github": None,
        "deep_analyses": [],
        "improvements_proposed": 0,
        "progress_report": None,
    }

    # === PHASE 1: arXiv Crawl ===
    log.info("phase started", extra={"metadata": {"phase": "1/5", "name": "arxiv_crawl"}})
    if verbose:
        print("[Phase 1/5] arXiv crawl...")

    arxiv_report = await crawl_and_score(threshold=0.25)
    save_report(arxiv_report, out)
    tracker.record_scan("arxiv", arxiv_report.total_papers, arxiv_report.relevant_papers)

    if verbose:
        print_report(arxiv_report, top_n=5)

    results["arxiv"] = {
        "total": arxiv_report.total_papers,
        "relevant": arxiv_report.relevant_papers,
        "implement": arxiv_report.implement_papers,
        "study": arxiv_report.study_papers,
    }
    log.info("arxiv crawl complete", extra={"metadata": {
        "total": arxiv_report.total_papers,
        "relevant": arxiv_report.relevant_papers,
    }})

    # === PHASE 2: GitHub Scan (every 3 days) ===
    day_of_year = date.today().timetuple().tm_yday
    if day_of_year % 3 == 0:
        if verbose:
            print("\n[Phase 2/5] GitHub scan (every 3 days)...")

        github_report = await github_scan(token=github_token, threshold=0.25)
        save_github_report(github_report, out)
        tracker.record_scan("github", github_report.total_repos, github_report.relevant_repos)

        if verbose:
            print_github_report(github_report, top_n=5)

        results["github"] = {
            "total": github_report.total_repos,
            "relevant": github_report.relevant_repos,
            "implement": github_report.implement_repos,
        }
    else:
        if verbose:
            print(f"\n[Phase 2/5] GitHub scan skipped (runs every 3 days, next: day {day_of_year + (3 - day_of_year % 3)})")

    # === PHASE 3: Deep Analysis of top papers ===
    log.info("phase started", extra={"metadata": {"phase": "3/5", "name": "deep_analysis"}})
    if verbose:
        print("\n[Phase 3/5] Deep analysis of top papers...")

    # Get papers worth deep analysis (implement + study)
    top_papers = [
        sp for sp in arxiv_report.papers
        if sp.alignment.recommendation in ("implement", "study")
    ][:5]  # Max 5 deep analyses per run

    # Cache consensus results for reuse in Phase 4
    consensus_cache: list[ConsensusAnalysis] = []

    for sp in top_papers:
        if verbose:
            print(f"  Analyzing: {sp.paper.title[:60]}...")

        try:
            consensus = await analyze_paper_deeply(
                title=sp.paper.title,
                abstract=sp.paper.abstract,
                url=sp.paper.url,
                alignment=sp.alignment,
                models=deep_analysis_models,
            )

            tracker.record_analysis(consensus)
            consensus_cache.append(consensus)

            results["deep_analyses"].append({
                "title": sp.paper.title[:80],
                "url": sp.paper.url,
                "impact": consensus.overall_impact,
                "confidence": consensus.confidence,
                "insights": len(consensus.consensus_insights),
                "actions": len(consensus.self_improvement_actions),
            })

            if verbose:
                print(f"    Impact: {consensus.overall_impact} | "
                      f"Confidence: {consensus.confidence:.0%} | "
                      f"Insights: {len(consensus.consensus_insights)} | "
                      f"Actions: {len(consensus.self_improvement_actions)}")

        except Exception as e:
            log.error("deep analysis failed", extra={"metadata": {"paper": sp.paper.title[:80], "error": str(e)}})
            if verbose:
                print(f"    Analysis failed: {e}")

    # === PHASE 4: Register self-improvement actions ===
    if verbose:
        print("\n[Phase 4/5] Registering self-improvement actions...")

    total_actions = 0
    for consensus in consensus_cache:
        for action in consensus.self_improvement_actions:
            tracker.propose_improvement(action)
            total_actions += 1

    results["improvements_proposed"] = total_actions
    log.info("improvements registered", extra={"metadata": {"total_actions": total_actions}})

    if verbose:
        print(f"  {total_actions} improvement actions proposed")

    # === PHASE 5: Generate progress report ===
    if verbose:
        print("\n[Phase 5/5] Generating progress report...")

    report_path = tracker.save_progress_report_md()
    results["progress_report"] = str(report_path)

    if verbose:
        print(f"  Progress report: {report_path}")
        print(f"\n  Pending improvements (high priority):")
        for action in tracker.get_pending_actions(min_priority=6)[:5]:
            print(f"    P{action['priority']} [{action['module']}] {action['description'][:60]}")

    # === Notify ===
    if notify_url:
        await _send_pipeline_notification(notify_url, results, tracker)

    log.info("pipeline complete", extra={"metadata": {
        "papers": results["arxiv"]["total"] if results["arxiv"] else 0,
        "deep_analyses": len(results["deep_analyses"]),
        "improvements": results["improvements_proposed"],
    }})

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"  Pipeline complete!")
        print(f"  Papers: {results['arxiv']['total'] if results['arxiv'] else 0}")
        print(f"  Deep analyses: {len(results['deep_analyses'])}")
        print(f"  Improvements proposed: {results['improvements_proposed']}")
        print(f"{'=' * 60}\n")

    return results


async def _send_pipeline_notification(gateway_url: str, results: dict, tracker: ProgressTracker) -> None:
    """Send pipeline results to gateway for messaging broadcast."""
    import httpx

    arxiv = results.get("arxiv", {})
    lines = [
        f"**Way2AGI Research Pipeline — {results['date']}**",
        "",
        f"arXiv: {arxiv.get('total', 0)} papers, {arxiv.get('relevant', 0)} relevant",
        f"Deep analyses: {len(results['deep_analyses'])}",
        f"Improvements proposed: {results['improvements_proposed']}",
        "",
    ]

    for a in results["deep_analyses"][:3]:
        lines.append(f"[{a['impact'].upper()}] {a['title']}")
        lines.append(f"  {a['insights']} insights, {a['actions']} actions")
        lines.append("")

    pending = tracker.get_pending_actions(min_priority=7)
    if pending:
        lines.append("**High-Priority Actions:**")
        for p in pending[:3]:
            lines.append(f"  P{p['priority']} [{p['module']}] {p['description'][:50]}")

    message = "\n".join(lines)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{gateway_url}/broadcast", json={
                "type": "research_pipeline",
                "text": message,
                "priority": 7,
            })
    except Exception:
        pass


# CLI entry point
if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Way2AGI Full Research Pipeline")
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument("--notify", "-n", help="Gateway URL for notifications")
    parser.add_argument("--models", "-m", nargs="+", help="Models for deep analysis")

    args = parser.parse_args()

    asyncio.run(run_full_pipeline(
        output_dir=args.output,
        notify_url=args.notify,
        github_token=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
        deep_analysis_models=args.models,
    ))
