# Memory Rules

Project Harness Lite memory is project-local and evidence-aware.

## Store

- Confirmed product decisions.
- Stable architecture constraints.
- API or integration contracts used by multiple agents.
- Repeated blockers that remain open.
- Owner mappings that are still active.
- Verification findings that affect future work.

## Do Not Store

- Cross-project facts.
- One-time conversation details.
- Claims marked `Unverified` unless they are stored as risks.
- Personal preferences unrelated to the current project.
- Completed minor tasks with no future impact.

## Write Rules

1. Append to `Plan/memory/project-memory.md`.
2. Include source version, report, or verification file path.
3. Label unresolved items clearly.
4. Revisit old memory during each manager cycle and keep stale assumptions visible.
