#!/usr/bin/env python3
"""Count papers listed in README.md.

The "Recent Paper Updates" section is treated as an index and excluded from
the collection total, so papers listed there and again in their category are
not double-counted.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


HEADING_RE = re.compile(r"^(?:\*\s*)?(#{2,3})\s+(.+?)\s*$")
PAPER_RE = re.compile(r"^\[(?P<date>\d{4}-\d{2}(?:-\d{2})?)\]\s*(?P<body>.+)$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
ARXIV_RE = re.compile(r"^/(abs|pdf|html)/(?P<id>\d{4}\.\d{4,5})(?:v\d+)?/?$")

EXCLUDED_SECTIONS = {
    "🚩 News & Updates",
    "🔥 Recent Paper Updates",
    "Overview",
    "Citation",
}


def clean_heading(text: str) -> str:
    return text.strip().strip("#").strip()


def strip_outer_bold(line: str) -> str:
    line = line.strip()
    if line.startswith("**") and line.endswith("**"):
        return line[2:-2].strip()
    return line


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")

    if parts.netloc == "arxiv.org":
        match = ARXIV_RE.match(path)
        if match:
            path = f"/abs/{match.group('id')}"

    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def parse_paper(line: str) -> dict[str, str | bool] | None:
    line = strip_outer_bold(line)
    match = PAPER_RE.match(line)
    if not match:
        return None

    link_match = LINK_RE.search(match.group("body"))
    if not link_match:
        return None

    prefix = match.group("body")[: link_match.start()]
    return {
        "date": match.group("date"),
        "title": link_match.group(1).strip(),
        "url": link_match.group(2).strip(),
        "key": normalize_url(link_match.group(2)),
        "open": "✅" in prefix,
        "closed": "❌" in prefix,
        "starred": "🌟" in prefix,
    }


def iter_papers(readme: Path):
    section = None
    subsection = None

    for line_number, raw_line in enumerate(readme.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        heading = HEADING_RE.match(line)
        if heading:
            level, title = heading.groups()
            title = clean_heading(title)
            if level == "##":
                section = title
                subsection = None
            else:
                subsection = title
            continue

        paper = parse_paper(line)
        if not paper or not section:
            continue

        paper["section"] = section
        paper["subsection"] = subsection or ""
        paper["line"] = line_number
        paper["excluded"] = section in EXCLUDED_SECTIONS
        yield paper


def main() -> int:
    parser = argparse.ArgumentParser(description="Count unique papers in README.md.")
    parser.add_argument("readme", nargs="?", default="README.md", type=Path)
    args = parser.parse_args()

    papers = list(iter_papers(args.readme))
    counted = [paper for paper in papers if not paper["excluded"]]
    recent = [paper for paper in papers if paper["section"] == "🔥 Recent Paper Updates"]

    unique: dict[str, dict[str, str | bool]] = {}
    appearances = defaultdict(list)
    for paper in counted:
        key = str(paper["key"])
        unique.setdefault(key, paper)
        appearances[key].append(paper)

    by_section = Counter(str(paper["section"]) for paper in counted)
    by_section_subsection = Counter(
        f"{paper['section']} / {paper['subsection']}" if paper["subsection"] else str(paper["section"])
        for paper in counted
    )

    duplicate_keys = {key: rows for key, rows in appearances.items() if len(rows) > 1}

    print(f"Unique papers: {len(unique)}")
    print(f"Paper entries in counted sections: {len(counted)}")
    print(f"Recent update entries excluded from total: {len(recent)}")
    print(f"Starred papers: {sum(1 for paper in unique.values() if paper['starred'])}")
    print(f"Open-resource papers: {sum(1 for paper in unique.values() if paper['open'])}")
    print()

    print("By section:")
    for section, count in by_section.items():
        print(f"  {section}: {count}")

    memory_breakdown = {
        section: count
        for section, count in by_section_subsection.items()
        if section.startswith("Memory Consistency / ")
    }
    if memory_breakdown:
        print()
        print("Memory Consistency breakdown:")
        for section, count in memory_breakdown.items():
            print(f"  {section}: {count}")

    if duplicate_keys:
        print()
        print("Duplicate counted links:")
        for rows in duplicate_keys.values():
            title = rows[0]["title"]
            locations = ", ".join(f"{row['section']}:{row['line']}" for row in rows)
            print(f"  {title} ({locations})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
