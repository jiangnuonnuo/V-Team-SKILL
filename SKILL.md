---
name: project-harness-lite
description: Lightweight per-project engineering harness for coordinating multiple Codex agents or one solo Codex operator rotating through product, architect, frontend, backend, tester, optional devops, and manager roles by demand version. Use when a project needs isolated Plan/ management, versioned work such as v1/v2, role-based solo or multi-agent execution, agent identity files, multi-role status tracking, manager verification against project reality, product reports, archives, project memory, handoff, and next-round task allocation without cross-project memory.
---

# Project Harness Lite

Use this skill to run a small project-local engineering organization inside a repository. Each boss demand is split into product/engineering versions such as `v1` and `v2`; each Codex thread can act as a named agent inside the active version, or one solo Codex operator can rotate through role cards such as `solo-product`, `solo-architect`, `solo-backend`, `solo-frontend`, `solo-tester`, optional `solo-devops`, and `solo-manager`. Execution roles implement work and keep their own compact status current; the manager role verifies reality before reporting, archiving, remembering, and assigning the next cycle.

## Core Rules

1. Keep all management state inside the current project root under `Plan/`.
2. Never merge memory between projects.
3. Treat `Plan/versions/<version>/agents/<agent-id>.md` as the source for one agent thread in that version.
4. Support multiple agents with the same role, such as `backend-1`, `backend-2`, and `backend-3`.
5. Execution agents implement work and update their own agent file; they do not write global project reports.
6. Manager agents do not claim completion from status text alone; they inspect project reality and label evidence.
7. Manager agents write only manager artifacts: verification reports, product reports, archives, memory, and next-step plans.
8. Do not create a new work file for every dialogue. Keep one version folder active until product scope or acceptance criteria changes enough to justify a new version.
9. Treat planning files as living documents. Update or rewrite the current plan when reality changes instead of appending every conversation.
10. Preserve original demand meaning, but allow product plans, role plans, corrections, and next steps to be directly revised.
11. In solo mode, one Codex operator may rotate through multiple role cards, but each work segment must name the active role and update that role's own agent card before switching.
12. Treat `devops` as optional until build, environment, deployment, release, script, or CI work becomes part of the current version.
13. Before implementation, run the version's pre-implementation review gate in `Plan/versions/<version>/reviews/current-requirement-review.md`.
14. Do not create a new review file for each rejection or re-review. Revise the current review file in place until it is approved.
15. Development starts only after the manager or architect marks the current review gate as approved.

## Project Layout

Use this layout in each project:

```text
Plan/
  demands/
    demand-001.md
  versions/
    v1/
      work.md
      agents/
      roles/
      reviews/current-requirement-review.md
      reports/current-product-report.md
      verification/current-verification.md
      next-steps/current-team-plan.md
      archive/
      handoff/
    v2/
      work.md
      ...
  memory/
    project-memory.md
```

Use `demands/` for the original boss/user demand. Use `versions/v1`, `versions/v2`, etc. for product planning and implementation cycles. A version can contain many dialogue updates and many manager cycles.

## Quick Start

Initialize a project:

```bash
python <path-to-this-skill>/scripts/init_project.py --project-root <project-root> --demand-id demand-001 --version v1
```

Initialize a one-person development team:

```bash
python <path-to-this-skill>/scripts/init_project.py --project-root <project-root> --demand-id demand-001 --version v1 --team-mode solo --solo-owner account-or-person
```

Include an active DevOps role only when the project needs build/deploy/environment ownership:

```bash
python <path-to-this-skill>/scripts/init_project.py --project-root <project-root> --demand-id demand-001 --version v1 --team-mode solo --include-devops
```

Register a Codex thread as an agent:

```bash
python <path-to-this-skill>/scripts/register_agent.py --project-root <project-root> --version v1 --agent-id backend-2 --role backend --responsibility "user permission module"
```

Update compact status after execution work:

```bash
python <path-to-this-skill>/scripts/update_agent_status.py --project-root <project-root> --version v1 --agent-id backend-2 --done "Implemented permission API" --changed backend/src/auth.py --next "Add integration test"
```

Update the fixed pre-implementation review file:

