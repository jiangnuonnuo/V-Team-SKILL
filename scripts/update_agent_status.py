#!/usr/bin/env python3
"""Update a versioned agent file as a compact living status document."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List


MANAGED_SECTIONS = {
    "Current Status": "current",
    "Completed": "done",
    "In Progress": "progress",
    "Changed Files": "changed",
    "Evidence": "test",
    "Blockers": "blocker",
    "Needs From Others": "need",
    "Handoff": "handoff",
    "Next Suggestions": "next",
    "Key Updates": "note",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update a compact Project Harness Lite agent status.")
    parser.add_argument("--project-root", required=True, help="Project root path.")
    parser.add_argument("--version", default="v1", help="Demand implementation version.")
    parser.add_argument("--agent-id", required=True, help="Agent id, for example backend-2.")
    parser.add_argument("--mode", choices=["merge", "replace"], default="merge", help="Merge with existing section items or replace them.")
    parser.add_argument("--state", default="updated", help="Current state, for example done or blocked.")
    parser.add_argument("--summary", default="", help="Short current summary.")
    parser.add_argument("--done", action="append", default=[], help="Completed item. Repeatable.")
    parser.add_argument("--progress", action="append", default=[], help="In-progress item. Repeatable.")
    parser.add_argument("--changed", action="append", default=[], help="Changed file path. Repeatable.")
    parser.add_argument("--test", action="append", default=[], help="Test/build evidence. Repeatable.")
    parser.add_argument("--blocker", action="append", default=[], help="Blocker. Repeatable.")
    parser.add_argument("--need", action="append", default=[], help="Need from another agent. Repeatable.")
    parser.add_argument("--handoff", action="append", default=[], help="Handoff note. Repeatable.")
    parser.add_argument("--next", action="append", default=[], help="Next suggestion. Repeatable.")
    parser.add_argument("--note", action="append", default=[], help="Important status note. Repeatable; only recent notes are kept.")
    return parser.parse_args()


def safe_agent_id(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_.-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    if not value:
        raise ValueError("--agent-id cannot be empty after normalization.")
    return value


def clean_item(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^[-*+]\s*", "", value)
    return value.strip()


def unique(items: Iterable[str]) -> List[str]:
    result: List[str] = []
    for item in items:
        value = clean_item(item)
        if value and value.lower() != "none" and value not in result:
            result.append(value)
    return result


def section_bounds(lines: List[str], title: str) -> tuple[int, int] | None:
    header = f"## {title}".lower()
    start = -1
    for index, line in enumerate(lines):
        if line.strip().lower() == header:
            start = index
            break
    if start == -1:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return start, end


def read_section_items(text: str, title: str) -> List[str]:
    lines = text.splitlines()
    bounds = section_bounds(lines, title)
    if not bounds:
        return []
    _, end = bounds
    start = bounds[0] + 1
    values: List[str] = []
    for line in lines[start:end]:
        stripped = line.strip()
        if stripped.startswith("-"):
            value = clean_item(stripped)
            if value and value != ":":
                values.append(value)
    return unique(values)


def replace_section(text: str, title: str, body_lines: List[str]) -> str:
    lines = text.splitlines()
    bounds = section_bounds(lines, title)
    new_block = [f"## {title}", *body_lines, ""]
    if bounds:
        start, end = bounds
        lines[start:end] = new_block
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(new_block)
    return "\n".join(lines).rstrip() + "\n"


def bullet_lines(items: Iterable[str]) -> List[str]:
    values = unique(items)
    return [f"- {item}" for item in values] if values else ["-"]


def merged_items(text: str, title: str, incoming: Iterable[str], mode: str) -> List[str]:
    new_items = unique(incoming)
    if mode == "replace":
        return new_items
    return unique([*read_section_items(text, title), *new_items])


def main() -> int:
    args = parse_args()
    root = Path(args.project_root).resolve()
    version = args.version.strip() or "v1"
    agent_id = safe_agent_id(args.agent_id)
    agent_file = root / "Plan" / "versions" / version / "agents" / f"{agent_id}.md"

    if not agent_file.exists():
        raise FileNotFoundError(
            f"Agent file not found: {agent_file}. Register the agent in this version first."
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = agent_file.read_text(encoding="utf-8")
    summary = args.summary or "Updated current work state."
    text = replace_section(
        text,
        "Current Status",
        [
            f"- State: {args.state}",
            f"- Summary: {summary}",
            f"- Last updated: {now}",
        ],
    )

    incoming_by_title = {
        "Completed": args.done,
        "In Progress": args.progress,
        "Changed Files": args.changed,
        "Evidence": args.test,
        "Blockers": args.blocker,
        "Needs From Others": args.need,
        "Handoff": args.handoff,
        "Next Suggestions": args.next,
    }
    for title, incoming in incoming_by_title.items():
        items = merged_items(text, title, incoming, args.mode)
        text = replace_section(text, title, bullet_lines(items))

    notes = args.note or [summary]
    note_items = [f"{now}: {item}" for item in unique(notes)]
    if args.mode == "replace":
        key_updates = note_items
    else:
        key_updates = unique([*note_items, *read_section_items(text, "Key Updates")])[:8]
    text = replace_section(text, "Key Updates", bullet_lines(key_updates))

    agent_file.write_text(text, encoding="utf-8")
    print(f"[OK] Updated compact status in {agent_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
