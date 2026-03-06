"""
Daily Research Cron — Automated arXiv scanning and concept generation.

Runs daily (default: 06:00 UTC) and:
1. Fetches latest papers from cs.AI, cs.LG, cs.CL, cs.MA
2. Scores each paper against our 6 AGI goals
3. Generates implementation concepts for high-scoring papers
4. Saves report to ~/.way2agi/research/
5. Optionally sends summary to Telegram/messaging channels

Can be installed as:
- systemd timer (Linux/WSL2)
- crontab entry
- Termux cron (via crond)
- Way2AGI CognitiveScheduler task
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from .arxiv_crawler import crawl_and_score, save_report, print_report
from .pipeline import run_full_pipeline
from .model_scanner import scan_all_providers, save_model_report


async def run_daily_research(
    output_dir: str | Path | None = None,
    notify_url: str | None = None,
    threshold: float = 0.25,
    verbose: bool = True,
) -> dict:
    """
    Execute the daily research pipeline.

    Returns a summary dict suitable for posting to messaging channels.
    """
    out = Path(output_dir) if output_dir else Path.home() / ".way2agi" / "research"

    if verbose:
        print(f"[{datetime.now().isoformat()}] Way2AGI Daily Research starting...")

    # Crawl and score
    report = await crawl_and_score(threshold=threshold)

    # Save report
    report_path = save_report(report, out)

    if verbose:
        print_report(report, top_n=10)
        print(f"Report saved: {report_path}")

    # Build summary for notifications
    summary = {
        "date": report.date,
        "total": report.total_papers,
        "relevant": report.relevant_papers,
        "implement": report.implement_papers,
        "study": report.study_papers,
        "top_papers": [
            {
                "title": sp.paper.title[:80],
                "url": sp.paper.url,
                "score": sp.alignment.overall_score,
                "goal": sp.alignment.top_goal.value if sp.alignment.top_goal else "?",
                "recommendation": sp.alignment.recommendation,
                "concepts": sp.concepts[:2],
            }
            for sp in report.papers[:5]
            if sp.alignment.is_relevant
        ],
    }

    # Notify via gateway WebSocket if URL provided
    if notify_url:
        await _send_notification(notify_url, summary)

    return summary


async def _send_notification(gateway_url: str, summary: dict) -> None:
    """Send research summary to Way2AGI gateway for broadcast."""
    import httpx

    # Format message for messaging channels
    lines = [
        f"**Way2AGI Research Report — {summary['date']}**",
        f"Scanned: {summary['total']} | Relevant: {summary['relevant']} | "
        f"Implement: {summary['implement']} | Study: {summary['study']}",
        "",
    ]

    for p in summary["top_papers"]:
        lines.append(f"[{p['recommendation'].upper()}] ({p['goal']}, {p['score']:.2f})")
        lines.append(f"  {p['title']}")
        lines.append(f"  {p['url']}")
        for c in p["concepts"]:
            lines.append(f"  -> {c[:80]}")
        lines.append("")

    message = "\n".join(lines)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Post as perception to the cognitive workspace
            await client.post(f"{gateway_url}/broadcast", json={
                "type": "research_report",
                "text": message,
                "priority": 6,
            })
    except Exception as e:
        print(f"[Research] Notification failed: {e}")


def generate_crontab_entry() -> str:
    """Generate a crontab line for daily execution at 06:00 UTC."""
    script = Path(__file__).resolve()
    python = sys.executable
    return f"0 6 * * * {python} -m research.src.cron >> ~/.way2agi/research/cron.log 2>&1"


def generate_systemd_timer() -> tuple[str, str]:
    """Generate systemd service + timer files."""
    python = sys.executable

    service = f"""[Unit]
Description=Way2AGI Daily Research Crawler
After=network-online.target

[Service]
Type=oneshot
ExecStart={python} -m research.src.cron
WorkingDirectory={Path.home() / "repos" / "Way2AGI"}
Environment=HOME={Path.home()}
"""

    timer = """[Unit]
Description=Way2AGI Daily Research Timer

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
"""
    return service, timer


def generate_termux_cron() -> str:
    """Generate Termux crond entry."""
    python = sys.executable
    return f"0 6 * * * {python} -m research.src.cron >> $HOME/.way2agi/research/cron.log 2>&1"


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Way2AGI Daily Research Cron")
    parser.add_argument("--output", "-o", help="Output directory", default=None)
    parser.add_argument("--notify", "-n", help="Gateway URL for notifications", default=None)
    parser.add_argument("--threshold", "-t", type=float, default=0.25, help="Relevance threshold")
    parser.add_argument("--install-cron", action="store_true", help="Print crontab entry")
    parser.add_argument("--install-systemd", action="store_true", help="Print systemd files")

    parser.add_argument("--full", action="store_true",
                        help="Run full pipeline (deep analysis + self-improvement)")
    parser.add_argument("--models", action="store_true",
                        help="Scan for useful AI models across all providers")

    args = parser.parse_args()

    if args.install_cron:
        print(generate_crontab_entry())
        sys.exit(0)

    if args.install_systemd:
        service, timer = generate_systemd_timer()
        print("=== way2agi-research.service ===")
        print(service)
        print("=== way2agi-research.timer ===")
        print(timer)
        sys.exit(0)

    if args.models:
        # Scan for useful AI models
        async def _run_model_scan():
            report = await scan_all_providers(verbose=True)
            out = Path(args.output) if args.output else Path.home() / ".way2agi" / "research"
            path = save_model_report(report, out)
            print(f"\nReport saved: {path}")
        asyncio.run(_run_model_scan())
    elif args.full:
        # Full pipeline: crawl + deep analysis + self-improvement + progress tracking
        import os
        asyncio.run(run_full_pipeline(
            output_dir=args.output,
            notify_url=args.notify,
            github_token=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
        ))
    else:
        # Quick scan only (no deep analysis)
        asyncio.run(run_daily_research(
            output_dir=args.output,
            notify_url=args.notify,
            threshold=args.threshold,
        ))
