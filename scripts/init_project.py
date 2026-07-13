#!/usr/bin/env python3
"""Initialize a project-local versioned Plan/ harness."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path


VERSION_DIRS = ["agents", "roles", "reviews", "reports", "verification", "next-steps", "archive", "handoff"]

ROLES = ["frontend", "backend", "product", "architect", "tester", "devops", "manager"]

SOLO_ROLE_RESPONSIBILITIES = {
    "product": "Clarify user demand, product intent, non-goals, and acceptance criteria.",
    "architect": "Define architecture, module boundaries, technical risks, and integration contracts.",
    "backend": "Implement server-side behavior, domain logic, data models, APIs, and backend tests.",
    "frontend": "Implement UI, interaction flows, state handling, frontend integration, and visual quality.",
    "tester": "Plan and run verification, regression checks, acceptance review, and evidence collection.",
    "devops": "Handle build, environment, deployment, scripts, and release checks when needed.",
    "manager": "Verify reality, coordinate role handoff, publish reports, refresh memory, and assign next steps.",
}

DEFAULT_SOLO_ROLES = ["product", "architect", "backend", "frontend", "tester", "manager"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize Plan/ for Project Harness Lite.")
    parser.add_argument("--project-root", required=True, help="Project root path.")
    parser.add_argument("--demand-id", default="demand-initial", help="Boss/user demand id.")
    parser.add_argument("--version", default="v1", help="Demand implementation version, for example v1.")
    parser.add_argument(
        "--team-mode",
        choices=["multi", "solo"],
        default="multi",
        help="Use multi for independent agents, or solo for one Codex operator rotating through roles.",
    )
    parser.add_argument(
        "--solo-owner",
        default="solo-codex",
        help="Human/account label for solo mode, for example account-xerina.",
    )
    parser.add_argument(
        "--include-devops",
        action="store_true",
        help="In solo mode, create an active solo-devops role card too.",
    )
    return parser.parse_args()


def write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def solo_roles(include_devops: bool) -> list[str]:
    roles = list(DEFAULT_SOLO_ROLES)
    if include_devops and "devops" not in roles:
        roles.insert(-1, "devops")
    return roles


def agent_card(agent_id: str, role: str, responsibility: str, version: str, now: str, solo_owner: str) -> str:
    return f"""# Agent: {agent_id}

## Identity
- Agent ID: {agent_id}
- Role: {role}
- Responsibility: {responsibility}
- Version: {version}
- Started: {now}
- Solo owner: {solo_owner}

## Scope
- Owns: {responsibility}
- Should coordinate with: same solo operator's other role cards; manager verifies cross-role claims.
- Should not own: manager reporting unless role is manager.

## Current Status
- State: planned
- Summary: Waiting for role rotation.
- Last updated: {now}

## Completed
-

## In Progress
-

## Changed Files
-

## Evidence
- Tests:
- Build:
- Manual verification:
- Notes:

## Blockers
-

## Needs From Others
-

## Handoff
- When leaving this role, summarize decisions, changed files, risks, and the next role to activate.

## Next Suggestions
-

## Key Updates
- {now}: Created for solo role rotation as {role}.
"""


def role_summary(role: str, version: str, team_mode: str, agent_id: str | None = None) -> str:
    responsibility = SOLO_ROLE_RESPONSIBILITIES.get(role, "")
    active_agent = agent_id or "-"
    mode_note = (
        "Solo mode: one Codex operator rotates into this role and updates this role's agent card."
        if agent_id
        else "Role is available but not active in the current solo rotation."
    )
    return f"""# Role Summary: {role} ({version})

## Active Agents
- {active_agent}

## Current Responsibilities
- {responsibility}

## Status Summary
- {mode_note}
- Team mode: {team_mode}

