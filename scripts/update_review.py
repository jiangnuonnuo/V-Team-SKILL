#!/usr/bin/env python3
"""Update the fixed pre-implementation review file for a version."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List


REVIEW_FILE = "current-requirement-review.md"
ROLE_SECTIONS = {
    "product": "Product Analysis",
    "architect": "Architect Analysis",
    "backend": "Backend Analysis",
    "frontend": "Frontend Analysis",
    "tester": "Tester Analysis",
    "devops": "DevOps Analysis",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Revise the fixed Project Harness Lite review file in place."
    )
    parser.add_argument("--project-root", required=True, help="Project root path.")
    parser.add_argument("--version", default="v1", help="Demand implementation version.")
    parser.add_argument("--reviewer", default="manager or architect", help="Review owner or chair.")
    parser.add_argument(
        "--status",
        choices=["draft", "in-review", "changes-requested", "approved", "rejected"],
        default="",
        help="Review gate status.",
    )
    parser.add_argument("--mode", choices=["merge", "replace"], default="merge")
    for role, section in ROLE_SECTIONS.items():
        parser.add_argument(
            f"--{role}-analysis",
            action="append",
            default=[],
            help=f"Add or replace an item in {section}. Repeatable.",
        )
    parser.add_argument("--meeting-state", default="", help="not started, scheduled, held, re-review, passed.")
    parser.add_argument("--meeting-note", action="append", default=[], help="Review meeting note. Repeatable.")
    parser.add_argument(
        "--issue",
        action="append",
        default=[],
        help="Add an issue as owner|issue|required change|status. Status defaults to open.",
    )
    parser.add_argument(
        "--set-issue-status",
        action="append",
        default=[],
        help="Update an existing issue as ID=status, for example R001=resolved.",
    )
    parser.add_argument(
        "--decision-result",
        choices=["pending", "changes-requested", "approved", "rejected"],
        default="",
        help="Final or current meeting decision.",
    )
    parser.add_argument("--decision-note", default="", help="Decision summary.")
    parser.add_argument("--condition", action="append", default=[], help="Approval condition. Repeatable.")
    parser.add_argument("--revision-note", action="append", default=[], help="Revision log note. Repeatable.")
    return parser.parse_args()


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


def replace_section(text: str, title: str, body_lines: List[str]) -> str:
    lines = text.splitlines()
    new_block = [f"## {title}", *body_lines, ""]
    bounds = section_bounds(lines, title)
    if bounds:
        start, end = bounds
        lines[start:end] = new_block
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(new_block)
    return "\n".join(lines).rstrip() + "\n"


def read_section_items(text: str, title: str) -> List[str]:
    lines = text.splitlines()
    bounds = section_bounds(lines, title)
    if not bounds:
        return []
    start, end = bounds
    values: List[str] = []
    for raw in lines[start + 1 : end]:
        stripped = raw.strip()
        if stripped.startswith("- "):
            value = clean_item(stripped)
            if value and value != ":":
                values.append(value)
    return unique(values)


def bullet_lines(items: Iterable[str]) -> List[str]:
    values = unique(items)
    return [f"- {item}" for item in values] if values else ["-"]


def merged_items(text: str, title: str, incoming: Iterable[str], mode: str) -> List[str]:
    new_items = unique(incoming)
    if mode == "replace":
        return new_items
    return unique([*read_section_items(text, title), *new_items])


def first_field(text: str, field: str, default: str = "") -> str:
    prefix = f"- {field}:"
    for raw in text.splitlines():
        line = raw.strip()
        if line.lower().startswith(prefix.lower()):
            return line.split(":", 1)[1].strip()
    return default


def table_cell(value: str) -> str:
    return value.replace("|", "/").replace("\n", " ").strip() or "-"


def parse_issue_rows(text: str) -> List[List[str]]:
    lines = text.splitlines()
    bounds = section_bounds(lines, "Review Issues")
    if not bounds:
        return []
    _, end = bounds
    rows: List[List[str]] = []
    for raw in lines[bounds[0] + 1 : end]:
        stripped = raw.strip()
        if not stripped.startswith("|") or "---" in stripped or stripped.lower().startswith("| id "):
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if len(parts) >= 5:
            rows.append(parts[:5])
    return rows


def next_issue_id(rows: List[List[str]]) -> str:
    max_id = 0
    for row in rows:
        match = re.match(r"R(\d+)$", row[0].strip(), re.IGNORECASE)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return f"R{max_id + 1:03d}"


def apply_issue_status(rows: List[List[str]], updates: Iterable[str]) -> None:
    for update in updates:
        if "=" not in update:
            raise ValueError("--set-issue-status must use ID=status format.")
        issue_id, status = [part.strip() for part in update.split("=", 1)]
        for row in rows:
            if row[0].lower() == issue_id.lower():
                row[4] = table_cell(status)
                break


def add_issues(rows: List[List[str]], specs: Iterable[str]) -> None:
    for spec in specs:
        parts = [part.strip() for part in spec.split("|")]
        if len(parts) < 3:
            raise ValueError("--issue must use owner|issue|required change|status format.")
        owner, issue, required = parts[:3]
        status = parts[3] if len(parts) > 3 and parts[3] else "open"
        rows.append([next_issue_id(rows), table_cell(owner), table_cell(issue), table_cell(required), table_cell(status)])


def issue_table(rows: List[List[str]]) -> List[str]:
    result = [
        "| ID | Owner | Issue | Required Change | Status |",
        "|---|---|---|---|---|",
    ]
    result.extend(f"| {' | '.join(row)} |" for row in rows)
    return result


def default_review(version: str, now: str) -> str:
    return f"""# Requirement Review - {version}

