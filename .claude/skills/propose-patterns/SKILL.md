---
name: propose-patterns
description: At the end of a project, drafts anonymised second-brain patterns from its requirements and results, for the consultant to approve. Use when the consultant asks to close a project or to feed the second brain.
disable-model-invocation: true
arguments: [requirements, results]
argument-hint: <requirements-file> <results.json>
---

# Propose patterns for the second brain

Requirements: `$requirements` · Results: `$results`

The second brain keeps **what we learned, never whose org it was** (guardrail 2). You draft;
the consultant approves (guardrail 3). Read `brain/README.md` for the format first.

1. **Read what the project taught.** The requirements file (business rules, checks, notes), the
   results (`results.json`: which checks were met, partial, not met, and why) and the approved
   patterns (`python -m brain list`, then read the ones that look related in `brain/patterns/`).
2. **Pick at most three lessons worth keeping.** Good candidates:
   - a business rule that needed a set of checks you would reuse (`rule-to-checks`);
   - a gap that is likely to show up again, with its usual cause and fix (`recurring-gap`);
   - something about the method that would have saved time (`lesson`).
   If an approved pattern already says it, propose an update to it with the same `id`: copy it,
   change what the project taught, add 1 to `seen_in_projects`.
3. **Write the pattern, not the case.** Replace every name from the org with a placeholder:
   `<custom_object>`, `<permission_set>`, `<profile>`, `<license>`; every number taken from the
   client becomes a placeholder such as `<min_available>`. No client, project, user, org or
   alias names, no record ids, no emails, no figures from the org. Standard Salesforce names
   (Case, Entitlement, PermissionsModifyAllData, Salesforce Platform) are fine.
4. **Save each one** as `brain/proposals/<id>.yaml` with `status: proposed`, `proposed_on` set to
   today and no approval fields. Never write to `brain/patterns/` (the hook blocks it).
5. **Check them:** `python -m brain check brain/proposals`. Fix every `BLOCK` line and look at
   every `WARN` line. Run it again until nothing is blocked.
6. **Hand over to the consultant.** For each proposal, one line on what it says and why it is
   worth keeping, then the command they run **in their own terminal** to approve it:

   ```
   python -m brain approve brain/proposals/<id>.yaml --by "<consultant name>"
   ```

   To reject one, the consultant deletes the file. Do not run `approve` yourself: the hook blocks
   it and the command needs a person at the terminal.