```bash
python <path-to-this-skill>/scripts/update_review.py --project-root <project-root> --version v1 --reviewer architect --status in-review --backend-analysis "API boundary is feasible but error codes need definition" --frontend-analysis "UI flow depends on login state contract"
```

Approve the review gate after rework passes:

```bash
python <path-to-this-skill>/scripts/update_review.py --project-root <project-root> --version v1 --reviewer architect --status approved --decision-result approved --decision-note "Requirement review passed; implementation can start"
```

Run one manager cycle:

```bash
python <path-to-this-skill>/scripts/run_manager_cycle.py --project-root <project-root> --version v1
```

Start a new version only when the product plan meaningfully changes:

```bash
python <path-to-this-skill>/scripts/init_project.py --project-root <project-root> --demand-id demand-001 --version v2
```

## Agent Workflow

When assigned to a non-manager role:

1. Register the agent if `Plan/versions/<version>/agents/<agent-id>.md` is missing.
2. Read `Plan/demands/<demand-id>.md`, `Plan/versions/<version>/work.md`, `Plan/versions/<version>/reviews/current-requirement-review.md`, and own versioned agent file.
3. Implement the assigned feature in the project.
4. Update only the own agent file with completed work, changed files, blockers, needs, and next suggestions.
5. Include concrete file paths and test/build evidence whenever possible.
6. Keep the agent file as a current summary. Do not store every dialogue turn.
7. Use `--mode replace` when a prior claim is wrong, rejected, or superseded by a new plan.

## Solo Dev Team Workflow

Use solo mode when one person/account wants Codex to behave like a coordinated development team rather than a single undifferentiated assistant.

1. Start with `solo-product` to clarify the demand, product intent, non-goals, and acceptance criteria.
2. Rotate to `solo-architect` to define architecture, module boundaries, technical risks, and integration contracts.
3. Fill the pre-implementation review file with product, architect, backend, frontend, and tester analyses.
4. Let `solo-manager` or `solo-architect` chair the review meeting and mark issues directly in the same review file.
5. If the review is rejected or changes are requested, revise the same review file in place; do not create `review-2`, `review-final`, or another replacement file.
6. After the review is approved, rotate to `solo-backend` and `solo-frontend` for implementation. Use both when the feature crosses API/UI boundaries; use only the relevant role for narrow work.
7. Rotate to `solo-tester` to create and run verification, regression checks, and acceptance review.
8. Rotate to `solo-devops` only when build, environment, deployment, release, script, or CI work is in scope.
9. Finish the cycle as `solo-manager`: inspect project reality, run the manager cycle, refresh report/next steps/memory, and assign the next role.

Before switching roles or Codex accounts:

- Update the current role's agent card with completed work, changed files, evidence, blockers, handoff, and next suggestions.
- Record the next intended role in `Handoff`.
- If the next account has no conversation context, tell it to read `Plan/versions/<version>/work.md`, `Plan/versions/<version>/agents/`, `Plan/versions/<version>/next-steps/current-team-plan.md`, and `Plan/memory/project-memory.md` before acting.

Suggested solo role ids:

- `solo-product`: user value, requirements, acceptance criteria, non-goals.
- `solo-architect`: architecture, boundaries, contracts, technical risk.
- `solo-backend`: domain logic, APIs, data, backend tests.
- `solo-frontend`: UI, interaction, state, frontend integration, visual quality.
- `solo-tester`: test plan, verification, regression, evidence.
- `solo-devops`: optional build/deploy/environment/release owner.
- `solo-manager`: reality check, report, memory, next-step allocation.

## Manager Workflow

When assigned to `manager`:

1. Read `Plan/demands/`, `Plan/versions/<version>/work.md`, `Plan/versions/<version>/reviews/current-requirement-review.md`, `Plan/versions/<version>/agents/`, `Plan/versions/<version>/roles/`, and `Plan/memory/`.
2. Inspect project reality before summarizing:
   - check claimed changed files exist
   - inspect relevant code or docs for claimed outputs
   - use visible test/build results when present
   - mark missing evidence explicitly
