"""Interactive CLI — search trends from the terminal."""

import asyncio
import json
import textwrap
from datetime import datetime
from pathlib import Path

from mcp_trends.sources.hackernews import search_hackernews
from mcp_trends.sources.youtube import search_youtube
from mcp_trends.sources.github import search_github
from mcp_trends.sources.google import search_google_linkedin
from mcp_trends.chains.summarizer import summarize_trends

RESULTS_DIR = Path(__file__).parent / "results"

SOURCES = {
    "1": ("Hacker News", search_hackernews),
    "2": ("YouTube", search_youtube),
    "3": ("GitHub", search_github),
    "4": ("Google/LinkedIn", search_google_linkedin),
    "5": ("All + Summary", None),
}


def print_result(result):
    if result.error:
        print(f"  ERROR: {result.error}")
        return
    for i, item in enumerate(result.results, 1):
        print(f"  {i}. {item.title}")
        print(f"     {item.url}")
        meta_parts = []
        for k, v in item.metadata.items():
            if k in ("raw_response", "description"):
                continue
            if v:
                meta_parts.append(f"{k}={v}")
        if meta_parts:
            print(f"     {', '.join(meta_parts)}")
    print(f"\n  Total: {len(result.results)} results")


def print_summary(summary):
    print("\n  Top Trends:")
    for i, trend in enumerate(summary.top_trends, 1):
        print(f"    {i}. {trend}")

    if summary.content_angles:
        print("\n  LinkedIn Content Angles:")
        for i, angle in enumerate(summary.content_angles, 1):
            print(f"\n    {i}. HOOK: \"{angle.hook}\"")
            print(f"       ANGLE: {angle.angle}")
            if angle.supporting_sources:
                print(f"       SOURCES: {', '.join(angle.supporting_sources)}")

    print("\n  Analysis:")
    for line in textwrap.wrap(summary.analysis, width=80):
        print(f"    {line}")


def save_result(topic, data):
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = topic.lower().replace(" ", "_")[:30]
    path = RESULTS_DIR / f"{ts}_{slug}.json"
    path.write_text(json.dumps(data, indent=2, default=str))
    print(f"\n  Saved to {path}")


async def search_all(topic, limit, period="week"):
    results = await asyncio.gather(
        search_hackernews(topic, limit, period),
        search_youtube(topic, limit),
        search_github(topic, limit),
        search_google_linkedin(topic, limit),
    )
    names = ["Hacker News", "YouTube", "GitHub", "Google/LinkedIn"]
    source_map = {}
    for name, result in zip(names, results):
        print(f"\n--- {name} ---")
        print_result(result)
        source_map[result.source] = result

    print("\n--- AI Summary ---")
    summary = await summarize_trends(topic, source_map)
    print_summary(summary)

    save_result(topic, {
        "topic": topic,
        "searched_at": datetime.now().isoformat(),
        "sources": {k: v.model_dump() for k, v in source_map.items()},
        "summary": summary.model_dump(),
    })


async def main():
    print("=" * 50)
    print("  MCP Trends Server — Interactive CLI")
    print("=" * 50)

    while True:
        print("\nEnter a topic to search (or 'q' to quit):")
        topic = input("> ").strip()
        if not topic or topic.lower() == "q":
            print("Bye!")
            break

        print("\nSources:")
        for key, (name, _) in SOURCES.items():
            print(f"  {key}. {name}")
        print("Pick a source [1-5, default=5]:")
        choice = input("> ").strip() or "5"

        print("\nTime period — w=week, m=month, q=quarter [default=w]:")
        period_input = input("> ").strip().lower() or "w"
        period_map = {"w": "week", "m": "month", "q": "quarter"}
        period = period_map.get(period_input, "week")

        print(f"\nHow many results? [default=5]:")
        limit_str = input("> ").strip() or "5"
        limit = int(limit_str) if limit_str.isdigit() else 5

        print(f"\nSearching '{topic}' (period={period})...\n")

        if choice == "5":
            await search_all(topic, limit, period)
        elif choice in SOURCES:
            name, fn = SOURCES[choice]
            print(f"--- {name} ---")
            if name == "Hacker News":
                result = await fn(topic, limit, period)
            else:
                result = await fn(topic, limit)
            print_result(result)
            save_result(topic, {
                "topic": topic,
                "searched_at": datetime.now().isoformat(),
                "source": name,
                "period": period,
                "results": result.model_dump(),
            })
        else:
            print(f"Unknown choice: {choice}")


if __name__ == "__main__":
    asyncio.run(main())
