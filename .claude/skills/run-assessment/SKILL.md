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
2. **Create the snapshot folder and its five area folders** before starting any collector:
   `snapshots/<alias>/<YYYY-MM-DD_HHMM>/{licenses-users,permissions,objects-config,automations,limits}/`.
3. **Collect in parallel.** Start these five subagents at the same time, each with the alias
   and the snapshot folder:
   `collector-licenses-users`, `collector-permissions`, `collector-objects-config`,
   `collector-automations`, `collector-limits`.
   Give `collector-objects-config` the list of objects the approved checks mention (every object in
   `objects_exist` and `object_access` rules). It describes exactly those.
4. **Check the snapshot.** Every area has a `_manifest.json`. List any errors for the
   consultant before going on.
5. **Analyse.** Run the deterministic checks:
   `python -m checks run $requirements <snapshot>`.
   It writes `reports/<alias>/<timestamp>/results.json`. Show the consultant the summary it prints.
   Checks marked `needs_judgement` are for the consultant; you may add your reading of the
   evidence, clearly labelled as judgement.
6. **Report.** *(Not built yet.)* Client summary, consultant detail and `gaps.json` in
   `reports/<alias>/<timestamp>/`.

Never skip step 1. Never run a check on the live org: only on the snapshot.