## Open Risks
-
"""


def role_assignment_rows(active_roles: list[str]) -> str:
    rows = []
    for role in active_roles:
        agent_id = f"solo-{role}"
        rows.append(
            f"| {agent_id} | {role} | {SOLO_ROLE_RESPONSIBILITIES[role]} | planned |"
        )
    return "\n".join(rows)


def review_document(version: str, demand_id: str, team_mode: str, now: str) -> str:
    return f"""# Requirement Review - {version}

## Review Gate
- Demand ID: {demand_id}
- Version: {version}
- Status: draft
- Review owner: manager or architect
- Implementation allowed: no
- Team mode: {team_mode}
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
    plan = root / "Plan"
    version = args.version.strip() or "v1"
    demand_id = args.demand_id.strip() or "demand-initial"
    version_dir = plan / "versions" / version
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    team_mode = args.team_mode
    active_solo_roles = solo_roles(args.include_devops) if team_mode == "solo" else []
    role_rows = (
        role_assignment_rows(active_solo_roles)
        if team_mode == "solo"
        else "|  |  |  |  |"
    )
    devops_state = "active" if args.include_devops else "available on demand"

    (plan / "demands").mkdir(parents=True, exist_ok=True)
    (plan / "memory").mkdir(parents=True, exist_ok=True)
    for name in VERSION_DIRS:
        (version_dir / name).mkdir(parents=True, exist_ok=True)

    write_if_missing(
        plan / "demands" / f"{demand_id}.md",
        f"""# Demand: {demand_id}

## Original Demand
-

## Product Intent
-

## Version History
- {version}: created at {now}
""",
    )

    write_if_missing(
        version_dir / "work.md",
        f"""# Version Work: {version}

## Demand
- Demand ID: {demand_id}
- Version: {version}

## Team Mode
- Mode: {team_mode}
- Solo owner: {args.solo_owner if team_mode == "solo" else "-"}
- Role rotation: {"product -> architect -> backend/frontend -> tester -> manager" if team_mode == "solo" else "manager coordinates independent agents"}
- DevOps: {devops_state if team_mode == "solo" else "available as an explicit role"}

## Review Gate
- Requirement review: Plan/versions/{version}/reviews/current-requirement-review.md
- Status: draft
- Implementation allowed: no
- Rule: development starts only after manager or architect marks the current review file approved.

## Goal
-

## Product Context
- User problem:
- Business value:
- Non-goals:

## Scope
- Included:
- Excluded:

## Acceptance Criteria
-

## Role Assignments
| Agent | Role | Responsibility | Status |
|---|---|---|---|
{role_rows}

## Dependencies
-

## Risks
-

## Active Gaps
- No active manager correction gaps.

## Manager Corrections
- This section is rewritten by manager verification when task gaps appear.

## Manager Notes
- Created: {now}
""",
    )

    for role in ROLES:
        solo_agent_id = f"solo-{role}" if role in active_solo_roles else None
        write_if_missing(
            version_dir / "roles" / f"{role}.md",
            role_summary(role, version, team_mode, solo_agent_id),
        )

    if team_mode == "solo":
        for role in active_solo_roles:
            agent_id = f"solo-{role}"
            write_if_missing(
                version_dir / "agents" / f"{agent_id}.md",
                agent_card(
                    agent_id,
                    role,
                    SOLO_ROLE_RESPONSIBILITIES[role],
                    version,
                    now,
                    args.solo_owner,
                ),
            )

    write_if_missing(
        version_dir / "reviews" / "current-requirement-review.md",
        review_document(version, demand_id, team_mode, now),
    )

    write_if_missing(
        version_dir / "archive" / "project-archive.md",
        "# Project Archive\n\n## Cycles\n",
    )
    write_if_missing(
        plan / "memory" / "project-memory.md",
        "# Project Memory\n\n## Durable Decisions\n-\n\n## Open Risks\n-\n\n## Stable Constraints\n-\n",
    )

    print(f"[OK] Initialized Project Harness Lite under {version_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
