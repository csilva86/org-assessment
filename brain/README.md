# brain/ — the second brain

Knowledge that carries from one project to the next. The `requirements-translator` agent reads
it before drafting checks.

## What goes here

- `patterns/` — business rule → checks mappings that worked
  (e.g. "an SLA rule usually needs these five checks").
- Recurring gaps and how they were solved.
- Lessons learned.

## What never goes here (guardrail 2)

No client names, project names, user names, emails, record ids, org ids, numbers or settings
taken from a client org. Write the pattern, not the case:

| ✅ Pattern | ❌ Client data |
| --- | --- |
| "SLA rules need Entitlements enabled; it is often off in orgs that grew from Sales Cloud." | "ACME's org had Entitlements off and 12 support users." |

Claude proposes new entries at the end of a project; the consultant approves them before they
are saved.
