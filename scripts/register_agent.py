#!/usr/bin/env python3
"""Create or refresh one version-local agent identity file."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path


ROLES = {"frontend", "backend", "product", "architect", "tester", "devops", "manager"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register a Project Harness Lite agent.")
    parser.add_argument("--project-root", required=True, help="Project root path.")
    parser.add_argument("--version", default="v1", help="Demand implementation version.")
    parser.add_argument("--agent-id", required=True, help="Unique id, for example backend-2.")
    parser.add_argument("--role", required=True, choices=sorted(ROLES), help="Agent role.")
    parser.add_argument("--responsibility", default="", help="Main responsibility for this agent.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing agent card.")
    return parser.parse_args()


def safe_agent_id(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_.-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    if not value:
        raise ValueError("--agent-id cannot be empty after normalization.")
    return value


def append_role_index(role_file: Path, agent_id: str, responsibility: str) -> None:
    role_file.parent.mkdir(parents=True, exist_ok=True)
    if not role_file.exists():
        role_file.write_text(
            f"# Role Summary: {role_file.stem}\n\n## Active Agents\n-\n\n## Current Responsibilities\n-\n",
            encoding="utf-8",
        )
    text = role_file.read_text(encoding="utf-8")
    entry = f"- {agent_id}: {responsibility or 'unassigned responsibility'}"
    if entry not in text:
        with role_file.open("a", encoding="utf-8") as fp:
            fp.write(f"\n## Agent Registration\n{entry}\n")


def main() -> int:
    args = parse_args()
    root = Path(args.project_root).resolve()
    plan = root / "Plan"
    version = args.version.strip() or "v1"
    version_dir = plan / "versions" / version
    agent_id = safe_agent_id(args.agent_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    for name in ("agents", "roles"):
        (version_dir / name).mkdir(parents=True, exist_ok=True)

    agent_file = version_dir / "agents" / f"{agent_id}.md"
    if agent_file.exists() and not args.force:
        print(f"[OK] Agent already exists: {agent_file}")
    else:
        agent_file.write_text(
            f"""# Agent: {agent_id}

## Identity
- Agent ID: {agent_id}
- Role: {args.role}
- Responsibility: {args.responsibility}
- Version: {version}
- Started: {now}

## Scope
- Owns: {args.responsibility}
- Should coordinate with:
- Should not own: manager reporting unless role is manager

## Current Status
- State: registered
- Summary:
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
-

## Next Suggestions
-

## Key Updates
- {now}: Registered as {args.role}.
""",
            encoding="utf-8",
        )
        print(f"[OK] Wrote agent card: {agent_file}")

    append_role_index(version_dir / "roles" / f"{args.role}.md", agent_id, args.responsibility)
    print(f"[OK] Updated role index: {version_dir / 'roles' / (args.role + '.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