3. Rewrite `Plan/versions/<version>/verification/current-verification.md`.
4. Rewrite `Plan/versions/<version>/reports/current-product-report.md`.
5. Rewrite `Plan/versions/<version>/next-steps/current-team-plan.md`.
6. Append `Plan/versions/<version>/archive/project-archive.md`.
7. Append durable decisions, unresolved risks, and stable constraints to `Plan/memory/project-memory.md`.
8. When task gaps are found, directly rewrite the `Active Gaps` and `Manager Corrections` sections in `Plan/versions/<version>/work.md`.
9. In solo mode, do not trust a claim just because the same operator made it in another role; verify file paths, tests, and visible implementation evidence exactly as with a multi-agent team.
10. If the review gate is not approved, assign review correction tasks before implementation tasks.

## Pre-Implementation Review Gate

Use `Plan/versions/<version>/reviews/current-requirement-review.md` as the single living review file for one version.

Required flow:

1. Product role writes demand analysis, user value, non-goals, and acceptance criteria.
2. Architect role writes architecture impact, module boundaries, contracts, and risk points.
3. Backend role writes backend feasibility, API/data/domain changes, and backend risks.
4. Frontend role writes UI flow, state, integration dependencies, and frontend risks.
5. Tester role writes acceptance checks, regression scope, and evidence needed.
6. Manager or architect chairs the review meeting and records issues in `Review Issues`.
7. If the user, manager, or architect rejects part of the plan, edit the same file: update the relevant role analysis, issue status, decision, and revision log.
8. Repeat the review meeting in the same file until `Status: approved`, `Result: approved`, and `Implementation allowed: yes`.
9. Start development only after approval.

The review file is a living document. Preserve the current truth, not every dialogue turn. Keep durable changes in `Revision Log`; use `archive` only for milestone summaries, not for every review edit.

## Living Document Rules

Use rewrite vs append like a real project team:

- Rewrite current plan sections when requirements are clarified, rejected, corrected, or reprioritized.
- Rewrite current agent summaries when the latest state supersedes old status.
- Rewrite current review sections when requirement analysis, review issues, or decisions are rejected and corrected.
- Append only durable checkpoints: new boss demand, new version, verified milestone, unresolved risk, important decision, or release note.
- Add a new version only when the product plan or acceptance criteria changes meaningfully.
- Add a new feature node inside the current version when scope expands but the version goal remains the same.
- Add a new fix/correction node when verification finds a gap; do not create a new task file for every fix.
- Keep `archive` and `memory` concise. They should preserve decisions and evidence, not full conversation history.

## Evidence Labels

Use these labels in manager outputs:

- `Verified`: claim has project evidence, such as changed file existence, tests, or direct implementation evidence.
- `Unverified`: claim is plausible but evidence is missing or not inspected.
- `Mismatch`: claim conflicts with project files or work requirements.
- `Blocked`: claim identifies a blocker or dependency that prevents completion.
- `Planned`: role or agent is registered but has not made a completion or progress claim yet.

## Manager Reality Check

The manager must avoid hallucination by writing uncertainty directly:

- If an agent says "done" but no changed files or test evidence exists, mark it `Unverified`.
- If a claimed file does not exist, mark it `Mismatch`.
- If work requirements are not traceable to an implementation or handoff, assign a correction task.
- If tests were not run, do not imply they passed.
- If the manager infers anything, label it as an assumption.

## Resources

- `scripts/init_project.py`: create project-local `Plan/` directories and seed files; use `--team-mode solo` to pre-create solo role cards and `--include-devops` when DevOps should be active.
- `scripts/register_agent.py`: create a named agent identity file.
- `scripts/update_agent_status.py`: rewrite compact current status in an agent file.
- `scripts/update_review.py`: rewrite the fixed pre-implementation review file in place; use it for role analyses, review meeting notes, issues, corrections, and approval.
- `scripts/run_manager_cycle.py`: rewrite current verification/report/plan, refresh work gaps, and append concise archive/memory checkpoints.
- [`references/agent-card-template.md`](references/agent-card-template.md): agent identity/status format.
- [`references/work-template.md`](references/work-template.md): work definition format.
- [`references/review-template.md`](references/review-template.md): pre-implementation review format.
- [`references/product-report-template.md`](references/product-report-template.md): manager product report format.
- [`references/next-steps-template.md`](references/next-steps-template.md): next-cycle assignment format.
- [`references/verification-template.md`](references/verification-template.md): reality-check report format.
- [`references/memory-rules.md`](references/memory-rules.md): project-local memory rules.