## Review Gate
- Demand ID:
- Version: {version}
- Status: draft
- Review owner: manager or architect
- Implementation allowed: no
- Team mode:
- Last updated: {now}

## Review Scope
- Review type: pre-implementation requirement and landing-plan review
- Goal: confirm that product, architect, backend, frontend, and tester analyses are ready before development starts.
- Non-goal: this file is not a code-change review after implementation.

## Product Analysis
-

## Architect Analysis
-

## Backend Analysis
-

## Frontend Analysis
-

## Tester Analysis
-

## DevOps Analysis
- Optional; fill only when build, environment, deployment, release, script, or CI work is in scope.

## Review Meeting
- Meeting state: not started
- Chair: manager or architect
- Participants: product, architect, backend, frontend, tester
- Notes:

## Review Issues
| ID | Owner | Issue | Required Change | Status |
|---|---|---|---|---|

## Decision
- Result: pending
- Approver:
- Decision note:
- Conditions:

## Revision Log
- {now}: Created review file. Revise this file in place for every rejection, correction, and re-review.
"""


def main() -> int:
    args = parse_args()
    root = Path(args.project_root).resolve()
    version = args.version.strip() or "v1"
    review_dir = root / "Plan" / "versions" / version / "reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_file = review_dir / REVIEW_FILE
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not review_file.exists():
        review_file.write_text(default_review(version, now), encoding="utf-8")

    text = review_file.read_text(encoding="utf-8")
    status = args.status or first_field(text, "Status", "draft")
    decision_result = args.decision_result or first_field(text, "Result", "pending")
    if status == "approved" and not args.decision_result:
        decision_result = "approved"
    implementation_allowed = "yes" if status == "approved" and decision_result == "approved" else "no"

    text = replace_section(
        text,
        "Review Gate",
        [
            f"- Demand ID: {first_field(text, 'Demand ID')}",
            f"- Version: {version}",
            f"- Status: {status}",
            f"- Review owner: {args.reviewer}",
            f"- Implementation allowed: {implementation_allowed}",
            f"- Team mode: {first_field(text, 'Team mode')}",
            f"- Last updated: {now}",
        ],
    )

    for role, section in ROLE_SECTIONS.items():
        incoming = getattr(args, f"{role}_analysis")
        if incoming:
            text = replace_section(text, section, bullet_lines(merged_items(text, section, incoming, args.mode)))

    meeting_items = read_section_items(text, "Review Meeting")
    if args.mode == "replace" and (args.meeting_state or args.meeting_note):
        meeting_items = []
    meeting_state = args.meeting_state or first_field(text, "Meeting state", "not started")
    meeting_body = [
        f"- Meeting state: {meeting_state}",
        f"- Chair: {args.reviewer}",
        "- Participants: product, architect, backend, frontend, tester",
        "- Notes:",
    ]
    meeting_notes = unique([*meeting_items, *args.meeting_note])
    meeting_body.extend(f"  - {item}" for item in meeting_notes if not item.lower().startswith(("meeting state:", "chair:", "participants:", "notes:")))
    text = replace_section(text, "Review Meeting", meeting_body)

    issue_rows = parse_issue_rows(text)
    apply_issue_status(issue_rows, args.set_issue_status)
    add_issues(issue_rows, args.issue)
    text = replace_section(text, "Review Issues", issue_table(issue_rows))

    condition_items = merged_items(text, "Decision", args.condition, "merge")
    decision_body = [
        f"- Result: {decision_result}",
        f"- Approver: {args.reviewer if decision_result == 'approved' else first_field(text, 'Approver')}",
        f"- Decision note: {args.decision_note or first_field(text, 'Decision note')}",
        "- Conditions:",
    ]
    decision_body.extend(f"  - {item}" for item in condition_items if not item.lower().startswith(("result:", "approver:", "decision note:", "conditions:")))
    text = replace_section(text, "Decision", decision_body)

    open_issue_statuses = {"open", "todo", "changes-requested", "rejected", "blocked"}
    has_open_issue = any(row[4].strip().lower() in open_issue_statuses for row in issue_rows)
    implementation_allowed = (
        "yes"
        if status == "approved" and decision_result == "approved" and not has_open_issue
        else "no"
    )
    text = replace_section(
        text,
        "Review Gate",
        [
            f"- Demand ID: {first_field(text, 'Demand ID')}",
            f"- Version: {version}",
            f"- Status: {status}",
            f"- Review owner: {args.reviewer}",
            f"- Implementation allowed: {implementation_allowed}",
            f"- Team mode: {first_field(text, 'Team mode')}",
            f"- Last updated: {now}",
        ],
    )

    revision_notes = args.revision_note or [f"Review updated by {args.reviewer}; status={status}; decision={decision_result}."]
    revision_log = unique([f"{now}: {item}" for item in unique(revision_notes)] + read_section_items(text, "Revision Log"))
    text = replace_section(text, "Revision Log", bullet_lines(revision_log[:30]))

    review_file.write_text(text, encoding="utf-8")
    print(f"[OK] Updated review in place: {review_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
