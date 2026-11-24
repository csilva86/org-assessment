---
name: run-assessment
description: Runs an Org Assessment end to end for an approved requirements file and an org alias. Use when the consultant asks to assess an org.
disable-model-invocation: true
arguments: [requirements, alias]
argument-hint: <requirements-file> <org-alias>
---

# Run an Org Assessment

Requirements file: `$requirements` · Org alias: `$alias`

1. **Check the inputs.**
   - The requirements file exists and has `status: approved`. If not, stop: the consultant
     approves first (guardrail 3).
   - The alias is given explicitly. Confirm the org with
     `sf data query --file queries/objects-config/organization.soql --target-org $alias --json`
     and show the consultant the org name, Id, type and whether it is a sandbox. Wait for a yes
     before collecting. Never use `sf org display`: it prints the access token (the hook blocks it).
2. **Choose the snapshot folder** `snapshots/<alias>/<YYYY-MM-DD_HHMM>/` (a new one, never reused).
   The collectors' script creates it.
3. **Collect in parallel.** Start these five subagents at the same time, each with the alias and
   the snapshot folder:
   `collector-licenses-users`, `collector-permissions`, `collector-objects-config`,
   `collector-automations`, `collector-limits`.
   Give `collector-objects-config` the list of objects the approved checks mention (every object in
   `objects_exist` and `object_access` rules); it also describes every custom object
   (`--describe-custom`). Each subagent runs `python -m collect area ...` once.
4. **Check the snapshot.** Every area has a `_manifest.json`. List any errors for the
   consultant before going on.
5. **Analyse.** Run the deterministic checks:
   `python -m checks run $requirements <snapshot>`.
   It writes `reports/<alias>/<timestamp>/results.json`. Show the consultant the summary it prints.
   Checks marked `needs_judgement` are for the consultant; you may add your reading of the
   evidence, clearly labelled as judgement.
6. **Report.** Step 5 already wrote, next to `results.json`: `client-summary.md` and `.html`,
   `consultant-detail.md` and `.html`, and `gaps.json`. If the consultant wants PDFs, run
   `python -m checks report <results.json> --pdf`. Show the consultant the client summary and list the
   gaps. Do not rewrite or "improve" the reports: they are built by code on purpose.

7. **Org documentation.** Run `python -m orgdoc build <snapshot>` (add `--pdf` for a PDF). It writes
   `org-documentation.md` and `.html` next to the reports. Tell the consultant where they are.

Never skip step 1. Never run a check on the live org: only on the snapshot.
