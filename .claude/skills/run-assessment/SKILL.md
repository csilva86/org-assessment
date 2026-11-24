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
   - The alias is given explicitly. Run `sf org display --target-org <alias> --json` and show
     the consultant the org name and instance. Wait for a yes before collecting.
2. **Create the snapshot folder** `snapshots/<alias>/<YYYY-MM-DD_HHMM>/`.
3. **Collect in parallel.** Start these five subagents at the same time, each with the alias
   and the snapshot folder:
   `collector-licenses-users`, `collector-permissions`, `collector-objects-config`,
   `collector-automations`, `collector-limits`.
   Give `collector-objects-config` the list of objects the approved checks mention.
4. **Check the snapshot.** Every area has a `_manifest.json`. List any errors for the
   consultant before going on.
5. **Analyse.** Run the deterministic checks: `python -m checks run $requirements <snapshot>`.
   *(Not built yet — next step of the project.)*
6. **Report.** *(Not built yet.)* Client summary, consultant detail and `gaps.json` in
   `reports/<alias>/<timestamp>/`.

Never skip step 1. Never run a check on the live org: only on the snapshot.
