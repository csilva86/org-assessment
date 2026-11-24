# Org Assessment — instructions for Claude Code

This repository checks whether a Salesforce org meets a set of functional and technical
requirements, and documents the org. It never changes the org.

## Guardrails (non-negotiable)

1. **Read-only.** Never run anything that changes an org: no deploy, no data writes, no
   anonymous Apex, no permission assignments. `.claude/hooks/guard_readonly.py` blocks these
   commands by code. If a command is blocked, do not look for another way to run it: stop and
   tell the consultant.
2. **Confidentiality between clients.** Data from one client never goes into another client's
   work, into `brain/`, into commits or into examples. `snapshots/` and `reports/` are
   git-ignored and stay on this machine. `brain/` holds patterns only: no client names, user
   names, emails, record ids, numbers or settings of a specific org. `python -m brain check`
   scans for them; use placeholders such as `<custom_object>`.
3. **The consultant approves.** You may draft the translation of business rules into checks.
   No check runs until the consultant has approved the requirements file
   (`status: approved`). The same goes for the second brain: you write proposals to
   `brain/proposals/`; only the consultant runs `python -m brain approve`, in their own terminal.
   `.claude/hooks/guard_brain.py` blocks you from writing to `brain/patterns/` and from running
   `approve`.
4. **Code before AI.** Every check that can be exact is written as code in `checks/` and gives
   the same result every time. You judge only what code cannot decide, and you mark those
   results as `judgement`.
5. **Every conclusion has evidence.** Nothing goes into a report without the snapshot data
   that proves it (file and path inside the snapshot).

## How a run works

1. **Requirements** — business rules in `requirements/<project>.yaml` (format:
   `requirements/README.md`). The `requirements-translator` agent drafts the technical checks;
   the consultant approves.
2. **Collection** — the collector agents run **in parallel**, one per area. Each one runs
   `python -m collect area <area> ...` once; the script runs the read-only commands, checks each
   with the guardrail, and writes the data and the manifest into
   `snapshots/<org-alias>/<YYYY-MM-DD_HHMM>/<area>/`:
   - `collector-licenses-users`
   - `collector-permissions`
   - `collector-objects-config`
   - `collector-automations`
   - `collector-limits`
3. **Analysis** — deterministic checks in `checks/` run on the snapshot, never on the live org.
   Each result is `met`, `partial` or `not_met`, with severity and evidence.
4. **Output** — client summary (business language), consultant detail, and `gaps.json`
   (input for the future development pipeline). Markdown is the source; PDF/HTML for delivery.
5. **Org documentation** — `python -m orgdoc build <snapshot>`: overview, licenses and users (counted,
   never named), data dictionary, permission matrix, automation map, limits, and a methodology
   appendix, from the same snapshot.
6. **Second brain** — after a project, `/propose-patterns <requirements> <results.json>` drafts
   up to three anonymised patterns in `brain/proposals/` and scans them (`python -m brain check`).
   The consultant approves each one with `python -m brain approve` or deletes it. The
   `requirements-translator` reads the approved patterns (`python -m brain list`).

## Conventions

- Use the `sf` CLI (v2) with `--json`. Never `sfdx`.
- SOQL lives in `queries/<area>/*.soql` and runs with `sf data query --file`. Never pass SOQL
  inline with `--query "..."`: on Windows the quotes break the `sf` path (see `queries/README.md`).
- The org alias comes from the consultant. Never guess it, and never use a default org.
- Snapshot folders are named after the alias: `snapshots/<alias>/<YYYY-MM-DD_HHMM>/`.
- Never delete, move or rename files in `snapshots/` or `reports/`, even after a failed run.
  Start a new snapshot folder instead, and tell the consultant what can be cleaned up.
- Read `.claude/skills/salesforce-readonly-collection/SKILL.md` before collecting. Never collect
  by running `sf` by hand: use `python -m collect`.
- Code is Python 3, tested with pytest (`python -m pytest tests`).
- Write in English in code, file names and reports' technical parts.
