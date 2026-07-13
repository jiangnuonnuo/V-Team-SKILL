#!/usr/bin/env python3
"""Run one versioned manager cycle for Project Harness Lite."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROLES = ["frontend", "backend", "product", "architect", "tester", "devops", "manager"]

SOLO_ROLE_ORDER = "product -> architect -> backend/frontend -> tester -> manager"


@dataclass
class AgentData:
    agent_id: str
    role: str
    responsibility: str
    completed: List[str]
    progress: List[str]
    changed: List[str]
    evidence: List[str]
    blockers: List[str]
    needs: List[str]
    handoff: List[str]
    next_items: List[str]
    path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one Project Harness Lite manager cycle.")
    parser.add_argument("--project-root", required=True, help="Project root containing Plan/.")
    parser.add_argument("--version", default="v1", help="Demand implementation version.")
    parser.add_argument(
        "--test-note",
        action="append",
        default=[],
        help="Visible test/build result to include in verification. Repeatable.",
    )
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "cp936", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return ""


def append_unique(items: List[str], value: str) -> None:
    value = value.strip()
    if value and value not in items and value.lower() != "none":
        items.append(value)


def clean_bullet(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[-*+]\s*", "", line)
    line = re.sub(r"^\d+[.)]\s*", "", line)
    return line.strip()


def section_items(text: str, headings: Iterable[str]) -> List[str]:
    wanted = {heading.lower() for heading in headings}
    current = ""
    labeled_block = ""
    found: List[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        indented_bullet = raw.startswith("  - ") or raw.startswith("\t- ")
        if stripped.startswith("#"):
            current = stripped.lstrip("#").strip().lower()
            labeled_block = ""
            continue
        label_match = re.match(r"^-\s+([^:]+):\s*$", stripped)
        if label_match:
            label = label_match.group(1).strip().lower()
            labeled_block = label if label in wanted else ""
            continue
        if stripped.startswith("- ") and current in wanted:
            append_unique(found, clean_bullet(stripped))
        elif indented_bullet and current in wanted:
            append_unique(found, clean_bullet(stripped))
        elif indented_bullet and labeled_block in wanted:
            append_unique(found, clean_bullet(stripped))
    return found


def first_field(text: str, field: str) -> str:
    prefix = f"- {field}:"
    for raw in text.splitlines():
        line = raw.strip()
        if line.lower().startswith(prefix.lower()):
            return line.split(":", 1)[1].strip()
    return ""


def parse_agent(path: Path) -> AgentData:
    text = read_text(path)
    agent_id = first_field(text, "Agent ID") or path.stem
    role = first_field(text, "Role") or infer_role(path.stem)
    responsibility = first_field(text, "Responsibility")
    return AgentData(
        agent_id=agent_id,
        role=role if role in ROLES else "unknown",
        responsibility=responsibility,
        completed=section_items(text, ["Completed"]),
        progress=section_items(text, ["In Progress"]),
        changed=section_items(text, ["Changed Files"]),
        evidence=section_items(text, ["Evidence"]),
        blockers=section_items(text, ["Blockers"]),
        needs=section_items(text, ["Needs From Others"]),
        handoff=section_items(text, ["Handoff"]),
        next_items=section_items(text, ["Next Suggestions"]),
        path=path,
    )


def infer_role(agent_id: str) -> str:
    low = agent_id.lower()
    for role in ROLES:
        if low == role or low.startswith(f"{role}-"):
            return role
    return "unknown"


def find_work_docs(version_dir: Path) -> List[Path]:
    work_file = version_dir / "work.md"
    return [work_file] if work_file.exists() else []


def review_gate(version_dir: Path) -> Dict[str, str]:
    review_file = version_dir / "reviews" / "current-requirement-review.md"
    if not review_file.exists():
        return {
            "path": review_file.as_posix(),
            "status": "missing",
            "allowed": "no",
            "result": "missing",
            "owner": "manager or architect",
        }
    text = read_text(review_file)
    status = first_field(text, "Status") or "draft"
    allowed = first_field(text, "Implementation allowed") or "no"
    result = first_field(text, "Result") or "pending"
    owner = first_field(text, "Review owner") or first_field(text, "Approver") or "manager or architect"
    return {
        "path": review_file.as_posix(),
        "status": status,
        "allowed": allowed,
        "result": result,
        "owner": owner,
    }


def detect_team_mode(work_docs: List[Path], agents: List[AgentData]) -> str:
    for doc in work_docs:
        text = read_text(doc).lower()
        if "mode: solo" in text:
            return "solo"
    if any(agent.agent_id.startswith("solo-") for agent in agents):
        return "solo"
    return "multi"


def slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    return value[:80] if value else "work-auto"


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def path_from_claim(root: Path, claim: str) -> Tuple[Path | None, str]:
    cleaned = clean_bullet(claim).strip("`'\"")
    cleaned = cleaned.split(":", 1)[0].strip()
    if not cleaned or cleaned == "-":
        return None, cleaned
    candidate = (root / cleaned).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, cleaned
    return candidate, cleaned


def evidence_for_agent(root: Path, agent: AgentData) -> Tuple[str, List[str], List[str]]:
    notes: List[str] = []
    mismatches: List[str] = []
    existing_files = 0
    claimed_files = 0

    for claim in agent.changed:
        path, shown = path_from_claim(root, claim)
        if path is None:
            continue
        claimed_files += 1
        if path.exists():
            existing_files += 1
            notes.append(f"file exists: {shown}")
        else:
            mismatches.append(f"claimed file missing: {shown}")

    has_completion = bool(agent.completed)
    has_test_evidence = any(item and item != "-" for item in agent.evidence)
    has_blocker = bool(agent.blockers)

    has_claim = has_completion or bool(agent.progress) or bool(agent.next_items)

    if has_blocker:
        label = "Blocked"
    elif mismatches:
        label = "Mismatch"
    elif has_completion and (existing_files > 0 or has_test_evidence):
        label = "Verified"
    elif has_completion:
        label = "Unverified"
    elif has_claim:
        label = "Unverified"
    else:
        label = "Planned"

    if claimed_files == 0:
        notes.append("no changed files claimed")
    if label == "Planned":
        notes.append("no completion claim yet")
    if has_test_evidence:
        notes.extend([f"evidence note: {item}" for item in agent.evidence])
    return label, notes, mismatches


def git_status(root: Path) -> List[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def summarize(items: Iterable[str], limit: int = 3) -> str:
    values = [item for item in items if item and item != "-"]
    if not values:
        return "-"
    return "; ".join(values[:limit])


def table_cell(value: str) -> str:
    return value.replace("|", "/").replace("\n", " ").strip() or "-"


def review_task_for_role(role: str) -> str:
    tasks = {
        "product": "Complete product demand analysis, user value, non-goals, and acceptance criteria in the review file.",
        "architect": "Complete architecture analysis and chair or prepare the review decision.",
        "backend": "Complete backend feasibility, API/data/domain impact, and backend risk analysis.",
        "frontend": "Complete frontend flow, state, integration dependency, and UI risk analysis.",
        "tester": "Complete acceptance checks, regression scope, and evidence requirements.",
        "devops": "Add DevOps analysis only if build, environment, deployment, release, script, or CI work is in scope.",
        "manager": "Chair the review meeting, record issues, and keep the review gate current.",
    }
    return tasks.get(role, "Complete this role's review analysis before implementation.")


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


def role_groups(agents: List[AgentData]) -> Dict[str, List[AgentData]]:
    groups: Dict[str, List[AgentData]] = {role: [] for role in ROLES}
    groups["unknown"] = []
    for agent in agents:
        groups.setdefault(agent.role, []).append(agent)
    return groups


def refresh_work_plan(
    work_docs: List[Path],
    root: Path,
    corrections: List[Tuple[str, str, str]],
    review: Dict[str, str],
) -> None:
    if not work_docs:
        return
    work_file = work_docs[0]
    text = read_text(work_file)
    if not text:
        return
    if corrections:
        gap_lines = ["| Owner | Gap | Required Correction |", "|---|---|---|"]
        for owner, task, reason in corrections:
            gap_lines.append(f"| {table_cell(owner)} | {table_cell(reason)} | {table_cell(task)} |")
    else:
        gap_lines = ["- No active manager correction gaps."]
    review_path = Path(review["path"])
    review_rel = rel(review_path, root)
    review_allowed = "yes" if review["status"] == "approved" and review["allowed"].lower() == "yes" else "no"
    text = replace_section(
        text,
        "Review Gate",
        [
            f"- Requirement review: {review_rel}",
            f"- Status: {review['status']}",
            f"- Implementation allowed: {review_allowed}",
            "- Rule: development starts only after manager or architect marks the current review file approved.",
        ],
    )
    text = replace_section(text, "Active Gaps", gap_lines)
    text = replace_section(
        text,
        "Manager Corrections",
        [
            "- This section is rewritten by the manager cycle when verification finds task gaps.",
            "- Treat it as the current correction plan, not a dialogue log.",
            f"- Source project: {rel(work_file, root)}",
        ],
    )
    work_file.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.project_root).resolve()
    plan = root / "Plan"
    version = slug(args.version.strip() or "v1")
    version_dir = plan / "versions" / version
    dirs = {
        "agents": version_dir / "agents",
        "roles": version_dir / "roles",
        "reports": version_dir / "reports",
        "verification": version_dir / "verification",
        "reviews": version_dir / "reviews",
        "next": version_dir / "next-steps",
        "archive": version_dir / "archive",
        "memory": plan / "memory",
    }
    for directory in dirs.values():
        ensure_dir(directory)

    work_docs = find_work_docs(version_dir)
    work_id = version
    now = datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M")

    agent_files = sorted(dirs["agents"].glob("*.md"), key=lambda p: p.name.lower())
    agents = [parse_agent(path) for path in agent_files]
    groups = role_groups(agents)
    team_mode = detect_team_mode(work_docs, agents)
    review = review_gate(version_dir)
    review_allowed = review["status"] == "approved" and review["allowed"].lower() == "yes"
    git_lines = git_status(root)

    evidence_rows: List[Tuple[AgentData, str, List[str], List[str]]] = []
    for agent in agents:
        label, notes, mismatches = evidence_for_agent(root, agent)
        evidence_rows.append((agent, label, notes, mismatches))

    verified_count = sum(1 for _, label, _, _ in evidence_rows if label == "Verified")
    mismatch_count = sum(1 for _, label, _, _ in evidence_rows if label == "Mismatch")
    blocked_count = sum(1 for _, label, _, _ in evidence_rows if label == "Blocked")
    unverified_count = sum(1 for _, label, _, _ in evidence_rows if label == "Unverified")
    planned_count = sum(1 for _, label, _, _ in evidence_rows if label == "Planned")
    confidence = "High" if agents and mismatch_count == 0 and unverified_count == 0 else "Medium"
    if mismatch_count or blocked_count:
        confidence = "Low" if mismatch_count else "Medium"

    verification_file = dirs["verification"] / "current-verification.md"
    report_file = dirs["reports"] / "current-product-report.md"
    plan_file = dirs["next"] / "current-team-plan.md"
    archive_file = dirs["archive"] / "project-archive.md"
    memory_file = dirs["memory"] / "project-memory.md"

    verification_lines = [
        f"# Verification Report - {version}",
        "",
        "## Verification Summary",
        f"- Overall evidence health: {verified_count} verified, {unverified_count} unverified, {mismatch_count} mismatch, {blocked_count} blocked, {planned_count} planned",
        f"- Manager confidence: {confidence}",
        f"- Team mode: {team_mode}",
        f"- Review gate: {review['status']} / implementation allowed: {review['allowed']}",
        f"- Checked at: {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Work Requirements Checked",
    ]
    if work_docs:
        for doc in work_docs:
            verification_lines.append(f"- {rel(doc, root)}")
    else:
            verification_lines.append(f"- No work document found at Plan/versions/{version}/work.md.")
    verification_lines.extend(
        [
            "",
            "## Agent Claim Evidence",
            "| Agent | Role | Claim | Evidence Label | Evidence | Manager Note |",
            "|---|---|---|---|---|---|",
        ]
    )
    for agent, label, notes, mismatches in evidence_rows:
        claim = summarize(agent.completed or agent.progress or agent.next_items, 2)
        evidence = summarize(notes, 3)
        manager_note = summarize(mismatches, 3)
        if manager_note == "-" and label == "Unverified":
            manager_note = "Need changed files, tests, or direct implementation evidence."
        verification_lines.append(
            f"| {table_cell(agent.agent_id)} | {table_cell(agent.role)} | {table_cell(claim)} | {label} | {table_cell(evidence)} | {table_cell(manager_note)} |"
        )
    verification_lines.append(f"- Requirement review: {rel(Path(review['path']), root)}")
    verification_lines.extend(["", "## Project Reality Checks", "- Changed files checked:"])
    checked_files = [note for _, _, notes, _ in evidence_rows for note in notes if note.startswith("file exists:")]
    if checked_files:
        for item in checked_files:
            verification_lines.append(f"  - {item}")
    else:
        verification_lines.append("  - No existing changed-file evidence found.")
    verification_lines.append("- Git status snapshot:")
    if git_lines:
        for line in git_lines[:20]:
            verification_lines.append(f"  - {line}")
    else:
        verification_lines.append("  - No git status available or repository has no visible changes.")
    verification_lines.append("- Tests/builds checked:")
    if args.test_note:
        for note in args.test_note:
            verification_lines.append(f"  - {note}")
    else:
        verification_lines.append("  - No test/build note supplied to manager cycle.")
    verification_lines.extend(["", "## Correction Tasks", "| Owner | Task | Reason | Done Definition |", "|---|---|---|---|"])
    correction_rows = 0
    corrections: List[Tuple[str, str, str]] = []
    if not review_allowed:
        reason = f"review gate is {review['status']} and implementation allowed is {review['allowed']}"
        task = "Complete and approve current-requirement-review.md before development."
        corrections.append((review["owner"], task, reason))
        verification_lines.append(
            f"| {table_cell(review['owner'])} | {table_cell(task)} | {table_cell(reason)} | Update the existing review file in place and set Implementation allowed: yes. |"
        )
        correction_rows += 1
    for agent, label, _, mismatches in evidence_rows:
        if label in {"Unverified", "Mismatch", "Blocked"}:
            reason = summarize(mismatches or agent.blockers or ["Evidence is incomplete."], 2)
            task = "Provide implementation evidence or fix the mismatch."
            if label == "Blocked":
                task = "Resolve or escalate blocker."
            corrections.append((agent.agent_id, task, reason))
            verification_lines.append(
                f"| {table_cell(agent.agent_id)} | {table_cell(task)} | {table_cell(reason)} | Update agent card with file/test evidence or blocker resolution. |"
            )
            correction_rows += 1
    if correction_rows == 0:
        verification_lines.append("| manager | Continue monitoring | No correction task found | Recheck next cycle |")
    verification_file.write_text("\n".join(verification_lines) + "\n", encoding="utf-8")
    refresh_work_plan(work_docs, root, corrections, review)

    report_lines = [
        f"# Product Report - {version}",
        "",
        "## Executive Summary",
        f"- Current phase: Manager cycle at {now.strftime('%Y-%m-%d %H:%M')}",
        f"- Product health: {'Blocked by review gate' if not review_allowed else 'At risk' if mismatch_count or blocked_count else 'On track with evidence gaps' if unverified_count else 'On track'}",
        f"- Manager confidence: {confidence}",
        f"- Team mode: {team_mode}",
        f"- Review gate: {review['status']} / implementation allowed: {review['allowed']}",
        "",
        "## Scope Progress",
        f"- Planned: {summarize([rel(doc, root) for doc in work_docs], 3)}",
        f"- Verified complete: {verified_count} agent claim group(s)",
        f"- Unverified claims: {unverified_count}",
        f"- Planned role cards: {planned_count}",
        f"- Remaining: {mismatch_count + blocked_count + unverified_count} item(s) need manager follow-up",
        f"- Review blocker: {'none' if review_allowed else 'pre-implementation review is not approved'}",
        "",
        "## Role Snapshot",
        "| Role | Agents | Verified Progress | Risks | Needs |",
        "|---|---|---|---|---|",
    ]
    label_by_agent = {agent.agent_id: label for agent, label, _, _ in evidence_rows}
    for role in [*ROLES, "unknown"]:
        role_agents = groups.get(role, [])
        if not role_agents:
            continue
        verified = [
            summarize(agent.completed, 1)
            for agent in role_agents
            if label_by_agent.get(agent.agent_id) == "Verified"
        ]
        risks = [item for agent in role_agents for item in agent.blockers]
        needs = [item for agent in role_agents for item in agent.needs]
        report_lines.append(
            f"| {role} | {table_cell(', '.join(agent.agent_id for agent in role_agents))} | {table_cell(summarize(verified, 3))} | {table_cell(summarize(risks, 3))} | {table_cell(summarize(needs, 3))} |"
        )
    report_lines.extend(
        [
            "",
            "## User/Product Impact",
            "- Product impact is based only on verified or explicitly labeled agent evidence.",
            "",
            "## Risks and Dependencies",
            f"- Blockers: {summarize([item for agent in agents for item in agent.blockers], 5)}",
            f"- Needs: {summarize([item for agent in agents for item in agent.needs], 5)}",
            "",
            "## Decisions Needed",
            "- Confirm whether unverified claims can be accepted or must return to the owning agent.",
            "",
            "## Meaning Preservation",
            f"- Source work docs: {summarize([rel(doc, root) for doc in work_docs], 5)}",
            "- Assumptions: Manager did not rewrite source work meaning; missing evidence remains labeled.",
            f"- Verification report: {rel(verification_file, root)}",
        ]
    )
    report_file.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    next_lines = [
        f"# Team Next-Step Plan - {version}",
        "",
        "## Planning Window",
        f"- Start: {now.strftime('%Y-%m-%d')}",
        f"- End: {(now + timedelta(days=7)).strftime('%Y-%m-%d')}",
        f"- Based on verification: {rel(verification_file, root)}",
        "",
        "## Review Gate",
        f"- Requirement review: {rel(Path(review['path']), root)}",
        f"- Status: {review['status']}",
        f"- Implementation allowed: {review['allowed']}",
        f"- Next review action: {'continue role analysis and review corrections' if not review_allowed else 'development may proceed'}",
        "",
    ]
    if team_mode == "solo":
        next_lines.extend(
            [
                "## Solo Role Rotation",
                "- One Codex operator may execute multiple role cards, but must update the active role card before switching roles.",
                f"- Recommended order: {SOLO_ROLE_ORDER}.",
                "- Use devops only when build, environment, deployment, release, or script work becomes part of the task.",
                "- Manager remains the final reality-check role and should verify evidence after implementation roles report.",
                "",
            ]
        )
    if review_allowed:
        priority_lines = [
            "1. Fix mismatch and blocked items.",
            "2. Add evidence for unverified completion claims.",
            "3. Continue verified work toward acceptance criteria.",
        ]
    else:
        priority_lines = [
            "1. Complete and approve the pre-implementation review gate.",
            "2. Fix mismatch and blocked items.",
            "3. Add evidence for unverified completion claims.",
            "4. Continue verified work toward acceptance criteria.",
        ]
    next_lines.extend(
        [
            "## Priority Order",
            *priority_lines,
            "",
            "## Agent Assignments",
            "| Agent | Role | Next Task | Reason | Done Definition | Dependency |",
            "|---|---|---|---|---|---|",
        ]
    )
    for agent, label, _, mismatches in evidence_rows:
        if label == "Verified":
            task = summarize(agent.next_items, 1)
            reason = "Verified work can move to next planned item."
        elif label == "Mismatch":
            task = "Fix claimed file or update claim with the correct path."
            reason = summarize(mismatches, 2)
        elif label == "Blocked":
            task = "Resolve blocker or request manager escalation."
            reason = summarize(agent.blockers, 2)
        elif label == "Planned":
            if not review_allowed:
                task = review_task_for_role(agent.role)
            else:
                task = summarize(agent.next_items, 1)
            if task == "-":
                task = "Start role work according to current priority order."
            reason = "Role is registered but has not reported work yet."
        else:
            task = "Provide changed files, tests, or direct implementation evidence."
            reason = "Completion claim is not yet verified."
        next_lines.append(
            f"| {table_cell(agent.agent_id)} | {table_cell(agent.role)} | {table_cell(task)} | {table_cell(reason)} | Update agent card with evidence and status. | {table_cell(summarize(agent.needs, 2))} |"
        )
    if not evidence_rows:
        next_lines.append("| manager | manager | Register execution agents and create first work item. | No agent cards found. | Plan/agents contains active agents. | - |")
    next_lines.extend(["", "## Manager Follow-Up", f"- Re-run manager cycle after correction tasks update their agent cards."])
    plan_file.write_text("\n".join(next_lines) + "\n", encoding="utf-8")

    if not archive_file.exists():
        archive_file.write_text("# Project Archive\n\n## Cycles\n", encoding="utf-8")
    with archive_file.open("a", encoding="utf-8") as fp:
        fp.write(
            f"\n## {now.strftime('%Y-%m-%d %H:%M')} - {version}\n"
            f"- Current verification: {rel(verification_file, root)}\n"
            f"- Current product report: {rel(report_file, root)}\n"
            f"- Current next steps: {rel(plan_file, root)}\n"
            f"- Evidence health: {verified_count} verified, {unverified_count} unverified, {mismatch_count} mismatch, {blocked_count} blocked, {planned_count} planned\n"
        )

    if not memory_file.exists():
        memory_file.write_text("# Project Memory\n\n## Durable Decisions\n-\n\n## Open Risks\n-\n\n## Stable Constraints\n-\n", encoding="utf-8")
    with memory_file.open("a", encoding="utf-8") as fp:
        fp.write(
            f"\n## Manager Cycle {now.strftime('%Y-%m-%d %H:%M')} - {version}\n"
            f"- Source verification: {rel(verification_file, root)}\n"
            f"- Open evidence gaps: {unverified_count + mismatch_count + blocked_count}\n"
        )
        for agent, label, _, mismatches in evidence_rows:
            if label in {"Mismatch", "Blocked"}:
                fp.write(f"- {agent.agent_id} [{label}]: {summarize(mismatches or agent.blockers, 2)}\n")

    print(f"[OK] Verification: {verification_file}")
    print(f"[OK] Product report: {report_file}")
    print(f"[OK] Next steps: {plan_file}")
    print(f"[OK] Archive updated: {archive_file}")
    print(f"[OK] Memory updated: {memory_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
